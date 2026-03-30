"""
main.py — Sorare MLB Scoreboard
Timezone : Europe/Paris
Synchro : un seul bouton, scheduler auto toutes les heures, zéro rerun intempestif.
"""

import streamlit as st
import datetime
import pandas as pd
import logging
import zoneinfo

import db
import sync
import gameweek as gw_module
import iopp as iopp_module
import so7 as so7_engine
from mlb_fetcher import search_player, get_player_headshot_url

TZ = zoneinfo.ZoneInfo("Europe/Paris")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

st.set_page_config(
    page_title="Sorare MLB", page_icon="⚾",
    layout="wide", initial_sidebar_state="expanded"
)

db.init_db()
sync.start_scheduler()

def _today() -> datetime.date:
    return datetime.datetime.now(tz=TZ).date()


# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background:#0d1117; }

/* GW Banner */
.gw-banner {
    background:linear-gradient(135deg,#161b22,#1c2128);
    border:1px solid #30363d; border-radius:10px;
    padding:12px 18px; margin-bottom:14px;
    display:flex; align-items:center; gap:16px; flex-wrap:wrap;
}
.gw-title { font-size:.95rem; font-weight:700; color:#e6edf3; }
.gw-dates { font-size:.75rem; color:#8b949e; }
.gw-score { font-size:1.5rem; font-weight:900; }
.gw-score-label { font-size:.6rem; color:#8b949e; text-transform:uppercase; letter-spacing:.05em; }
.gw-pill { background:#21262d; color:#79c0ff; border-radius:5px;
           padding:2px 8px; font-size:.68rem; font-weight:700; }

/* Cartes joueurs */
.player-card {
    background:linear-gradient(180deg,#1c2128,#161b22);
    border:2px solid #30363d; border-radius:12px;
    overflow:hidden; text-align:center;
    transition:border-color .2s;
}
.player-card:hover { border-color:#388bfd; }
.player-card.rank-1 { border-color:#f1c40f; box-shadow:0 0 12px #f1c40f33; }
.player-card.rank-2 { border-color:#95a5a6; }
.player-card.rank-3 { border-color:#cd7f32; }
.card-header { background:linear-gradient(135deg,#0d1117,#21262d);
    padding:3px 8px; display:flex; justify-content:space-between; align-items:center; }
.card-pos { font-size:.62rem; font-weight:700; color:#8b949e; }
.card-rank { font-size:.68rem; font-weight:800; color:#f1c40f; }
.card-img-wrapper { background:linear-gradient(180deg,#21262d,#161b22);
    padding:6px 3px 0; display:flex; align-items:flex-end; justify-content:center; height:95px; }
.card-img-wrapper img { width:80px; height:85px;
    object-fit:cover; object-position:top; border-radius:4px 4px 0 0; }
.card-name { font-size:.72rem; font-weight:700; color:#e6edf3;
    padding:4px 5px 1px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.card-team { font-size:.6rem; color:#8b949e; padding:0 5px 3px; }
.card-score-strip { background:#0a0e14; border-top:1px solid #30363d; padding:4px 3px; }
.card-score-main { font-size:1.1rem; font-weight:900; line-height:1; }
.card-score-gw { font-size:.6rem; color:#79c0ff; font-weight:700; margin-top:1px; }
.card-score-dns { font-size:.72rem; color:#8b949e; padding:3px 0; }
.score-pos { color:#3fb950; } .score-neg { color:#f85149; }

/* Badges */
.badge { display:inline-block; padding:1px 5px; border-radius:8px;
         font-size:.6rem; font-weight:700; }
.badge-hitter { background:#1f6feb; color:#fff; }
.badge-pitcher { background:#21262d; color:#388bfd; border:1px solid #388bfd; }

/* Pills historique */
.day-pills { display:flex; justify-content:center; gap:2px; flex-wrap:wrap;
             padding:2px 3px 4px; }
.day-pill { font-size:.52rem; font-weight:700; padding:1px 3px;
            border-radius:3px; white-space:nowrap; }
.pill-pos { background:#196c2e; color:#7ee787; }
.pill-neg { background:#6e1c1c; color:#ff7b72; }
.pill-zero { background:#21262d; color:#8b949e; }

/* So7 slots */
.so7-slot { background:linear-gradient(135deg,#161b22,#1c2128);
    border:1px solid #30363d; border-radius:8px; padding:10px 14px; margin-bottom:8px; }
.so7-slot-label { font-size:.62rem; font-weight:700; letter-spacing:.08em;
    color:#8b949e; text-transform:uppercase; }
.so7-player-name { font-size:1rem; font-weight:700; color:#e6edf3; }
.so7-player-sub { font-size:.75rem; color:#8b949e; }
.so7-score { font-size:1.4rem; font-weight:800; }
.so7-score-pos { color:#3fb950; } .so7-score-neg { color:#f85149; }
.slot-sp  { border-left:3px solid #388bfd; } .slot-rp  { border-left:3px solid #79c0ff; }
.slot-cmi { border-left:3px solid #d2a8ff; } .slot-ci  { border-left:3px solid #f0883e; }
.slot-of  { border-left:3px solid #3fb950; } .slot-xh  { border-left:3px solid #ffa657; }
.slot-flex{ border-left:3px solid #ff7b72; }

/* IOPP */
.iopp-card { background:#161b22; border:1px solid #30363d; border-radius:10px;
    padding:12px 16px; margin-bottom:8px; }
.iopp-bar-bg { background:#21262d; border-radius:4px; height:8px; margin:6px 0; overflow:hidden; }
.iopp-bar-fill { height:100%; border-radius:4px; }

/* Synchro status */
.sync-status {
    background:#161b22; border:1px solid #30363d; border-radius:8px;
    padding:10px 16px; font-size:.8rem; color:#8b949e;
    display:flex; align-items:center; gap:10px;
}
</style>
""", unsafe_allow_html=True)


# ─── Fonction synchro unifiée ─────────────────────────────────────────────────
def run_full_sync(force: bool = False) -> dict:
    """
    Synchro complète : aujourd'hui + tous les jours de la GW en cours.
    Retourne un résumé de ce qui a été fait.
    """
    today   = _today()
    cur_gw  = gw_module.current_gw()
    gw_end  = datetime.date.fromisoformat(cur_gw["end_date"])
    gw_start= datetime.date.fromisoformat(cur_gw["start_date"])

    dates_to_sync = []
    # Tous les jours de la GW jusqu'à aujourd'hui
    d = gw_start
    while d <= min(today, gw_end):
        dates_to_sync.append(d)
        d += datetime.timedelta(days=1)
    # Ajouter hier si pas déjà inclus
    yesterday = today - datetime.timedelta(days=1)
    if yesterday not in dates_to_sync:
        dates_to_sync.append(yesterday)

    total_synced = 0
    total_dns    = 0
    total_errors = 0
    dates_done   = []

    for date in sorted(set(dates_to_sync)):
        if not force and db.is_date_synced(date.isoformat()):
            continue
        r = sync.sync_date(date, force=force)
        total_synced += r.get("synced", 0)
        total_dns    += r.get("no_game", 0)
        total_errors += r.get("errors", 0)
        if r.get("synced", 0) > 0 or r.get("no_game", 0) > 0:
            dates_done.append(date.isoformat())

    return {
        "synced":  total_synced,
        "dns":     total_dns,
        "errors":  total_errors,
        "dates":   dates_done,
    }


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚾ Sorare MLB")

    # GW en cours
    cur_gw = gw_module.current_gw()
    st.markdown(f"""
<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;
     padding:9px 14px;margin-bottom:10px;'>
  <div style='font-size:.58rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;'>GW EN COURS</div>
  <div style='font-size:.82rem;font-weight:700;color:#e6edf3;margin:2px 0;'>{cur_gw['label']}</div>
  <div style='font-size:.65rem;color:#79c0ff;'>⏱ {cur_gw['days_left']} jour(s) restant(s)</div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Bouton synchro UNIQUE ──────────────────────────────────────────────────
    st.subheader("🔄 Synchronisation")

    # Statut scheduler
    sched_ok = sync._scheduler and sync._scheduler.running
    if sched_ok:
        jobs = sync._scheduler.get_jobs()
        next_run = jobs[0].next_run_time.strftime("%H:%M") if jobs else "?"
        st.caption(f"✅ Auto toutes les heures · prochain : {next_run}")
    else:
        st.caption("⚠️ Scheduler inactif")

    force_resync = st.checkbox("Forcer le re-fetch", value=False,
                               help="Re-télécharge même les jours déjà synchro")

    if st.button("🔄 Synchroniser maintenant", use_container_width=True, type="primary"):
        with st.spinner("Synchro en cours…"):
            result = run_full_sync(force=force_resync)

        s = result["synced"]
        d_= result["dns"]
        e = result["errors"]
        dates = result["dates"]

        if e > 0:
            st.error(f"⚠️ {e} erreur(s)")
        elif s == 0 and d_ == 0 and not dates:
            st.info("✅ Tout est déjà à jour")
        else:
            st.success(f"✅ {s} score(s) · {d_} DNS")
            if dates:
                st.caption("Dates mises à jour : " + ", ".join(d[5:] for d in dates))

    st.markdown("---")

    # ── Roster ────────────────────────────────────────────────────────────────
    st.subheader("👥 Mon Roster")
    roster_sb = db.get_roster()
    if roster_sb:
        for p in roster_sb:
            c1, c2 = st.columns([3, 1])
            icon = "🥎" if p["role"] == "pitcher" else "🏏"
            c1.markdown(f"{icon} **{p['name']}** `{p['position']}`")
            if c2.button("✕", key=f"rm_{p['player_id']}"):
                db.remove_player(p["player_id"])
                st.rerun()
    else:
        st.info("Roster vide.")

    st.markdown("---")

    # ── Recherche ────────────────────────────────────────────────────────────
    st.subheader("➕ Ajouter un joueur")
    q = st.text_input("Nom", placeholder="ex: Shohei Ohtani")
    if q and len(q) >= 3:
        with st.spinner("Recherche…"):
            try:
                res = search_player(q)
                for r in res[:5]:
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"**{r['name']}** — {r['team']} `{r['position']}`")
                    rg = "pitcher" if r["position"] in ("SP","RP","P","CL") else "hitter"
                    if c2.button("＋", key=f"add_{r['id']}"):
                        db.add_player(r["id"], r["name"], r["team"], r["position"], rg)
                        st.success(f"{r['name']} ajouté !")
                        st.rerun()
                if not res:
                    st.warning("Aucun joueur trouvé.")
            except Exception as e:
                st.error(str(e))


# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_scores, tab_history, tab_iopp, tab_so7 = st.tabs(
    ["📊 Scores du jour", "📅 Historique", "📈 IOPP", "🏆 Best So7"]
)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Scores du jour
# ══════════════════════════════════════════════════════════════════════════════
with tab_scores:
    today     = _today()
    cur_gw    = gw_module.current_gw()
    gw_start  = datetime.date.fromisoformat(cur_gw["start_date"])
    gw_end    = datetime.date.fromisoformat(cur_gw["end_date"])

    selected_date = st.date_input(
        "Date", value=today, max_value=today, key="score_date"
    )
    date_str = selected_date.isoformat()

    # Synchro auto silencieuse si données manquantes (sans rerun)
    if not db.is_date_synced(date_str) and db.get_roster():
        with st.spinner(f"⏳ Synchro automatique {date_str}…"):
            sync.sync_date(selected_date, force=False)

    # Banner GW
    gw_days_done = max(0, (min(today, gw_end) - gw_start).days + 1)
    days_total   = (gw_end - gw_start).days + 1

    gw_total_by_player: dict[int, float] = {}
    for p in db.get_roster():
        pid = p["player_id"]
        sc_list = db.get_scores_range(
            pid, cur_gw["start_date"], min(today, gw_end).isoformat()
        )
        gw_total_by_player[pid] = round(
            sum(s["total"] for s in sc_list if s.get("total") is not None), 2
        )
    gw_team_total = sum(gw_total_by_player.values())

    st.markdown(f"""
<div class="gw-banner">
  <div>
    <div class="gw-score-label">Gameweek en cours</div>
    <div class="gw-title">{cur_gw['label']}</div>
    <div class="gw-dates">{gw_start.strftime('%d/%m')} → {gw_end.strftime('%d/%m/%Y')}</div>
  </div>
  <div style="flex:1"></div>
  <div style="text-align:right">
    <div class="gw-score-label">Score GW équipe</div>
    <div class="gw-score {'score-pos' if gw_team_total>=0 else 'score-neg'}">{gw_team_total:+.1f} pts</div>
    <div class="gw-pill">J{gw_days_done}/{days_total} · {cur_gw['days_left']} restant(s)</div>
  </div>
</div>""", unsafe_allow_html=True)

    scores = db.get_scores_for_date(date_str)
    if not scores:
        if not db.get_roster():
            st.warning("Roster vide — ajoute des joueurs dans la sidebar.")
        else:
            st.info(f"Aucune donnée pour le {date_str}. Clique sur **Synchroniser maintenant** dans la sidebar.")
    else:
        valid    = [s for s in scores if s["total"] is not None]
        no_games = [s for s in scores if s["total"] is None]

        if valid:
            td   = sum(s["total"] for s in valid)
            best = max(valid, key=lambda x: x["total"])
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("🏆 Score du jour", f"{td:.1f}")
            m2.metric("📊 Moy/joueur",    f"{td/len(valid):.1f}")
            m3.metric("⭐ Meilleur",       f"{best['player_name']} ({best['total']:.1f})")
            m4.metric("👥 Actifs",         f"{len(valid)}/{len(scores)}")

        st.markdown("---")

        # Historique 7j pour les pills
        hist_start  = (selected_date - datetime.timedelta(days=6)).isoformat()
        all_hist    = {
            s["player_id"]: db.get_scores_range(s["player_id"], hist_start, date_str)
            for s in scores
        }

        sorted_scores = sorted(valid, key=lambda x: x["total"], reverse=True) + no_games
        COLS = 5
        for row_chunk in [sorted_scores[i:i+COLS] for i in range(0, len(sorted_scores), COLS)]:
            cols = st.columns(COLS)
            for col, s in zip(cols, row_chunk):
                pid   = s["player_id"]
                name  = s.get("player_name", "?")
                pos   = s.get("position", "?")
                team  = s.get("team", "")
                role  = s.get("role", "hitter")
                total = s.get("total")
                rank  = sorted_scores.index(s) + 1

                rank_css, rank_lbl = "", ""
                if total is not None:
                    if rank == 1: rank_css, rank_lbl = "rank-1", "🥇"
                    elif rank == 2: rank_css, rank_lbl = "rank-2", "🥈"
                    elif rank == 3: rank_css, rank_lbl = "rank-3", "🥉"

                if total is None:
                    score_html = '<div class="card-score-dns">DNS</div>'
                else:
                    sc_c = "score-pos" if total >= 0 else "score-neg"
                    score_html = f'<div class="card-score-main {sc_c}">{total:+.1f}</div>'

                gw_val  = gw_total_by_player.get(pid, 0.0)
                gw_html = f'<div class="card-score-gw">GW {gw_val:+.1f}</div>' if gw_val else ""

                hist  = sorted(all_hist.get(pid, []), key=lambda x: x["date"])
                pills = ""
                for h in hist:
                    v = h.get("total"); lbl = h["date"][5:]
                    if v is None:  pills += f'<span class="day-pill pill-zero">{lbl}</span>'
                    elif v >= 0:   pills += f'<span class="day-pill pill-pos">{lbl} {v:+.0f}</span>'
                    else:          pills += f'<span class="day-pill pill-neg">{lbl} {v:+.0f}</span>'

                img = get_player_headshot_url(pid)
                bc  = "badge-pitcher" if role == "pitcher" else "badge-hitter"
                bl  = "P" if role == "pitcher" else "H"
                first_name = name.split(" ")[0]

                with col:
                    st.markdown(f"""
<div class="player-card {rank_css}">
  <div class="card-header">
    <span class="card-pos">{pos} <span class="badge {bc}">{bl}</span></span>
    <span class="card-rank">{rank_lbl}</span>
  </div>
  <div class="card-img-wrapper">
    <img src="{img}" alt="{name}"
     onerror="this.src='https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/0/headshot/67/current'"/>
  </div>
  <div class="card-name" title="{name}">{first_name}</div>
  <div class="card-team">{team}</div>
  <div class="card-score-strip">{score_html}{gw_html}</div>
  <div class="day-pills">{pills}</div>
</div>""", unsafe_allow_html=True)

                    bd = s.get("breakdown", {})
                    if bd:
                        with st.expander("Détail", expanded=False):
                            st.dataframe(
                                pd.DataFrame([{"Action": k, "Pts": v}
                                              for k, v in bd.items()])
                                  .sort_values("Pts", ascending=False),
                                hide_index=True, use_container_width=True)

        if no_games:
            st.caption("⚫ DNS : " + " · ".join(s["player_name"] for s in no_games))


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Historique
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("📅 Historique")
    roster = db.get_roster()
    if not roster:
        st.info("Roster vide.")
    else:
        avail = db.get_all_dates_with_scores()
        if not avail:
            st.info("Aucune donnée. Lance une synchronisation depuis la sidebar.")
        else:
            cur  = gw_module.current_gw()
            prev = gw_module.previous_gw()
            presets = {
                f"GW en cours ({cur['label']})":    (cur["start_date"],  cur["end_date"]),
                f"GW précédente ({prev['label']})": (prev["start_date"], prev["end_date"]),
                "Personnalisé": None,
            }
            pk = st.selectbox("Période", list(presets.keys()))
            pv = presets[pk]
            if pv:
                hs = datetime.date.fromisoformat(pv[0])
                he = datetime.date.fromisoformat(pv[1])
                st.info(f"📅 {hs} → {he}")
            else:
                max_d = datetime.date.fromisoformat(avail[0])
                min_d = datetime.date.fromisoformat(avail[-1])
                c1, c2 = st.columns(2)
                hs = c1.date_input("Du", value=min_d, min_value=min_d, max_value=max_d, key="hs2")
                he = c2.date_input("Au", value=max_d, min_value=min_d, max_value=max_d, key="he2")

            rows_h = []
            for p in roster:
                for sc in db.get_scores_range(p["player_id"], hs.isoformat(), he.isoformat()):
                    rows_h.append({"Joueur": p["name"], "Date": sc["date"], "Score": sc["total"]})

            if rows_h:
                df_h = pd.DataFrame(rows_h)
                piv  = df_h.pivot_table(index="Joueur", columns="Date", values="Score", aggfunc="first")
                piv["TOTAL"] = piv.sum(axis=1, skipna=True)
                piv["MOY"]   = piv.drop(columns=["TOTAL"]).mean(axis=1, skipna=True).round(1)
                piv = piv.sort_values("TOTAL", ascending=False)
                dc  = [c for c in piv.columns if c not in ("TOTAL", "MOY")]

                def _cs(v):
                    if pd.isna(v): return "color:#8b949e"
                    if v > 30: return "background-color:#1a7f37;color:white"
                    if v > 15: return "background-color:#196c2e;color:#7ee787"
                    if v >  0: return "color:#7ee787"
                    if v <  0: return "background-color:#6e1c1c;color:#ff7b72"
                    return "color:#8b949e"

                st.dataframe(
                    piv.style.format("{:.1f}", na_rep="DNS")
                              .applymap(_cs, subset=pd.IndexSlice[:, dc])
                              .format("{:.1f}", subset=["TOTAL","MOY"]),
                    use_container_width=True)

                st.markdown("---")
                sel = st.selectbox("Zoom joueur", df_h["Joueur"].unique())
                df_z = df_h[df_h["Joueur"] == sel].set_index("Date")["Score"].dropna()
                if not df_z.empty:
                    st.bar_chart(df_z, use_container_width=True)
            else:
                st.info("Aucun score sur cette période.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — IOPP
# ══════════════════════════════════════════════════════════════════════════════
with tab_iopp:
    st.subheader("📈 IOPP — Index de Performance")
    st.caption(
        "**L15 2026** = moyenne des 15 derniers matchs joués. "
        "**Moy 2025** = score moyen recalculé depuis les stats MLB 2025. "
        "Seuil ±15% → 🔥 Surperformance / ❄️ Sous-performance."
    )
    roster = db.get_roster()
    if not roster:
        st.warning("Roster vide.")
    else:
        if st.button("🔄 Calculer l'IOPP", type="primary"):
            with st.spinner("Calcul IOPP…"):
                ioppd = iopp_module.compute_roster_iopp(roster)
            st.session_state["iopp_data"] = ioppd

        if "iopp_data" not in st.session_state:
            st.info("Clique sur **Calculer l'IOPP**.")
        else:
            ioppd = st.session_state["iopp_data"]
            surperf = [p for p in roster if (ioppd.get(p["player_id"],{}).get("pct") or 0) >= 15]
            sousp   = [p for p in roster if (ioppd.get(p["player_id"],{}).get("pct") or 0) <= -15]
            m1, m2, m3 = st.columns(3)
            m1.metric("🔥 Surperformance", len(surperf))
            m2.metric("➡️ Dans la norme",  len(roster) - len(surperf) - len(sousp))
            m3.metric("❄️ Sous-performance", len(sousp))
            st.markdown("---")

            def _sk(p):
                return -(ioppd.get(p["player_id"], {}).get("pct") or 0)
            sorted_r = sorted(roster, key=_sk)

            for row_r in [sorted_r[i:i+3] for i in range(0, len(sorted_r), 3)]:
                cols_i = st.columns(3)
                for col_i, p in zip(cols_i, row_r):
                    pid  = p["player_id"]
                    ip   = ioppd.get(pid, {})
                    l15  = ip.get("l15_avg")
                    a25  = ip.get("avg_2025")
                    pct  = ip.get("pct")
                    delta= ip.get("delta")
                    sta  = ip.get("status", "❓")
                    scol = ip.get("status_color", "#8b949e")
                    g15  = ip.get("l15_games", 0)
                    g25  = ip.get("games_2025", 0)
                    img  = get_player_headshot_url(pid)
                    bc2  = "badge-pitcher" if p["role"] == "pitcher" else "badge-hitter"
                    bl2  = "P" if p["role"] == "pitcher" else "H"
                    bar_pct = int(min(max(l15/a25, 0), 2)/2*100) if (l15 and a25 and a25>0) else 50

                    with col_i:
                        st.markdown(f"""
<div class="iopp-card">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
    <img src="{img}" style="width:44px;height:40px;object-fit:cover;object-position:top;border-radius:5px;"
     onerror="this.style.display='none'"/>
    <div>
      <div style="font-weight:700;color:#e6edf3;font-size:.88rem;">{p['name']}</div>
      <div style="font-size:.68rem;color:#8b949e;">{p['position']} <span class="badge {bc2}">{bl2}</span></div>
    </div>
    <div style="margin-left:auto;font-size:1rem;">{sta}</div>
  </div>
  <div class="iopp-bar-bg">
    <div class="iopp-bar-fill" style="width:{bar_pct}%;background:{scol};"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:.7rem;margin-top:4px;gap:4px;">
    <div>
      <div style="color:#8b949e;">L{g15} 2026</div>
      <div style="color:#e6edf3;font-weight:700;font-size:.95rem;">
        {f"{l15:+.1f}" if l15 is not None else "—"}</div>
    </div>
    <div style="text-align:center;">
      <div style="color:#8b949e;">Δ vs 2025</div>
      <div style="color:{scol};font-weight:700;font-size:.95rem;">
        {f"{delta:+.1f} ({pct:+.0f}%)" if delta is not None else "—"}</div>
    </div>
    <div style="text-align:right;">
      <div style="color:#8b949e;">Moy 2025 ({g25}G)</div>
      <div style="color:#e6edf3;font-weight:700;font-size:.95rem;">
        {f"{a25:.1f}" if a25 else "—"}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

            st.markdown("---")
            rows_io = [{"Joueur": p["name"], "Pos": p["position"],
                        "L15 2026": ioppd.get(p["player_id"],{}).get("l15_avg"),
                        "Moy 2025": ioppd.get(p["player_id"],{}).get("avg_2025"),
                        "Δ":        ioppd.get(p["player_id"],{}).get("delta"),
                        "Δ%":       ioppd.get(p["player_id"],{}).get("pct"),
                        "Statut":   ioppd.get(p["player_id"],{}).get("status","—")}
                       for p in sorted_r]
            df_io = pd.DataFrame(rows_io)

            def _cp(v):
                if pd.isna(v): return "color:#8b949e"
                if v >= 15: return "color:#3fb950;font-weight:700"
                if v <= -15: return "color:#f85149;font-weight:700"
                return "color:#8b949e"

            st.dataframe(
                df_io.style
                     .format("{:.1f}", subset=["L15 2026","Moy 2025","Δ"], na_rep="—")
                     .format("{:.0f}%", subset=["Δ%"], na_rep="—")
                     .applymap(_cp, subset=["Δ%"]),
                hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Best So7
# ══════════════════════════════════════════════════════════════════════════════
with tab_so7:
    st.subheader("🏆 Meilleure So7")
    st.caption("Calcule la meilleure lineup So7 possible sur la gameweek choisie.")

    col_l, col_r = st.columns([2, 1])

    with col_r:
        st.markdown("**📁 Sauvegarder une GW**")
        gw_lbl = st.text_input("Nom", placeholder="ex: GW Midweek mars", key="gw_lbl")
        gw_s_  = st.date_input("Début", key="gw_s", value=_today()-datetime.timedelta(days=6))
        gw_e_  = st.date_input("Fin",   key="gw_e", value=_today()-datetime.timedelta(days=3))
        if st.button("💾 Sauvegarder", use_container_width=True):
            if gw_lbl:
                db.save_gameweek(gw_lbl, gw_s_.isoformat(), gw_e_.isoformat())
                st.success("Sauvegardée !")
                st.rerun()
        saved = db.get_gameweeks()
        if saved:
            st.markdown("**📋 Sauvegardées**")
            for g in saved:
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{g['label']}**  \n`{g['start_date']}` → `{g['end_date']}`")
                if c2.button("🗑", key=f"del_{g['id']}"):
                    db.delete_gameweek(g["id"])
                    st.rerun()

    with col_l:
        st.markdown("**📅 Choisir la période**")
        cur2   = gw_module.current_gw()
        prev2  = gw_module.previous_gw()
        saved2 = db.get_gameweeks()
        opts: dict = {
            f"✅ GW en cours — {cur2['label']}":    (cur2["start_date"],  cur2["end_date"]),
            f"⬅️ GW précédente — {prev2['label']}": (prev2["start_date"], prev2["end_date"]),
        }
        for g in saved2:
            opts[f"📁 {g['label']}"] = (g["start_date"], g["end_date"])
        opts["📆 Période manuelle"] = None

        ck = st.selectbox("Gameweek", list(opts.keys()))
        ch = opts[ck]
        if ch:
            so7_start = datetime.date.fromisoformat(ch[0])
            so7_end   = datetime.date.fromisoformat(ch[1])
            st.info(f"📅 {so7_start.strftime('%d/%m')} → {so7_end.strftime('%d/%m/%Y')}")
        else:
            so7_start = st.date_input("Début", key="so7_s2",
                                      value=_today()-datetime.timedelta(days=5))
            so7_end   = st.date_input("Fin",   key="so7_e2",
                                      value=_today()-datetime.timedelta(days=1))

        nb_d7 = (so7_end - so7_start).days + 1
        st.caption(f"{nb_d7} jour(s) : " +
                   " · ".join((so7_start+datetime.timedelta(days=i)).strftime("%d/%m")
                               for i in range(nb_d7)))

        if st.button("🚀 Calculer la meilleure So7", type="primary", use_container_width=True):
            with st.spinner("Calcul So7…"):
                gw_sc2 = so7_engine.compute_gameweek_scores(
                    so7_start.isoformat(), so7_end.isoformat())
                st.session_state["so7_result"] = so7_engine.optimize_so7(gw_sc2)
                st.session_state["so7_scores"] = gw_sc2
                st.session_state["so7_start"]  = so7_start
                st.session_state["so7_end"]    = so7_end

    st.markdown("---")

    if "so7_result" not in st.session_state or st.session_state["so7_result"] is None:
        st.info("Configure la période et clique sur **Calculer la meilleure So7**.")
    else:
        result2 = st.session_state["so7_result"]
        gw_sc2  = st.session_state["so7_scores"]
        gw_s2   = st.session_state["so7_start"]
        gw_e2   = st.session_state["so7_end"]
        lineup2 = result2["lineup"]
        total2  = result2["total"]
        bench2  = result2["bench"]
        best2   = max(lineup2.values(), key=lambda x: x["total_gw"])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🏆 Score So7", f"{total2:.1f} pts")
        m2.metric("📅 Période", f"{gw_s2.strftime('%d/%m')} → {gw_e2.strftime('%d/%m')}")
        m3.metric("⭐ MVP", f"{best2['name']} ({best2['total_gw']:.1f})")
        m4.metric("🎮 Matchs", sum(p["games_played"] for p in lineup2.values()))

        st.markdown("---")
        st.markdown("### 🏟️ Lineup So7")
        scm = {"SP":"slot-sp","RP":"slot-rp","C_MI":"slot-cmi",
               "CI":"slot-ci","OF":"slot-of","XH":"slot-xh","FLEX":"slot-flex"}
        cp2, ch2 = st.columns(2)

        for slot in so7_engine.SO7_SLOTS:
            if slot not in lineup2: continue
            pl2  = lineup2[slot]
            lbl2 = so7_engine.SLOT_LABELS[slot]
            sc2  = pl2["total_gw"]
            sc2c = "so7-score-pos" if sc2 >= 0 else "so7-score-neg"
            ds2  = "  ".join(
                f"`{d[-5:]}` **{v:+.0f}**" if v is not None else f"`{d[-5:]}` —"
                for d, v in sorted(pl2["days"].items()))

            tgt = cp2 if slot in ("SP","RP") else ch2
            with tgt:
                st.markdown(f"""
<div class="so7-slot {scm.get(slot,'')}">
  <div class="so7-slot-label">{lbl2}</div>
  <div class="so7-player-name">{pl2['name']}</div>
  <div class="so7-player-sub">{pl2['team']} · {pl2['position']} · {pl2['games_played']} match(s)</div>
</div>""", unsafe_allow_html=True)
                cx, cy = st.columns([1, 3])
                cx.markdown(f"<div class='so7-score {sc2c}'>{sc2:+.1f}</div>",
                            unsafe_allow_html=True)
                cy.markdown(ds2)

        st.markdown("---")
        st.markdown("### 📊 Récapitulatif")
        nd2 = (gw_e2 - gw_s2).days + 1
        ad2 = [(gw_s2 + datetime.timedelta(days=i)).isoformat() for i in range(nd2)]
        rr2 = []
        for pp2 in gw_sc2:
            su2 = next((so7_engine.SLOT_LABELS[s] for s in lineup2
                        if lineup2[s]["player_id"] == pp2["player_id"]), "— Banc")
            rw2 = {"Joueur": pp2["name"], "Pos": pp2["position"], "Slot": su2,
                   "Total GW": pp2["total_gw"], "Matchs": pp2["games_played"]}
            for d2 in ad2:
                rw2[d2[5:]] = pp2["days"].get(d2)
            rr2.append(rw2)

        df2  = pd.DataFrame(rr2).sort_values("Total GW", ascending=False)
        dc2  = [d[5:] for d in ad2]

        def _cs2(v):
            if pd.isna(v): return "color:#8b949e"
            if v >= 20: return "background-color:#1a7f37;color:white"
            if v >= 10: return "background-color:#196c2e;color:#7ee787"
            if v >  0:  return "color:#7ee787"
            if v <  0:  return "background-color:#6e1c1c;color:#ff7b72"
            return "color:#8b949e"

        st.dataframe(
            df2.style.format("{:.1f}", subset=["Total GW"] + dc2, na_rep="—")
                     .applymap(_cs2, subset=dc2),
            use_container_width=True, hide_index=True)

        if bench2:
            with st.expander(f"🪑 Banc ({len(bench2)} joueur(s))"):
                for pb3 in bench2:
                    bl3 = [s for s in pb3["eligible_slots"]
                           if s in lineup2 and lineup2[s]["total_gw"] >= pb3["total_gw"]]
                    rz  = (f"→ Score < titulaire : "
                           f"{', '.join(so7_engine.SLOT_LABELS[s] for s in bl3)}"
                           if bl3 else "")
                    st.markdown(f"**{pb3['name']}** `{pb3['position']}` "
                                f"— **{pb3['total_gw']:+.1f} pts** "
                                f"({pb3['games_played']}G) {rz}")
