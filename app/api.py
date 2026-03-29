"""
api.py — FastAPI : API JSON + serving du dashboard HTML
Port 8504. Remplace le container Nginx — plus besoin de volume nginx.conf.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import datetime, zoneinfo, os

import db, gameweek as gw_module, so7 as so7_engine

TZ = zoneinfo.ZoneInfo("Europe/Paris")

app = FastAPI(title="Sorare MLB Dashboard API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Chemin vers le dashboard HTML (copié dans /app par le Dockerfile)
DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")

def _today() -> datetime.date:
    return datetime.datetime.now(tz=TZ).date()


# ── Dashboard TV ──────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    """Sert le dashboard TV directement — http://ton-ip:8504"""
    try:
        with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>dashboard.html introuvable</h1>", status_code=404)


# ── API données MLB ───────────────────────────────────────────────────────────
@app.get("/api/dashboard")
def get_dashboard():
    today    = _today()
    cur_gw   = gw_module.current_gw()
    gw_start = datetime.date.fromisoformat(cur_gw["start_date"])
    gw_end   = datetime.date.fromisoformat(cur_gw["end_date"])
    roster   = db.get_roster()

    day_scores = db.get_scores_for_date(today.isoformat())

    gw_by_player = {}
    for p in roster:
        pid = p["player_id"]
        sc_list = db.get_scores_range(
            pid, cur_gw["start_date"], min(today, gw_end).isoformat()
        )
        gw_by_player[pid] = round(
            sum(s["total"] for s in sc_list if s.get("total") is not None), 2
        )

    so7_result = None
    try:
        gw_scores = so7_engine.compute_gameweek_scores(
            cur_gw["start_date"], min(today, gw_end).isoformat()
        )
        raw = so7_engine.optimize_so7(gw_scores)
        if raw:
            so7_result = {
                "total": raw["total"],
                "lineup": {
                    slot: {
                        "name":         p["name"],
                        "position":     p["position"],
                        "team":         p["team"],
                        "role":         p["role"],
                        "total_gw":     p["total_gw"],
                        "games_played": p["games_played"],
                        "player_id":    p["player_id"],
                        "label":        so7_engine.SLOT_LABELS[slot],
                        "days":         p["days"],
                    }
                    for slot, p in raw["lineup"].items()
                },
            }
    except Exception as e:
        so7_result = {"error": str(e)}

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
    players_out.sort(key=lambda x: (x["score_today"] is None, -(x["score_today"] or 0)))

    gw_team_total = sum(gw_by_player.values())
    days_done     = max(0, (min(today, gw_end) - gw_start).days + 1)
    days_total    = (gw_end - gw_start).days + 1

    return {
        "timestamp":    datetime.datetime.now(tz=TZ).isoformat(),
        "today":        today.isoformat(),
        "gameweek": {
            **cur_gw,
            "team_total": gw_team_total,
            "days_done":  days_done,
            "days_total": days_total,
        },
        "players":      players_out,
        "so7":          so7_result,
        "roster_count": len(roster),
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.datetime.now(tz=TZ).isoformat()}


if __name__ == "__main__":
    import uvicorn
    db.init_db()
    uvicorn.run(app, host="0.0.0.0", port=8504, log_level="info")
