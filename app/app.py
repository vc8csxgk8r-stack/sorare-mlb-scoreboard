import streamlit as st
import pandas as pd
import json
import sqlite3
import os
from datetime import date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import statsapi

st.set_page_config(page_title="Sorare MLB Scores", layout="wide")
st.title("📊 Sorare MLB - Scores recalculés (sans login)")

DB_PATH = "/app/data/scores.db"
ROSTER_PATH = "/app/data/roster.json"

def init_db():
    os.makedirs("/app/data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS daily_scores (date TEXT PRIMARY KEY, data TEXT)")
    conn.close()
    if not os.path.exists(ROSTER_PATH):
        with open(ROSTER_PATH, "w") as f: json.dump([], f)

init_db()

def load_roster():
    with open(ROSTER_PATH) as f: return json.load(f)

def get_last_snapshot():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM daily_scores ORDER BY date DESC LIMIT 1", conn)
    conn.close()
    return (json.loads(df['data'].iloc[0]), df['date'].iloc[0]) if not df.empty else (None, None)

def calculate_sorare_score(stats, player_type="hitter"):
    if player_type == "hitter":
        singles = stats.get('hits', 0) - stats.get('doubles', 0) - stats.get('triples', 0) - stats.get('homeRuns', 0)
        return round(
            stats.get('runs', 0)*3 + stats.get('rbi', 0)*3 + singles*2 +
            stats.get('doubles', 0)*5 + stats.get('triples', 0)*8 + stats.get('homeRuns', 0)*10 +
            stats.get('baseOnBalls', 0)*2 + stats.get('hitByPitch', 0)*2 +
            stats.get('stolenBases', 0)*5 - stats.get('strikeOuts', 0), 1)
    else:
        return round(stats.get('inningsPitched', 0)*3 + stats.get('strikeOuts', 0)*2 + stats.get('wins', 0)*5 +
                     stats.get('saves', 0)*10 + stats.get('holds', 0)*5 - stats.get('earnedRuns', 0)*2, 1)

def perform_sync():
    with st.spinner("🔄 Calcul des scores de la soirée d'hier..."):
        roster = load_roster()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        season = str(date.today().year)
        results = []

        st.write("**DEBUG - Récupération des game logs (hier soir) :**")
        for player in roster:
            try:
                player_id = player.get("mlb_id")
                data = statsapi.get('people', {'personId': player_id, 'hydrate': f'stats(group={player["type"]},type=gameLog,season={season})'})
                splits = data['people'][0]['stats'][0]['splits'] if 'people' in data and data['people'] else []
                
                total = 0
                match_count = 0
                for split in splits:
                    if split.get('date') == yesterday:
                        total += calculate_sorare_score(split.get('stat', {}), player["type"])
                        match_count += 1
                
                results.append({"player": player["name"], "score_cumule": total, "type": player["type"], "matches": match_count})
                st.write(f"✅ {player['name']} → {match_count} matchs hier (score {total})")
            except Exception as e:
                results.append({"player": player["name"], "score_cumule": 0, "type": player["type"], "matches": 0})
                st.write(f"❌ {player['name']} → Erreur: {str(e)[:100]}")

        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO daily_scores (date, data) VALUES (?, ?)", (yesterday, json.dumps(results)))
        conn.commit()
        conn.close()

        st.success(f"✅ Scores du {yesterday} calculés et sauvegardés !")
        st.rerun()

# Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(perform_sync, 'cron', hour=7, minute=0)
scheduler.start()

# UI
st.sidebar.header("📋 Mon roster Sorare MLB")
roster = load_roster()
if roster:
    st.sidebar.dataframe(pd.DataFrame(roster)[["name", "type"]], hide_index=True)

if st.button("🔄 Calculer les scores de la soirée d'hier", type="primary", use_container_width=True):
    perform_sync()

last_snapshot, snapshot_date = get_last_snapshot()
if last_snapshot:
    df = pd.DataFrame(last_snapshot)
    st.subheader(f"📅 Scores du {snapshot_date} (soirée d'hier)")
    st.dataframe(df.sort_values("score_cumule", ascending=False)[["player", "type", "score_cumule", "matches"]], use_container_width=True, hide_index=True)
    st.metric("Total équipe", f"{df['score_cumule'].sum():.1f} pts")
else:
    st.info("Clique sur le bouton ci-dessus pour lancer le calcul.")
