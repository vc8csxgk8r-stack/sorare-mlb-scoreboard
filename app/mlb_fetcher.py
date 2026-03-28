"""
mlb_fetcher.py
Récupère les box scores officiels MLB via l'API statsapi.mlb.com (sans clé API).
Compatible avec la structure JSON actuelle de l'API MLB (2024-2025).
"""

import requests
import datetime
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://statsapi.mlb.com/api/v1"

# ─── Timeout & session ────────────────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "sorare-mlb-scoreboard/1.0"})

def _get(path: str, params: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    try:
        r = SESSION.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logger.error(f"MLB API error [{url}]: {e}")
        raise

# ─── Recherche joueur ─────────────────────────────────────────────────────────
def search_player(name: str) -> list[dict]:
    """Retourne une liste de joueurs correspondant au nom (prénom+nom ou nom seul)."""
    data = _get("/people/search", {"names": name, "hydrate": "currentTeam"})
    results = []
    for p in data.get("people", []):
        results.append({
            "id": p["id"],
            "name": p.get("fullName", ""),
            "team": p.get("currentTeam", {}).get("name", "N/A"),
            "position": p.get("primaryPosition", {}).get("abbreviation", "?"),
        })
    return results

# ─── Matchs d'un jour ─────────────────────────────────────────────────────────
def get_game_ids_for_date(date: datetime.date) -> list[int]:
    """Retourne les IDs de matchs MLB pour une date donnée."""
    date_str = date.strftime("%Y-%m-%d")
    data = _get("/schedule", {
        "sportId": 1,
        "date": date_str,
        "gameType": "R,F,D,L,W",   # Regular + playoffs
        "fields": "dates,games,gamePk,status,abstractGameState",
    })
    ids = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            # On ne prend que les matchs terminés
            if g.get("status", {}).get("abstractGameState") == "Final":
                ids.append(g["gamePk"])
    return ids

# ─── Box score d'un match ─────────────────────────────────────────────────────
def get_box_score(game_pk: int) -> dict:
    """Retourne le box score complet d'un match."""
    return _get(f"/game/{game_pk}/boxscore")

# ─── Stats d'un joueur dans tous les matchs d'un jour ─────────────────────────
def get_player_stats_for_date(player_id: int, date: datetime.date) -> dict | None:
    """
    Cherche un joueur dans tous les matchs du jour.
    Retourne un dict unifié de ses stats (batting ou pitching) ou None s'il n'a pas joué.
    """
    game_ids = get_game_ids_for_date(date)
    if not game_ids:
        return None

    for gid in game_ids:
        try:
            box = get_box_score(gid)
        except Exception:
            continue

        for side in ("home", "away"):
            team = box.get("teams", {}).get(side, {})
            players = team.get("players", {})
            key = f"ID{player_id}"
            if key not in players:
                continue

            p = players[key]
            stats = p.get("stats", {})
            position = p.get("position", {}).get("abbreviation", "")

            # Pitcher
            if "pitching" in stats and stats["pitching"].get("inningsPitched") is not None:
                raw = stats["pitching"]
                return {
                    "player_id": player_id,
                    "name": p.get("person", {}).get("fullName", str(player_id)),
                    "date": date.isoformat(),
                    "game_pk": gid,
                    "role": "pitcher",
                    "position": position,
                    # Stats pitching
                    "innings_pitched": _parse_ip(raw.get("inningsPitched", "0")),
                    "strikeouts": raw.get("strikeOuts", 0),
                    "walks": raw.get("baseOnBalls", 0),
                    "hits_allowed": raw.get("hits", 0),
                    "earned_runs": raw.get("earnedRuns", 0),
                    "home_runs_allowed": raw.get("homeRuns", 0),
                    "wins": raw.get("wins", 0),
                    "losses": raw.get("losses", 0),
                    "saves": raw.get("saves", 0),
                    "holds": raw.get("holds", 0),
                    "blown_saves": raw.get("blownSaves", 0),
                    "complete_game": 1 if raw.get("completeGames", 0) >= 1 else 0,
                    "shutout": 1 if raw.get("shutouts", 0) >= 1 else 0,
                    "no_hitter": 0,  # non dispo dans box score simple
                    "hit_batsmen": raw.get("hitBatsmen", 0),  # ✅ ajouté
                    # Batting aussi si two-way
                    "at_bats": 0, "hits": 0, "singles": 0, "doubles": 0,
                    "triples": 0, "home_runs": 0, "rbi": 0, "runs": 0,
                    "stolen_bases": 0, "caught_stealing": 0,
                    "walks_bat": 0, "strikeouts_bat": 0,
                    "hit_by_pitch": 0, "sacrifice_fly": 0,
                }

            # Hitter
            if "batting" in stats:
                raw = stats["batting"]
                ab = raw.get("atBats", 0)
                h  = raw.get("hits", 0)
                d  = raw.get("doubles", 0)
                t  = raw.get("triples", 0)
                hr = raw.get("homeRuns", 0)
                singles = max(0, h - d - t - hr)
                return {
                    "player_id": player_id,
                    "name": p.get("person", {}).get("fullName", str(player_id)),
                    "date": date.isoformat(),
                    "game_pk": gid,
                    "role": "hitter",
                    "position": position,
                    # Stats batting
                    "at_bats": ab,
                    "hits": h,
                    "singles": singles,
                    "doubles": d,
                    "triples": t,
                    "home_runs": hr,
                    "rbi": raw.get("rbi", 0),
                    "runs": raw.get("runs", 0),
                    "stolen_bases": raw.get("stolenBases", 0),
                    "caught_stealing": raw.get("caughtStealing", 0),
                    "walks_bat": raw.get("baseOnBalls", 0),
                    "strikeouts_bat": raw.get("strikeOuts", 0),
                    "hit_by_pitch": raw.get("hitByPitch", 0),
                    "sacrifice_fly": raw.get("sacFlies", 0),
                    # Pitching vide
                    "innings_pitched": 0.0, "strikeouts": 0, "walks": 0,
                    "hits_allowed": 0, "earned_runs": 0, "home_runs_allowed": 0,
                    "wins": 0, "losses": 0, "saves": 0, "holds": 0,
                    "blown_saves": 0, "complete_game": 0, "shutout": 0, "no_hitter": 0,
                }

    return None  # Pas joué ce jour


def get_player_headshot_url(player_id: int) -> str:
    """
    Retourne l'URL du portrait officiel MLB (API img.mlbstatic.com).
    Toujours disponible, pas besoin d'appel réseau pour construire l'URL.
    """
    return f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{player_id}/headshot/67/current"

def get_player_action_url(player_id: int) -> str:
    """Portrait action (fond transparent, format moderne)."""
    return f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:action:cutout:current.png/w_280,q_auto:best/v1/people/{player_id}/action/cutout/current"
    """Convertit '6.2' (6 manches + 2 tiers) en float décimal réel."""
    try:
        parts = str(ip_str).split(".")
        full = int(parts[0])
        thirds = int(parts[1]) if len(parts) > 1 else 0
        return round(full + thirds / 3, 4)
    except Exception:
        return 0.0
