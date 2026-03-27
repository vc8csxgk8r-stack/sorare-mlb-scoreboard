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
import so7 as so7_engine

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
tab_scores, tab_history, tab_so7, tab_sync = st.tabs(["📊 Scores du jour", "📅 Historique", "🏆 Best So7", "🔄 Synchronisation"])

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

                # Coloration manuelle sans matplotlib
                date_cols = [c for c in pivot.columns if c not in ("TOTAL", "MOY")]

                def color_score(val):
                    if pd.isna(val):
                        return "color: #8b949e"
                    if val > 30:
                        return "background-color: #1a7f37; color: white"
                    if val > 15:
                        return "background-color: #2ea043; color: white"
                    if val > 0:
                        return "background-color: #196c2e; color: #7ee787"
                    if val < 0:
                        return "background-color: #6e1c1c; color: #ff7b72"
                    return "color: #8b949e"

                styled = (
                    pivot.style
                    .format("{:.1f}", na_rep="DNS")
                    .applymap(color_score, subset=pd.IndexSlice[:, date_cols])
                    .format("{:.1f}", subset=["TOTAL", "MOY"])
                )
                st.dataframe(styled, use_container_width=True)

                # Graphe par joueur
                st.markdown("---")
                player_selected = st.selectbox("Zoom sur un joueur", options=df["Joueur"].unique())
                df_p = df[df["Joueur"] == player_selected].set_index("Date")["Score"].dropna()
                if not df_p.empty:
                    st.bar_chart(df_p, use_container_width=True)
            else:
                st.info("Aucun score dans cette plage de dates.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Best So7 (Meilleure équipe sur une gameweek)
# ══════════════════════════════════════════════════════════════════════════════
with tab_so7:
    st.subheader("🏆 Meilleure équipe So7 — Simulation gameweek")
    st.caption(
        "Calcule rétrospectivement la meilleure lineup So7 possible avec ton roster "
        "sur la période choisie, selon le barême Sorare officiel."
    )

    # ─── Sélection / gestion des gameweeks ────────────────────────────────────
    col_gw_left, col_gw_right = st.columns([2, 1])

    with col_gw_right:
        st.markdown("**📁 Sauvegarder cette gameweek**")
        gw_label = st.text_input("Nom", placeholder="ex: GW 42 — 26-30 mars", key="gw_label")
        gw_s = st.date_input("Début", key="gw_save_start",
                             value=datetime.date.today() - datetime.timedelta(days=6))
        gw_e = st.date_input("Fin", key="gw_save_end",
                             value=datetime.date.today() - datetime.timedelta(days=3))
        if st.button("💾 Sauvegarder", use_container_width=True):
            if gw_label:
                db.save_gameweek(gw_label, gw_s.isoformat(), gw_e.isoformat())
                st.success("Gameweek sauvegardée !")
                st.rerun()

        # Liste des gameweeks sauvegardées
        saved_gws = db.get_gameweeks()
        if saved_gws:
            st.markdown("**📋 Gameweeks sauvegardées**")
            for gw in saved_gws:
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{gw['label']}**  \n`{gw['start_date']}` → `{gw['end_date']}`")
                if c2.button("🗑", key=f"del_gw_{gw['id']}"):
                    db.delete_gameweek(gw["id"])
                    st.rerun()

    with col_gw_left:
        st.markdown("**📅 Choisir la période à analyser**")

        # Quick-select depuis les gameweeks sauvegardées
        saved_gws = db.get_gameweeks()
        gw_options = {f"{g['label']} ({g['start_date']} → {g['end_date']})": g
                      for g in saved_gws}
        gw_options["— Période manuelle —"] = None

        selected_gw_label = st.selectbox("Gameweek sauvegardée", list(gw_options.keys()),
                                         index=len(gw_options) - 1)
        selected_gw = gw_options[selected_gw_label]

        if selected_gw:
            so7_start = datetime.date.fromisoformat(selected_gw["start_date"])
            so7_end   = datetime.date.fromisoformat(selected_gw["end_date"])
            st.info(f"Période : **{so7_start}** → **{so7_end}**")
        else:
            so7_start = st.date_input("Début de gameweek", key="so7_start",
                                      value=datetime.date.today() - datetime.timedelta(days=5))
            so7_end   = st.date_input("Fin de gameweek", key="so7_end",
                                      value=datetime.date.today() - datetime.timedelta(days=1))

        if so7_start > so7_end:
            st.error("La date de début doit être avant la date de fin.")
            st.stop()

        # Synchro rapide si des jours manquent
        nb_days = (so7_end - so7_start).days + 1
        st.markdown(f"Période de **{nb_days} jour(s)** : "
                    + ", ".join((so7_start + datetime.timedelta(days=i)).strftime("%d/%m")
                                for i in range(nb_days)))

        if st.button("🚀 Calculer la meilleure So7", type="primary", use_container_width=True):
            # 1. Synchro auto des jours manquants
            missing = [
                so7_start + datetime.timedelta(days=i)
                for i in range(nb_days)
                if not db.is_date_synced((so7_start + datetime.timedelta(days=i)).isoformat())
            ]
            if missing:
                with st.spinner(f"Synchro {len(missing)} jour(s) manquant(s)…"):
                    for d in missing:
                        sync.sync_date(d, force=False)

            # 2. Calcul des scores cumulés sur la gameweek
            gw_scores = so7_engine.compute_gameweek_scores(
                so7_start.isoformat(), so7_end.isoformat()
            )
            st.session_state["so7_result"] = so7_engine.optimize_so7(gw_scores)
            st.session_state["so7_scores"] = gw_scores
            st.session_state["so7_start"]  = so7_start
            st.session_state["so7_end"]    = so7_end

    # ─── Affichage du résultat ─────────────────────────────────────────────────
    st.markdown("---")

    if "so7_result" not in st.session_state or st.session_state["so7_result"] is None:
        if db.get_roster():
            st.info("👆 Configure la période et clique sur **Calculer la meilleure So7**.")
        else:
            st.warning("Roster vide — ajoute des joueurs dans la sidebar.")
    else:
        result    = st.session_state["so7_result"]
        gw_scores = st.session_state["so7_scores"]
        gw_s_disp = st.session_state["so7_start"]
        gw_e_disp = st.session_state["so7_end"]

        lineup = result["lineup"]
        total  = result["total"]
        bench  = result["bench"]

        # ── Métriques ──────────────────────────────────────────────────────────
        best_player = max(lineup.values(), key=lambda p: p["total_gw"])
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🏆 Score équipe So7", f"{total:.1f} pts")
        m2.metric("📅 Période",
                  f"{gw_s_disp.strftime('%d/%m')} → {gw_e_disp.strftime('%d/%m')}")
        m3.metric("⭐ MVP", f"{best_player['name']} ({best_player['total_gw']:.1f})")
        m4.metric("🎮 Matchs joués",
                  sum(p["games_played"] for p in lineup.values()))

        st.markdown("---")

        # ── Lineup So7 ─────────────────────────────────────────────────────────
        st.markdown("### 🏟️ Meilleure lineup So7")

        # CSS spécifique So7
        st.markdown("""
        <style>
        .so7-slot {
            background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 14px 18px;
            margin-bottom: 10px;
        }
        .so7-slot-label {
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            color: #8b949e;
            text-transform: uppercase;
            margin-bottom: 2px;
        }
        .so7-player-name { font-size: 1.1rem; font-weight: 700; color: #e6edf3; }
        .so7-player-sub  { font-size: 0.82rem; color: #8b949e; }
        .so7-score       { font-size: 1.6rem; font-weight: 800; }
        .so7-score-pos   { color: #3fb950; }
        .so7-score-neg   { color: #f85149; }
        .slot-sp   { border-left: 3px solid #388bfd; }
        .slot-rp   { border-left: 3px solid #79c0ff; }
        .slot-cmi  { border-left: 3px solid #d2a8ff; }
        .slot-ci   { border-left: 3px solid #f0883e; }
        .slot-of   { border-left: 3px solid #3fb950; }
        .slot-xh   { border-left: 3px solid #ffa657; }
        .slot-flex { border-left: 3px solid #ff7b72; }
        </style>
        """, unsafe_allow_html=True)

        slot_css = {
            "SP": "slot-sp", "RP": "slot-rp", "C_MI": "slot-cmi",
            "CI": "slot-ci", "OF": "slot-of", "XH": "slot-xh", "FLEX": "slot-flex",
        }

        # Affichage en 2 colonnes : pitchers | hitters
        col_pitch, col_hit = st.columns(2)

        for slot in so7_engine.SO7_SLOTS:
            if slot not in lineup:
                continue
            player = lineup[slot]
            label  = so7_engine.SLOT_LABELS[slot]
            sc     = player["total_gw"]
            sc_cls = "so7-score-pos" if sc >= 0 else "so7-score-neg"
            css    = slot_css.get(slot, "")
            gp     = player["games_played"]

            # Détail des scores jour par jour
            days_str = "  ".join(
                f"`{d[-5:]}` **{v:+.0f}**" if v is not None else f"`{d[-5:]}` —"
                for d, v in sorted(player["days"].items())
            )

            html = f"""
            <div class="so7-slot {css}">
              <div class="so7-slot-label">{label}</div>
              <div class="so7-player-name">{player['name']}</div>
              <div class="so7-player-sub">{player['team']} · {player['position']} · {gp} match(s)</div>
            </div>
            """

            target_col = col_pitch if slot in ("SP", "RP") else col_hit
            with target_col:
                st.markdown(html, unsafe_allow_html=True)
                c_score, c_days = st.columns([1, 3])
                c_score.markdown(
                    f"<div class='so7-score {sc_cls}'>{sc:+.1f}</div>",
                    unsafe_allow_html=True
                )
                c_days.markdown(days_str)

        # ── Récap tableau ──────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📊 Récapitulatif complet du roster")

        # Construire toutes les dates de la GW
        nb_d = (gw_e_disp - gw_s_disp).days + 1
        all_dates = [(gw_s_disp + datetime.timedelta(days=i)).isoformat()
                     for i in range(nb_d)]

        rows_recap = []
        used_in_lineup = {lineup[s]["player_id"] for s in lineup}

        for p in gw_scores:
            slot_used = next(
                (so7_engine.SLOT_LABELS[s] for s in lineup if lineup[s]["player_id"] == p["player_id"]),
                "— Banc"
            )
            row = {
                "Joueur":   p["name"],
                "Pos":      p["position"],
                "Slot So7": slot_used,
                "Total GW": p["total_gw"],
                "Matchs":   p["games_played"],
            }
            for d in all_dates:
                row[d[5:]] = p["days"].get(d)   # format MM-DD
            rows_recap.append(row)

        df_recap = pd.DataFrame(rows_recap).sort_values("Total GW", ascending=False)

        date_cols = [d[5:] for d in all_dates]

        def color_slot(val):
            if val == "— Banc":
                return "color: #8b949e"
            return "color: #3fb950; font-weight: 600"

        def color_score(val):
            if pd.isna(val):
                return "color: #8b949e"
            if val >= 20:
                return "background-color: #1a7f37; color: white"
            if val >= 10:
                return "background-color: #196c2e; color: #7ee787"
            if val > 0:
                return "color: #7ee787"
            if val < 0:
                return "background-color: #6e1c1c; color: #ff7b72"
            return "color: #8b949e"

        styled = (
            df_recap.style
            .format("{:.1f}", subset=["Total GW"] + date_cols, na_rep="—")
            .applymap(color_score, subset=date_cols)
            .applymap(color_slot, subset=["Slot So7"])
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # ── Bench ──────────────────────────────────────────────────────────────
        if bench:
            with st.expander(f"🪑 Banc ({len(bench)} joueur(s) non sélectionnés)"):
                for p in bench:
                    reason = ""
                    eligible = p["eligible_slots"]
                    # Chercher quel slot ils auraient pu occuper
                    blocked = [s for s in eligible if s in lineup and lineup[s]["total_gw"] >= p["total_gw"]]
                    if blocked:
                        reason = f"→ Score inférieur au titulaire en {', '.join(so7_engine.SLOT_LABELS[s] for s in blocked)}"
                    st.markdown(
                        f"**{p['name']}** `{p['position']}` — **{p['total_gw']:+.1f} pts** "
                        f"({p['games_played']} matchs)  {reason}"
                    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Synchronisation manuelle avancée
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
