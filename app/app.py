import streamlit as st
import pandas as pd
import json
import sqlite3
import os
from datetime import date, timedelta, datetime
from apscheduler.schedulers.background import BackgroundScheduler
import statsapi

st.set_page_config(page_title="Sorare MLB Scores", layout="wide")
st.title("📊 Sorare MLB - Scores recalculés (sans login)")

# ===================== CONFIG =====================
DB_PATH = "/app/data/scores.db"
ROSTER_PATH = "/app/data/roster.json"

# ===================== INIT DB & ROSTER =====================
def init_db():
    os.makedirs("/app/data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS daily_scores (date TEXT PRIMARY KEY, data TEXT)")
    conn.close()

    if not os.path.exists(ROSTER_PATH):
        with open(ROSTER_PATH, "w") as f:
            json.dump([], f)

init_db()

def load_roster():
    with open(ROSTER_PATH) as f:
        return json.load(f)

def save_roster(roster):
    with open(ROSTER_PATH, "w") as f:
        json.dump(roster, f, indent=2)

def get_last_snapshot():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM daily_scores ORDER BY date DESC LIMIT 1", conn)
    conn.close()
    if not df.empty:
        return json.loads(df['data'].iloc[0]), df['date'].iloc[0]
    return None, None

# ===================== SCORING SORARE MLB OFFICIEL =====================
def calculate_sorare_score(stats, player_type="hitter"):
    if player_type == "hitter":
        singles = stats.get('hits', 0) - stats.get('doubles', 0) - stats.get('triples', 0) - stats.get('homeRuns', 0)
        score = (
            stats.get('runs', 0) * 3 +           # R
            stats.get('rbi', 0) * 3 +            # RBI
            singles * 2 +                        # 1B
            stats.get('doubles', 0) * 5 +        # 2B
            stats.get('triples', 0) * 8 +        # 3B
            stats.get('homeRuns', 0) * 10 +      # HR
            stats.get('baseOnBalls', 0) * 2 +    # BB
            stats.get('hitByPitch', 0) * 2 +     # HBP
            stats.get('stolenBases', 0) * 5 +    # SB
            stats.get('strikeOuts', 0) * (-1)    # K
        )
        return round(score, 1)
    else:  # pitcher
        score = (
            stats.get('inningsPitched', 0) * 3 +
            stats.get('strikeOuts', 0) * 2 +
            stats.get('wins', 0) * 5 +
            stats.get('saves', 0) * 10 +
            stats.get('holds', 0) * 5 +
            stats.get('earnedRuns', 0) * (-2) +
            stats.get('baseOnBalls', 0) * (-1) +
            stats.get('hits', 0) * (-0.5) +
            stats.get('hitByPitch', 0) * (-1)
        )
        return round(score, 1)

# ===================== SYNCHRO =====================
def perform_sync():
    with st.spinner("🔄 Récupération des stats MLB et calcul des scores..."):
        roster = load_roster()
        if not roster:
            st.warning("Aucun joueur dans ton roster. Ajoute-en dans la sidebar.")
            return

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        start_period = (date.today() - timedelta(days=10)).isoformat()
        season = str(date.today().year)

        results = []
        for player in roster:
            try:
                player_id = player.get("mlb_id")
                if not player_id:
                    lookup = statsapi.lookup_player(player["name"])
                    if lookup:
                        player_id = lookup[0]["id"]

                if not player_id:
                    results.append({"player": player["name"], "score_cumule": 0, "type": player["type"], "matches": 0})
                    continue

                # Récupération des game logs
                data = statsapi.get('people', {
                    'personId': player_id,
                    'hydrate': f'stats(group={player["type"]},type=gameLog,season={season})'
                })

                splits = []
                if 'people' in data and data['people']:
                    stats_list = data['people'][0].get('stats', [])
                    if stats_list:
                        splits = stats_list[0].get('splits', [])

                total_score = 0
                match_count = 0
                for split in splits:
                    game_date = split.get('date')
                    if game_date and start_period <= game_date <= yesterday:
                        total_score += calculate_sorare_score(split.get('stat', {}), player["type"])
                        match_count += 1

                results.append({
                    "player": player["name"],
                    "score_cumule": total_score,
                    "type": player["type"],
                    "matches": match_count
                })
            except Exception:
                results.append({"player": player["name"], "score_cumule": 0, "type": player["type"], "matches": 0})

        # Sauvegarde
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO daily_scores (date, data) VALUES (?, ?)",
                     (yesterday, json.dumps(results)))
        conn.commit()
        conn.close()

        st.success(f"✅ Synchro terminée ! Snapshot du {yesterday} sauvegardé.")
        st.rerun()

# ===================== SCHEDULER =====================
scheduler = BackgroundScheduler()
scheduler.add_job(perform_sync, 'cron', hour=7, minute=0)

def check_game_day():
    try:
        today = date.today().isoformat()
        if statsapi.schedule(start_date=today, end_date=today):
            scheduler.add_job(perform_sync, 'interval', minutes=10, id='live_sync', replace_existing=True)
            st.toast("⚾ Jour de matchs MLB détecté → synchro toutes les 10 minutes activée", icon="⚾")
    except:
        pass

scheduler.add_job(check_game_day, 'cron', hour=9, minute=0)
scheduler.start()

# ===================== INTERFACE =====================
st.sidebar.header("📋 Mon roster Sorare MLB")
roster = load_roster()

with st.sidebar.expander("➕ Ajouter un joueur"):
    name = st.text_input("Nom du joueur (ex: Aaron Judge)")
    mlb_id = st.number_input("MLB ID (optionnel mais recommandé)", value=0, step=1)
    ptype = st.selectbox("Type de joueur", ["hitter", "pitcher"])
    if st.button("Ajouter au roster"):
        if name:
            roster.append({"name": name.strip(), "mlb_id": int(mlb_id) if mlb_id else None, "type": ptype})
            save_roster(roster)
            st.rerun()

if roster:
    st.sidebar.dataframe(pd.DataFrame(roster)[["name", "type"]], hide_index=True)

col1, col2 = st.columns([3,1])
with col2:
    if st.button("🔄 Lancer une synchro manuelle maintenant", type="primary", use_container_width=True):
        perform_sync()

last_snapshot, snapshot_date = get_last_snapshot()

if last_snapshot:
    df = pd.DataFrame(last_snapshot)
    st.subheader(f"📅 Scores cumulés de la gameweek (snapshot du {snapshot_date})")
    st.dataframe(
        df.sort_values("score_cumule", ascending=False)[["player", "type", "score_cumule", "matches"]],
        use_container_width=True,
        hide_index=True
    )
    st.metric("Total équipe", f"{df['score_cumule'].sum():.1f} pts")
else:
    st.info("Aucun snapshot disponible pour l’instant. Ajoute tes joueurs puis lance une synchro.")

st.caption("Données officielles MLB • Scoring Sorare officiel • Snapshot stable du jour d’avant • Synchro auto 10 min les jours de matchs")
