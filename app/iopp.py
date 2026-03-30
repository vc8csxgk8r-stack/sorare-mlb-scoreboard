"""
iopp.py  — Index de Performance des Joueurs (IOPP / L15 Sorare)

Sorare utilise une moyenne glissante des 15 derniers matchs joués ("L15")
comme indicateur de forme. On la compare entre saison 2025 et 2026.

Sources :
  - Scores Sorare calculés en DB (saison en cours)
  - API MLB Stats pour les stats brutes historiques saison 2025
    → endpoint /people/{id}/stats?stats=season&season=2025&group=hitting/pitching
"""

import requests
import datetime
import logging
import db
import sorare_scoring

logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "sorare-mlb-iopp/1.0"})
BASE_URL = "https://statsapi.mlb.com/api/v1"

# Nombre de matchs pour le L-N Sorare
L_WINDOW = 15


def _get_season_stats(player_id: int, season: int, group: str) -> dict:
    """Récupère les stats agrégées saison complète d'un joueur via MLB API."""
    try:
        url = f"{BASE_URL}/people/{player_id}/stats"
        r = SESSION.get(url, params={
            "stats":  "season",
            "season": season,
            "group":  group,
            # hydrate permet d'avoir gamesPlayed et gamesPitched
        }, timeout=10)
        r.raise_for_status()
        data = r.json()
        splits = data.get("stats", [{}])[0].get("splits", [])
        if splits:
            return splits[0].get("stat", {})
    except Exception as e:
        logger.warning(f"[iopp] Stats {season} {group} pour {player_id}: {e}")
    return {}


def _games_for_pitcher(raw: dict) -> int:
    """
    Retourne le nombre de matchs effectifs d'un pitcher.
    Priorité : gamesPitched > gamesStarted > gamesPlayed.
    """
    gp = raw.get("gamesPitched") or raw.get("gamesStarted") or raw.get("gamesPlayed") or 0
    try:
        return int(gp)
    except (ValueError, TypeError):
        return 0


def _stats_to_sorare_score_hitter(raw: dict, games: int) -> float:
    """
    Convertit des stats agrégées saison en score Sorare moyen par match.
    On divise chaque compteur par le nombre de matchs joués.
    """
    if not raw or games == 0:
        return 0.0
    h   = raw.get("hits", 0)
    d   = raw.get("doubles", 0)
    t   = raw.get("triples", 0)
    hr  = raw.get("homeRuns", 0)
    singles = max(0, h - d - t - hr)
    per_game = {
        "role":           "hitter",
        "singles":        singles / games,
        "doubles":        d       / games,
        "triples":        t       / games,
        "home_runs":      hr      / games,
        "rbi":            raw.get("rbi", 0)             / games,
        "runs":           raw.get("runs", 0)            / games,
        "stolen_bases":   raw.get("stolenBases", 0)     / games,
        "walks_bat":      raw.get("baseOnBalls", 0)     / games,
        "hit_by_pitch":   raw.get("hitByPitch", 0)      / games,
        "strikeouts_bat": raw.get("strikeOuts", 0)      / games,
        "hits":           h / games,
    }
    return sorare_scoring.compute_score(per_game)["total"]


def _stats_to_sorare_score_pitcher(raw: dict, games: int) -> float:
    if not raw or games == 0:
        return 0.0
    ip_str = raw.get("inningsPitched", "0")
    try:
        parts  = str(ip_str).split(".")
        ip_tot = int(parts[0]) + (int(parts[1]) if len(parts) > 1 else 0) / 3
    except Exception:
        ip_tot = 0.0

    # Si 0 innings, on essaie quand même avec les autres stats
    if ip_tot == 0 and games > 0:
        # Pas de stats pitching valides
        return 0.0

    per_game = {
        "role":            "pitcher",
        "innings_pitched": ip_tot / games,
        "strikeouts":      raw.get("strikeOuts", 0)    / games,
        "walks":           raw.get("baseOnBalls", 0)   / games,
        "hits_allowed":    raw.get("hits", 0)          / games,
        "earned_runs":     raw.get("earnedRuns", 0)    / games,
        "hit_batsmen":     raw.get("hitBatsmen", 0)    / games,
        "wins":            raw.get("wins", 0)          / games,
        "saves":           raw.get("saves", 0)         / games,
        "holds":           raw.get("holds", 0)         / games,
    }
    return sorare_scoring.compute_score(per_game)["total"]


def compute_iopp(player_id: int, role: str, position: str) -> dict:
    """
    Calcule l'IOPP d'un joueur :
      - L15_2026 : moyenne des 15 dernières performances Sorare en DB
      - avg_2025  : moyenne Sorare recalculée depuis les stats agrégées 2025
      - status    : Surperformance / Sous-performance / Dans la norme
    """
    # ── L15 2026 depuis la DB ──────────────────────────────────────────────────
    import zoneinfo
    today      = datetime.datetime.now(tz=zoneinfo.ZoneInfo("Europe/Paris")).date().isoformat()
    all_scores = db.get_scores_range(player_id, "2026-01-01", today)
    played     = [s for s in all_scores if s.get("total") is not None]
    last_15    = played[-L_WINDOW:] if len(played) >= 1 else played
    l15_avg    = round(sum(s["total"] for s in last_15) / len(last_15), 2) if last_15 else None
    l15_games  = len(last_15)

    # ── Moyenne 2025 depuis l'API MLB Stats ────────────────────────────────────
    is_pitcher = role == "pitcher"
    group_2025 = "pitching" if is_pitcher else "hitting"
    raw_2025   = _get_season_stats(player_id, 2025, group_2025)

    if is_pitcher:
        games_2025 = _games_for_pitcher(raw_2025)
        avg_2025   = _stats_to_sorare_score_pitcher(raw_2025, games_2025)
    else:
        games_2025 = int(raw_2025.get("gamesPlayed") or 0)
        avg_2025   = _stats_to_sorare_score_hitter(raw_2025, games_2025)

    # Arrondi — None si 0
    avg_2025 = round(avg_2025, 2) if avg_2025 and avg_2025 > 0 else None

    # Log pour debug
    logger.info(f"[iopp] player={player_id} role={role} "
                f"l15={l15_avg}({l15_games}G) avg2025={avg_2025}({games_2025}G)")

    # ── Tendance ──────────────────────────────────────────────────────────────
    if l15_avg is not None and avg_2025 and avg_2025 > 0:
        delta = l15_avg - avg_2025
        pct   = delta / avg_2025 * 100
        if pct >= 15:
            status = "🔥 Surperformance"
            status_color = "#3fb950"
        elif pct <= -15:
            status = "❄️ Sous-performance"
            status_color = "#f85149"
        else:
            status = "➡️ Dans la norme"
            status_color = "#8b949e"
    elif l15_avg is None:
        delta = None; pct = None
        status = "📭 Pas de matchs 2026"
        status_color = "#8b949e"
    else:
        delta = None; pct = None
        status = "📊 Pas de stats 2025"
        status_color = "#8b949e"

    return {
        "player_id":    player_id,
        "l15_avg":      l15_avg,
        "l15_games":    l15_games,
        "avg_2025":     avg_2025,
        "games_2025":   games_2025,
        "delta":        round(delta, 2) if delta is not None else None,
        "pct":          round(pct, 1)   if pct   is not None else None,
        "status":       status,
        "status_color": status_color,
    }


def compute_roster_iopp(roster: list[dict]) -> dict[int, dict]:
    """Calcule l'IOPP pour tous les joueurs du roster. Retourne un dict {player_id: iopp}."""
    result = {}
    for p in roster:
        pid  = p["player_id"]
        role = p.get("role", "hitter")
        pos  = p.get("position", "")
        try:
            result[pid] = compute_iopp(pid, role, pos)
        except Exception as e:
            logger.error(f"[iopp] Erreur {p['name']}: {e}")
            result[pid] = {
                "l15_avg": None, "l15_games": 0, "avg_2025": None,
                "games_2025": 0, "delta": None, "pct": None,
                "status": "❓ Erreur", "status_color": "#8b949e",
            }
    return result
