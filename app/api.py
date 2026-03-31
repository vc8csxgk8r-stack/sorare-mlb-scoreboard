"""
api.py — FastAPI pour le dashboard TV (port 8504)
Sert aussi index.html sur GET /
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import datetime, zoneinfo, os

import db, gameweek as gw_mod, so7 as so7_mod

TZ = zoneinfo.ZoneInfo("Europe/Paris")
app = FastAPI(title="Sorare MLB API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["GET"], allow_headers=["*"])

HTML_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")

def _today(): return datetime.datetime.now(tz=TZ).date()

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    try:
        return HTMLResponse(open(HTML_PATH, encoding="utf-8").read())
    except FileNotFoundError:
        return HTMLResponse("<h1>dashboard.html introuvable</h1>", status_code=404)

@app.get("/api/dashboard")
def get_dashboard():
    today    = _today()
    cur_gw   = gw_mod.current_gw()
    gw_start = datetime.date.fromisoformat(cur_gw["start_date"])
    gw_end   = datetime.date.fromisoformat(cur_gw["end_date"])
    roster   = db.get_roster()
    range_end = min(today, gw_end).isoformat()

    day_scores = db.get_scores_for_date(today.isoformat())

    gw_by_pid = {}
    for p in roster:
        sc_list = db.get_scores_range(p["player_id"], cur_gw["start_date"], range_end)
        gw_by_pid[p["player_id"]] = round(
            sum(s["total"] for s in sc_list if s.get("total") is not None), 2
        )

    # So7
    so7_result = None
    try:
        gw_scores = so7_mod.compute_gameweek_scores(cur_gw["start_date"], range_end)
        raw = so7_mod.optimize_so7(gw_scores)
        if raw:
            so7_result = {
                "total": raw["total"],
                "lineup": {
                    slot: {
                        "name": p["name"], "position": p["position"],
                        "team": p["team"], "role": p["role"],
                        "total_gw": p["total_gw"], "games_played": p["games_played"],
                        "player_id": p["player_id"],
                        "label": so7_mod.SLOT_LABELS[slot], "days": p["days"],
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
            "name":        s.get("player_name","?"),
            "position":    s.get("position","?"),
            "team":        s.get("team",""),
            "role":        s.get("role","hitter"),
            "score_today": s.get("total"),
            "score_gw":    gw_by_pid.get(pid, 0.0),
            "headshot":    f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{pid}/headshot/67/current",
        })
    players_out.sort(key=lambda x: (x["score_today"] is None, -(x["score_today"] or 0)))

    team_total = sum(gw_by_pid.values())
    days_done  = max(0, (min(today, gw_end) - gw_start).days + 1)
    days_total = (gw_end - gw_start).days + 1

    return {
        "timestamp": datetime.datetime.now(tz=TZ).isoformat(),
        "today":     today.isoformat(),
        "gameweek":  {**cur_gw, "team_total": team_total,
                      "days_done": days_done, "days_total": days_total},
        "players":   players_out,
        "so7":       so7_result,
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.datetime.now(tz=TZ).isoformat()}

if __name__ == "__main__":
    import uvicorn
    db.init_db()
    uvicorn.run(app, host="0.0.0.0", port=8504, log_level="info")
