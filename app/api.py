"""
api.py — FastAPI mini-API pour le dashboard TV
Expose les données MLB (So7, scores GW, roster) en JSON.
Port 8502, même container que Streamlit.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import datetime, zoneinfo, json

import db, gameweek as gw_module, so7 as so7_engine, sync

TZ = zoneinfo.ZoneInfo("Europe/Paris")

app = FastAPI(title="Sorare MLB Dashboard API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

def _today() -> datetime.date:
    return datetime.datetime.now(tz=TZ).date()


@app.get("/api/dashboard")
def get_dashboard():
    """Point d'entrée unique — tout ce qu'il faut pour le dashboard TV."""
    today     = _today()
    cur_gw    = gw_module.current_gw()
    gw_start  = datetime.date.fromisoformat(cur_gw["start_date"])
    gw_end    = datetime.date.fromisoformat(cur_gw["end_date"])
    roster    = db.get_roster()

    # ── Scores du jour ─────────────────────────────────────────────────────────
    date_str  = today.isoformat()
    day_scores = db.get_scores_for_date(date_str)

    # ── Score GW en cours par joueur ───────────────────────────────────────────
    gw_by_player = {}
    for p in roster:
        pid = p["player_id"]
        sc_list = db.get_scores_range(
            pid, cur_gw["start_date"],
            min(today, gw_end).isoformat()
        )
        gw_by_player[pid] = round(
            sum(s["total"] for s in sc_list if s.get("total") is not None), 2
        )

    # ── Best So7 GW en cours ───────────────────────────────────────────────────
    so7_result = None
    try:
        gw_scores = so7_engine.compute_gameweek_scores(
            cur_gw["start_date"],
            min(today, gw_end).isoformat()
        )
        raw = so7_engine.optimize_so7(gw_scores)
        if raw:
            lineup_out = {}
            for slot, player in raw["lineup"].items():
                lineup_out[slot] = {
                    "name":         player["name"],
                    "position":     player["position"],
                    "team":         player["team"],
                    "role":         player["role"],
                    "total_gw":     player["total_gw"],
                    "games_played": player["games_played"],
                    "player_id":    player["player_id"],
                    "label":        so7_engine.SLOT_LABELS[slot],
                    "days":         player["days"],
                }
            so7_result = {
                "total":  raw["total"],
                "lineup": lineup_out,
            }
    except Exception as e:
        so7_result = {"error": str(e)}

    # ── Joueurs pour le carousel ────────────────────────────────────────────────
    players_out = []
    for s in day_scores:
        pid = s["player_id"]
        players_out.append({
            "player_id":   pid,
            "name":        s.get("player_name", "?"),
            "position":    s.get("position", "?"),
            "team":        s.get("team", ""),
            "role":        s.get("role", "hitter"),
            "score_today": s.get("total"),
            "score_gw":    gw_by_player.get(pid, 0.0),
            "headshot":    f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{pid}/headshot/67/current",
            "breakdown":   s.get("breakdown", {}),
        })

    # Tri : actifs par score jour desc, puis DNS
    players_out.sort(key=lambda x: (x["score_today"] is None, -(x["score_today"] or 0)))

    gw_team_total = sum(gw_by_player.values())
    days_done     = max(0, (min(today, gw_end) - gw_start).days + 1)
    days_total    = (gw_end - gw_start).days + 1

    return {
        "timestamp":  datetime.datetime.now(tz=TZ).isoformat(),
        "today":      today.isoformat(),
        "gameweek": {
            **cur_gw,
            "team_total":  gw_team_total,
            "days_done":   days_done,
            "days_total":  days_total,
        },
        "players":    players_out,
        "so7":        so7_result,
        "roster_count": len(roster),
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.datetime.now(tz=TZ).isoformat()}


if __name__ == "__main__":
    import uvicorn
    db.init_db()
    uvicorn.run(app, host="0.0.0.0", port=8502, log_level="info")
