"""
main.py  –  Sorare MLB Scoreboard
Dashboard Streamlit : scores Sorare calculés depuis l'API officielle MLB.
"""

import streamlit as st
import datetime
import pandas as pd
import logging

import db
import sync
from mlb_fetcher import search_player

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# ─── Config page ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sorare MLB Scoreboard",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Init ─────────────────────────────────────────────────────────────────────
db.init_db()
sync.start_scheduler()

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #0d1117; }
.score-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
}
.score-big { font-size: 2rem; font-weight: 700; }
.score-pos { color: #3fb950; }
.score-neg { color: #f85149; }
.score-zero { color: #8b949e; }
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
}
.badge-hitter { background: #1f6feb; color: #fff; }
.badge-pitcher { background: #388bfd22; color: #388bfd; border: 1px solid #388bfd; }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar : Gestion du Roster ──────────────────────────────────────────────
with st.sidebar:
    st.title("⚾ Sorare MLB")
    st.markdown("---")
    st.subheader("👥 Mon Roster")

    roster = db.get_roster()
    if roster:
        for p in roster:
            col1, col2 = st.columns([3, 1])
            role_icon = "🥎" if p["role"] == "pitcher" else "🏏"
            col1.markdown(f"{role_icon} **{p['name']}** `{p['position']}`")
            if col2.button("✕", key=f"rm_{p['player_id']}", help="Retirer du roster"):
                db.remove_player(p["player_id"])
                st.rerun()
    else:
        st.info("Roster vide. Ajoute des joueurs ci-dessous.")

    st.markdown("---")
    st.subheader("➕ Ajouter un joueur")

    search_query = st.text_input("Nom du joueur", placeholder="ex: Shohei Ohtani")
    if search_query and len(search_query) >= 3:
        with st.spinner("Recherche…"):
            try:
                results = search_player(search_query)
                if results:
                    for r in results[:5]:
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"**{r['name']}** — {r['team']} `{r['position']}`")
                        role_guess = "pitcher" if r["position"] in ("SP", "RP", "P", "CL") else "hitter"
                        if c2.button("＋", key=f"add_{r['id']}"):
                            db.add_player(r["id"], r["name"], r["team"], r["position"], role_guess)
                            st.success(f"{r['name']} ajouté !")
                            st.rerun()
                else:
                    st.warning("Aucun joueur trouvé.")
            except Exception as e:
                st.error(f"Erreur recherche : {e}")

    st.markdown("---")
    st.caption("🔄 Synchro auto toutes les 15 min (13h–04h UTC)")

# ─── Tabs principaux ──────────────────────────────────────────────────────────
tab_scores, tab_history, tab_sync = st.tabs(["📊 Scores du jour", "📅 Historique", "🔄 Synchronisation"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Scores du jour (ou date choisie)
# ══════════════════════════════════════════════════════════════════════════════
with tab_scores:
    col_date, col_btn = st.columns([3, 1])

    # Dates disponibles
    available_dates = db.get_all_dates_with_scores()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    # Par défaut : hier (matchs terminés)
    default_date = datetime.date.fromisoformat(yesterday) if yesterday in available_dates \
                   else (datetime.date.fromisoformat(available_dates[0]) if available_dates
                         else datetime.date.today() - datetime.timedelta(days=1))

    selected_date = col_date.date_input(
        "Date", value=default_date, max_value=datetime.date.today()
    )

    if col_btn.button("🔄 Synchro maintenant", use_container_width=True):
        progress_bar = st.progress(0, text="Démarrage…")
        status_text  = st.empty()

        def progress_cb(current, total, msg):
            if total > 0:
                progress_bar.progress(current / total, text=msg)
            status_text.text(msg)

        sync.set_progress_callback(progress_cb)
        result = sync.sync_date(selected_date, force=True)
        progress_bar.empty()
        status_text.empty()
        sync.set_progress_callback(None)

        synced = result.get("synced", 0)
        errors = result.get("errors", 0)
        no_game = result.get("no_game", 0)
        if result.get("running"):
            st.warning("⏳ Une synchro est déjà en cours.")
        elif result.get("error_msg"):
            st.error(f"❌ Erreur API MLB : {result['error_msg']}")
        else:
            st.success(f"✅ {synced} joueur(s) synchro | {no_game} pas joué | {errors} erreur(s)")
        st.rerun()

    st.markdown("---")

    # Affichage des scores
    date_str = selected_date.isoformat()
    scores = db.get_scores_for_date(date_str)

    if not scores:
        st.info(f"Aucune donnée pour le {date_str}. Lance une synchronisation →")
    else:
        # Résumé
        valid = [s for s in scores if s["total"] is not None]
        no_game_list = [s for s in scores if s["total"] is None]

        if valid:
            total_team = sum(s["total"] for s in valid)
            avg = total_team / len(valid)
            best = max(valid, key=lambda x: x["total"])

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🏆 Score équipe", f"{total_team:.1f}")
            m2.metric("📊 Moyenne", f"{avg:.1f}")
            m3.metric("⭐ Meilleur", f"{best['player_name']} ({best['total']:.1f})")
            m4.metric("👥 Joueurs actifs", len(valid))

            st.markdown("---")

        # Cards joueurs
        for s in scores:
            name    = s.get("player_name", "?")
            pos     = s.get("position", "?")
            role    = s.get("role", "hitter")
            total   = s.get("total")
            team    = s.get("team", "")

            badge_class = "badge-pitcher" if role == "pitcher" else "badge-hitter"
            badge_label = "Pitcher" if role == "pitcher" else "Hitter"

            if total is None:
                score_html = '<span class="score-zero">— DNS</span>'
                score_class = "score-zero"
            else:
                score_class = "score-pos" if total >= 0 else "score-neg"
                score_html = f'<span class="score-big {score_class}">{total:+.1f}</span>'

            with st.expander(f"{name}  |  {team}  `{pos}`  →  {total if total is not None else 'DNS'} pts"):
                col_sc, col_bd = st.columns([1, 2])
                col_sc.markdown(f"<div style='text-align:center'>{score_html}<br>"
                                f"<span class='badge {badge_class}'>{badge_label}</span></div>",
                                unsafe_allow_html=True)

                breakdown = s.get("breakdown", {})
                if breakdown:
                    bd_df = pd.DataFrame(
                        [{"Action": k, "Points": v} for k, v in breakdown.items()]
                    ).sort_values("Points", ascending=False)
                    col_bd.dataframe(bd_df, hide_index=True, use_container_width=True)
                else:
                    col_bd.info("Pas de match joué ce jour.")

        # Joueurs sans données
        if no_game_list:
            st.markdown(f"*{len(no_game_list)} joueur(s) n'ont pas joué ce jour : "
                        + ", ".join(s["player_name"] for s in no_game_list) + "*")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Historique multi-jours
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("📅 Historique des scores")

    roster = db.get_roster()
    if not roster:
        st.info("Roster vide.")
    else:
        available_dates = db.get_all_dates_with_scores()
        if not available_dates:
            st.info("Aucune donnée historique. Lance une synchronisation.")
        else:
            # Sélection plage de dates
            col_s, col_e = st.columns(2)
            max_d = datetime.date.fromisoformat(available_dates[0])
            min_d = datetime.date.fromisoformat(available_dates[-1])
            start_d = col_s.date_input("Du", value=min_d, min_value=min_d, max_value=max_d, key="hist_start")
            end_d   = col_e.date_input("Au", value=max_d, min_value=min_d, max_value=max_d, key="hist_end")

            # Tableau pivotable
            rows = []
            for p in roster:
                pid = p["player_id"]
                scores_list = db.get_scores_range(pid, start_d.isoformat(), end_d.isoformat())
                for sc in scores_list:
                    rows.append({
                        "Joueur": p["name"],
                        "Date": sc["date"],
                        "Rôle": sc.get("role", "?"),
                        "Score": sc["total"],
                    })

            if rows:
                df = pd.DataFrame(rows)
                pivot = df.pivot_table(index="Joueur", columns="Date", values="Score", aggfunc="first")
                pivot["TOTAL"] = pivot.sum(axis=1, skipna=True)
                pivot["MOY"]   = pivot.drop(columns=["TOTAL"]).mean(axis=1, skipna=True).round(1)
                pivot = pivot.sort_values("TOTAL", ascending=False)

                st.dataframe(
                    pivot.style.format("{:.1f}", na_rep="DNS")
                               .background_gradient(cmap="RdYlGn", subset=pd.IndexSlice[:, pivot.columns[:-2]]),
                    use_container_width=True,
                )

                # Graphe par joueur
                st.markdown("---")
                player_selected = st.selectbox("Zoom sur un joueur", options=df["Joueur"].unique())
                df_p = df[df["Joueur"] == player_selected].set_index("Date")["Score"].dropna()
                if not df_p.empty:
                    st.bar_chart(df_p, use_container_width=True)
            else:
                st.info("Aucun score dans cette plage de dates.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Synchronisation manuelle avancée
# ══════════════════════════════════════════════════════════════════════════════
with tab_sync:
    st.subheader("🔄 Synchronisation manuelle")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Synchro d'une date précise**")
        sync_date_sel = st.date_input("Date à synchro", key="sync_single",
                                      value=datetime.date.today() - datetime.timedelta(days=1))
        force_resync = st.checkbox("Forcer (re-fetch même si déjà synchro)", value=False)

        if st.button("▶ Lancer", key="btn_single", use_container_width=True):
            with st.spinner(f"Synchro {sync_date_sel}…"):
                r = sync.sync_date(sync_date_sel, force=force_resync)
            if r.get("error_msg"):
                st.error(f"Erreur : {r['error_msg']}")
            else:
                st.success(f"✅ {r.get('synced',0)} synchro | {r.get('no_game',0)} DNS | {r.get('errors',0)} erreurs")

    with col_b:
        st.markdown("**Synchro des N derniers jours**")
        n_days = st.slider("Nombre de jours", 1, 30, 7)

        if st.button("▶ Lancer (multi-jours)", key="btn_multi", use_container_width=True):
            progress = st.progress(0)
            results = []
            today = datetime.date.today()
            for i in range(1, n_days + 1):
                d = today - datetime.timedelta(days=i)
                progress.progress(i / n_days, text=f"Synchro {d}…")
                r = sync.sync_date(d, force=False)
                r["date"] = d.isoformat()
                results.append(r)
            progress.empty()

            df_res = pd.DataFrame(results)[["date", "synced", "no_game", "errors"]]
            st.dataframe(df_res, hide_index=True, use_container_width=True)

    st.markdown("---")
    st.markdown("**État du scheduler automatique**")
    scheduler_ok = sync._scheduler and sync._scheduler.running
    if scheduler_ok:
        st.success("✅ Scheduler actif — synchro toutes les 15 min (13h–04h UTC)")
        jobs = sync._scheduler.get_jobs()
        for j in jobs:
            st.code(f"{j.id}: prochain run → {j.next_run_time}")
    else:
        st.warning("⚠️ Scheduler inactif.")
