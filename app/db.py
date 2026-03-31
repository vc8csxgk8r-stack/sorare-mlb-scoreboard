"""
db.py
Base de données locale SQLite : roster + historique des scores.
Stocké dans /data/sorare_mlb.db (volume Docker persistant).
"""

import sqlite3
import datetime
import json
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "/data/sorare_mlb.db")


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
    """Crée les tables si elles n'existent pas."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS roster (
                player_id   INTEGER PRIMARY KEY,
                name        TEXT NOT NULL,
                team        TEXT DEFAULT '',
                position    TEXT DEFAULT '',
                role        TEXT DEFAULT 'hitter',
                added_at    TEXT DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS scores (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id   INTEGER NOT NULL,
                date        TEXT NOT NULL,
                game_pk     INTEGER,
                role        TEXT,
                total       REAL,
                breakdown   TEXT,
                raw_stats   TEXT,
                synced_at   TEXT DEFAULT (datetime('now')),
                UNIQUE(player_id, date)
            );

            CREATE TABLE IF NOT EXISTS gameweeks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                label       TEXT NOT NULL,
                start_date  TEXT NOT NULL,
                end_date    TEXT NOT NULL,
                UNIQUE(start_date, end_date)
            );

            CREATE INDEX IF NOT EXISTS idx_scores_date     ON scores(date);
            CREATE INDEX IF NOT EXISTS idx_scores_player   ON scores(player_id);
        """)
    logger.info(f"DB initialisée : {DB_PATH}")
    # Corriger les rôles mal définis à l'ajout (ex: SP ajouté comme hitter)
    try:
        fix_roster_roles()
    except Exception:
        pass  # Table roster peut ne pas encore exister au tout premier démarrage


# ─── GAMEWEEKS ────────────────────────────────────────────────────────────────
def save_gameweek(label: str, start_date: str, end_date: str) -> int:
    with _conn() as con:
        cur = con.execute("""
            INSERT INTO gameweeks(label, start_date, end_date)
            VALUES (?, ?, ?)
            ON CONFLICT(start_date, end_date) DO UPDATE SET label=excluded.label
        """, (label, start_date, end_date))
        return cur.lastrowid


def get_gameweeks() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM gameweeks ORDER BY start_date DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_gameweek(gw_id: int):
    with _conn() as con:
        con.execute("DELETE FROM gameweeks WHERE id=?", (gw_id,))


# ─── ROSTER ───────────────────────────────────────────────────────────────────
def add_player(player_id: int, name: str, team: str = "", position: str = "", role: str = "hitter"):
    with _conn() as con:
        con.execute("""
            INSERT INTO roster(player_id, name, team, position, role)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(player_id) DO UPDATE SET
                name=excluded.name, team=excluded.team,
                position=excluded.position, role=excluded.role
        """, (player_id, name, team, position, role))


def remove_player(player_id: int):
    with _conn() as con:
        con.execute("DELETE FROM roster WHERE player_id=?", (player_id,))


def get_roster() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM roster ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def fix_roster_roles():
    """
    Corrige automatiquement les rôles du roster selon la position MLB.
    SP/RP/CL/P/TWP → pitcher, tout le reste → hitter.
    Appelée au démarrage pour réparer les joueurs mal catégorisés à l'ajout.
    """
    PITCHER_POS = {"SP", "RP", "CL", "P", "TWP"}
    with _conn() as con:
        players = con.execute("SELECT player_id, position, role FROM roster").fetchall()
        fixed = 0
        for p in players:
            pos = (p["position"] or "").upper()
            expected = "pitcher" if pos in PITCHER_POS else "hitter"
            if expected != p["role"]:
                con.execute("UPDATE roster SET role=? WHERE player_id=?",
                            (expected, p["player_id"]))
                fixed += 1
        if fixed:
            logger.info(f"[fix_roles] {fixed} rôle(s) corrigé(s) dans le roster")


def update_player_role(player_id: int, role: str):
    with _conn() as con:
        con.execute("UPDATE roster SET role=? WHERE player_id=?", (role, player_id))


# ─── SCORES ───────────────────────────────────────────────────────────────────
def upsert_score(player_id: int, date: str, game_pk: int | None,
                 role: str, total: float, breakdown: dict, raw_stats: dict):
    with _conn() as con:
        con.execute("""
            INSERT INTO scores(player_id, date, game_pk, role, total, breakdown, raw_stats)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id, date) DO UPDATE SET
                game_pk=excluded.game_pk, role=excluded.role,
                total=excluded.total, breakdown=excluded.breakdown,
                raw_stats=excluded.raw_stats,
                synced_at=datetime('now')
        """, (player_id, date, game_pk, role, total,
              json.dumps(breakdown), json.dumps(raw_stats)))


def upsert_no_game(player_id: int, date: str):
    """
    Enregistre qu'un joueur n'a pas joué ce jour.
    ON CONFLICT DO NOTHING → si un vrai score existe déjà, on ne l'écrase pas.
    Si l'entrée existante est aussi un no_game (total NULL), on ne touche rien.
    """
    with _conn() as con:
        con.execute("""
            INSERT INTO scores(player_id, date, game_pk, role, total, breakdown, raw_stats)
            VALUES (?, ?, NULL, NULL, NULL, '{}', '{}')
            ON CONFLICT(player_id, date) DO NOTHING
        """, (player_id, date))


def get_scores_for_date(date: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT s.*,
                   r.name     AS player_name,
                   r.position AS position,
                   r.team     AS team,
                   COALESCE(s.role, r.role) AS role
            FROM scores s
            JOIN roster r ON s.player_id = r.player_id
            WHERE s.date = ?
            ORDER BY s.total DESC NULLS LAST
        """, (date,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["breakdown"] = json.loads(d.get("breakdown") or "{}")
        d["raw_stats"]  = json.loads(d.get("raw_stats")  or "{}")
        result.append(d)
    return result


def get_scores_range(player_id: int, start: str, end: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT s.*,
                   r.role AS role    -- rôle du roster, toujours à jour
            FROM scores s
            JOIN roster r ON s.player_id = r.player_id
            WHERE s.player_id=? AND s.date BETWEEN ? AND ?
            ORDER BY s.date DESC
        """, (player_id, start, end)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["breakdown"] = json.loads(d.get("breakdown") or "{}")
        result.append(d)
    return result


def get_all_dates_with_scores() -> list[str]:
    with _conn() as con:
        rows = con.execute("""
            SELECT DISTINCT date FROM scores
            WHERE total IS NOT NULL
            ORDER BY date DESC
        """).fetchall()
    return [r["date"] for r in rows]


def is_date_synced(date: str) -> bool:
    """
    Retourne True si tous les joueurs du roster ont un enregistrement pour cette date.
    Les pitchers avec total=NULL sont re-fetchés (ils peuvent avoir pitché depuis).
    """
    with _conn() as con:
        roster_count = con.execute("SELECT COUNT(*) FROM roster").fetchone()[0]
        if roster_count == 0:
            return False
        # Vérifie que tous les joueurs ont une entrée
        synced_count = con.execute(
            "SELECT COUNT(*) FROM scores WHERE date=?", (date,)
        ).fetchone()[0]
        if synced_count < roster_count:
            return False
        # Si des pitchers ont total=NULL, pas encore considéré synchro
        # (ils pitchent rarement, on re-vérifie toujours)
        null_pitchers = con.execute("""
            SELECT COUNT(*) FROM scores s
            JOIN roster r ON s.player_id = r.player_id
            WHERE s.date=? AND s.total IS NULL AND r.role='pitcher'
        """, (date,)).fetchone()[0]
        return null_pitchers == 0
