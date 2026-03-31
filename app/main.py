"""
Sorare MLB Scoreboard — v2
Architecture : Streamlit multi-pages, Europe/Paris, synchro auto toutes les heures.
"""

import streamlit as st
import datetime, zoneinfo, logging, pandas as pd

import db, sync, gameweek as gw, so7 as so7_mod, iopp as iopp_mod
from mlb_fetcher import search_player, get_player_headshot_url

TZ = zoneinfo.ZoneInfo("Europe/Paris")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ── Init ──────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Sorare MLB", page_icon="⚾",
                   layout="wide", initial_sidebar_state="expanded")
db.init_db()
sync.start_scheduler()

def today() -> datetime.date:
    return datetime.datetime.now(tz=TZ).date()

def fmt_date(d: datetime.date) -> str:
    MOIS = ["jan","fév","mar","avr","mai","juin","juil","août","sep","oct","nov","déc"]
    return f"{d.day} {MOIS[d.month-1]}"

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #0d1117; }
.block-container { padding-top: 1rem; }

/* Cartes joueurs */
.pcard {
  background: #161b22; border: 2px solid #30363d;
  border-radius: 10px; overflow: hidden;
  text-align: center; transition: border-color .15s;
}
.pcard:hover { border-color: #388bfd; }
.pcard.r1 { border-color: #f1c40f; box-shadow: 0 0 10px #f1c40f33; }
.pcard.r2 { border-color: #95a5a6; }
.pcard.r3 { border-color: #cd7f32; }
.pcard.pitcher-card { border-color: #388bfd44; }
.pcard.dns { opacity: .5; }

.pc-header { background: #0d1117; padding: 3px 7px;
  display: flex; justify-content: space-between; align-items: center; }
.pc-pos { font-size: .58rem; font-weight: 700; color: #8b949e; }
.pc-rank { font-size: .62rem; font-weight: 800; color: #f1c40f; }

.pc-photo { background: linear-gradient(180deg,#1a2030,#111820);
  display: flex; align-items: flex-end; justify-content: center;
  height: 80px; overflow: hidden; padding: 4px 2px 0; }
.pc-photo img { width: 70px; height: 72px; object-fit: cover;
  object-position: top; border-radius: 4px 4px 0 0; }

.pc-name { font-size: .68rem; font-weight: 700; padding: 3px 4px 1px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.pc-score { background: #0a0e14; border-top: 1px solid #30363d;
  padding: 4px 3px 5px; }
.sc-val { font-size: 1.1rem; font-weight: 900; line-height: 1; }
.sc-pos { color: #3fb950; } .sc-neg { color: #f85149; }
.sc-dns { color: #8b949e; font-size: .72rem; }
.sc-gw  { font-size: .58rem; color: #79c0ff; font-weight: 700; margin-top: 1px; }

/* Séparateur hitter/pitcher */
.role-sep {
  display: flex; align-items: center; gap: 10px;
  margin: 14px 0 8px;
  font-size: .65rem; font-weight: 800; color: #8b949e;
  text-transform: uppercase; letter-spacing: .1em;
}
.role-sep::before, .role-sep::after {
  content: ''; flex: 1; height: 1px; background: #30363d;
}

/* GW Banner */
.gw-banner {
  background: linear-gradient(135deg,#161b22,#1c2128);
  border: 1px solid #30363d; border-radius: 10px;
  padding: 14px 20px; margin-bottom: 16px;
  display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
}
.gw-label { font-size: .58rem; font-weight: 700; color: #8b949e;
  text-transform: uppercase; letter-spacing: .07em; }
.gw-name  { font-size: 1rem; font-weight: 800; color: #e6edf3; }
.gw-dates { font-size: .72rem; color: #8b949e; }
.gw-score { font-size: 1.6rem; font-weight: 900; color: #3fb950; }
.gw-pill  { background: #21262d; color: #79c0ff; border-radius: 5px;
  padding: 2px 9px; font-size: .68rem; font-weight: 700; }

/* So7 slots */
.so7-row { display: grid; grid-template-columns: repeat(2,1fr); gap: 6px; margin-bottom: 4px; }
.so7-slot {
  background: #161b22; border: 1px solid #30363d;
  border-radius: 8px; padding: 8px 12px;
  display: flex; align-items: center; gap: 10px;
}
.so7-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.so7-label { font-size: .55rem; font-weight: 700; color: #8b949e;
  text-transform: uppercase; letter-spacing: .06em; }
.so7-name  { font-size: .85rem; font-weight: 700; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }
.so7-meta  { font-size: .6rem; color: #8b949e; }
.so7-sc    { font-size: 1rem; font-weight: 900; white-space: nowrap; margin-left: auto; }

/* IOPP */
.iopp-card {
  background: #161b22; border: 1px solid #30363d;
  border-radius: 10px; padding: 14px;
}
.iopp-bar-bg   { background: #21262d; border-radius: 4px; height: 8px;
  margin: 8px 0 6px; overflow: hidden; }
.iopp-bar-fill { height: 100%; border-radius: 4px; }

/* Pills historique */
.pills { display:flex; flex-wrap:wrap; gap:2px; justify-content:center;
  padding: 2px 3px 4px; }
.pill { font-size:.52rem; font-weight:700; padding:1px 3px;
  border-radius:3px; white-space:nowrap; }
.pill-pos { background:#196c2e; color:#7ee787; }
.pill-neg { background:#6e1c1c; color:#ff7b72; }
.pill-nil { background:#21262d; color:#8b949e; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚾ Sorare MLB")

    # GW courante
    cur = gw.current_gw()
    st.markdown(f"""
<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
  padding:9px 14px;margin-bottom:12px;">
  <div style="font-size:.55rem;color:#8b949e;text-transform:uppercase;
    letter-spacing:.07em;">GW EN COURS</div>
  <div style="font-size:.85rem;font-weight:700;color:#e6edf3;margin:2px 0;">
    {cur['label']}</div>
  <div style="font-size:.65rem;color:#79c0ff;">
    ⏱ {cur['days_left']} jour(s) restant(s)</div>
</div>""", unsafe_allow_html=True)

    # ── Synchro ────────────────────────────────────────────────────────────────
    st.subheader("🔄 Synchro")
    sched_ok = sync._scheduler and sync._scheduler.running
    if sched_ok:
        jobs = sync._scheduler.get_jobs()
        nxt  = jobs[0].next_run_time.strftime("%H:%M") if jobs else "?"
        st.caption(f"✅ Auto toutes les heures · prochain : {nxt} (Paris)")
    else:
        st.caption("⚠️ Scheduler inactif")

    force = st.checkbox("Forcer le re-fetch", value=False)
    if st.button("🔄 Synchroniser", use_container_width=True, type="primary"):
        # Synchro GW complète + aujourd'hui
        cur_gw_  = gw.current_gw()
        gw_start = datetime.date.fromisoformat(cur_gw_["start_date"])
        gw_end   = datetime.date.fromisoformat(cur_gw_["end_date"])
        dates    = []
        d = gw_start
        while d <= min(today(), gw_end):
            dates.append(d)
            d += datetime.timedelta(days=1)
        yest = today() - datetime.timedelta(days=1)
        if yest not in dates:
            dates.append(yest)

        synced = dns = errors = 0
        with st.spinner("Synchro…"):
            for date in sorted(set(dates)):
                if not force and db.is_date_synced(date.isoformat()):
                    continue
                r = sync.sync_date(date, force=force)
                synced += r.get("synced", 0)
                dns    += r.get("no_game", 0)
                errors += r.get("errors", 0)

        if errors:
            st.error(f"⚠️ {errors} erreur(s)")
        elif synced == 0 and dns == 0:
            st.info("✅ Déjà à jour")
        else:
            st.success(f"✅ {synced} score(s) · {dns} DNS")

    st.markdown("---")

    # ── Roster ────────────────────────────────────────────────────────────────
    st.subheader("👥 Roster")
    roster = db.get_roster()

    # Affichage séparé pitchers / hitters
    pitchers = [p for p in roster if p["role"] == "pitcher"]
    hitters  = [p for p in roster if p["role"] != "pitcher"]

    if pitchers:
        st.caption("🥎 Pitchers")
        for p in pitchers:
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{p['name']}** `{p['position']}`")
            if c2.button("✕", key=f"rm_{p['player_id']}"):
                db.remove_player(p["player_id"]); st.rerun()

    if hitters:
        st.caption("🏏 Hitters")
        for p in hitters:
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{p['name']}** `{p['position']}`")
            if c2.button("✕", key=f"rm_{p['player_id']}"):
                db.remove_player(p["player_id"]); st.rerun()

    if not roster:
        st.info("Roster vide.")

    st.markdown("---")
    st.subheader("➕ Ajouter")
    q = st.text_input("Nom", placeholder="ex: Shohei Ohtani", label_visibility="collapsed")
    if q and len(q) >= 3:
        with st.spinner("Recherche…"):
            try:
                res = search_player(q)
                for r in res[:5]:
                    c1, c2 = st.columns([3, 1])
                    role_g = "pitcher" if r["position"] in ("SP","RP","P","CL") else "hitter"
                    icon   = "🥎" if role_g == "pitcher" else "🏏"
                    c1.markdown(f"{icon} **{r['name']}** `{r['position']}` — {r['team']}")
                    if c2.button("＋", key=f"add_{r['id']}"):
                        db.add_player(r["id"], r["name"], r["team"], r["position"], role_g)
                        st.success(f"✅ {r['name']} ajouté")
                        st.rerun()
                if not res:
                    st.warning("Aucun joueur trouvé.")
            except Exception as e:
                st.error(str(e))


# ── Pages ─────────────────────────────────────────────────────────────────────
SLOT_COLORS = {"SP":"#388bfd","RP":"#79c0ff","C_MI":"#d2a8ff",
               "CI":"#f0883e","OF":"#3fb950","XH":"#ffa657","FLEX":"#ff7b72"}

tab_gw, tab_day, tab_iopp, tab_roster_mgmt = st.tabs(
    ["🏆 GW en cours", "📊 Scores du jour", "📈 Performance", "⚙️ Gestion"]
)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — GW en cours : So7 + scores cumulés
# ══════════════════════════════════════════════════════════════════════════════
with tab_gw:
    cur_gw   = gw.current_gw()
    prev_gw  = gw.previous_gw()
    gw_start = datetime.date.fromisoformat(cur_gw["start_date"])
    gw_end   = datetime.date.fromisoformat(cur_gw["end_date"])

    # Sélecteur GW
    col_sel, col_btn = st.columns([3, 1])
    gw_choice = col_sel.selectbox(
        "Gameweek",
        options=["current", "previous"],
        format_func=lambda x: f"✅ GW en cours — {cur_gw['label']}" if x == "current"
                              else f"⬅️ GW précédente — {prev_gw['label']}",
        label_visibility="collapsed"
    )

    if gw_choice == "previous":
        gw_ref   = prev_gw
        gw_start = datetime.date.fromisoformat(prev_gw["start_date"])
        gw_end   = datetime.date.fromisoformat(prev_gw["end_date"])
    else:
        gw_ref = cur_gw

    # Calcul score GW par joueur
    roster  = db.get_roster()
    t_today = today()
    range_end = min(t_today, gw_end).isoformat()

    gw_scores_by_player = {}
    for p in roster:
        sc_list = db.get_scores_range(
            p["player_id"], gw_start.isoformat(), range_end
        )
        gw_scores_by_player[p["player_id"]] = {
            "total":  round(sum(s["total"] for s in sc_list if s.get("total") is not None), 2),
            "games":  sum(1 for s in sc_list if s.get("total") is not None),
            "days":   {s["date"]: s.get("total") for s in sc_list},
        }

    team_total = sum(v["total"] for v in gw_scores_by_player.values())
    days_done  = max(0, (min(t_today, gw_end) - gw_start).days + 1)
    days_total = (gw_end - gw_start).days + 1

    # Banner
    st.markdown(f"""
<div class="gw-banner">
  <div>
    <div class="gw-label">Gameweek</div>
    <div class="gw-name">{gw_ref['label']}</div>
    <div class="gw-dates">{fmt_date(gw_start)} → {fmt_date(gw_end)} {gw_end.year}</div>
  </div>
  <div style="flex:1"></div>
  <div style="text-align:right">
    <div class="gw-label">Score équipe</div>
    <div class="gw-score">{team_total:+.1f} pts</div>
    <div class="gw-pill">J{days_done}/{days_total} · {gw_ref['days_left']} restant(s)</div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── So7 optimisé ──────────────────────────────────────────────────────────
    st.markdown("### 🏟️ Meilleure lineup So7")

    gw_player_scores = so7_mod.compute_gameweek_scores(
        gw_start.isoformat(), range_end
    )
    so7_result = so7_mod.optimize_so7(gw_player_scores)

    if not so7_result:
        st.warning("Roster insuffisant pour constituer une So7 complète.")
    else:
        lineup = so7_result["lineup"]
        bench  = so7_result["bench"]

        m1,m2,m3,m4 = st.columns(4)
        best_p = max(lineup.values(), key=lambda x: x["total_gw"])
        m1.metric("🏆 Score So7",  f"{so7_result['total']:.1f} pts")
        m2.metric("⭐ MVP",         f"{best_p['name']} ({best_p['total_gw']:.1f})")
        m3.metric("🎮 Matchs",      sum(p["games_played"] for p in lineup.values()))
        m4.metric("📅 Période",     f"{fmt_date(gw_start)} → {fmt_date(gw_end)}")

        st.markdown("")

        # Affichage 2 colonnes : pitchers | hitters
        c_pitch, c_hit = st.columns(2)

        for slot in so7_mod.SO7_SLOTS:
            if slot not in lineup: continue
            p   = lineup[slot]
            col = SLOT_COLORS.get(slot, "#8b949e")
            sc  = p["total_gw"]
            sc_cls = "sc-pos" if sc >= 0 else "sc-neg"

            # Détail jours
            days_detail = "  ".join(
                f"`{d[5:]}` **{v:+.0f}**" if v is not None else f"`{d[5:]}` —"
                for d, v in sorted(p["days"].items())
            )

            tgt = c_pitch if slot in ("SP","RP") else c_hit
            with tgt:
                st.markdown(f"""
<div class="so7-slot">
  <div class="so7-dot" style="background:{col}"></div>
  <div style="flex:1;min-width:0">
    <div class="so7-label">{so7_mod.SLOT_LABELS[slot]}</div>
    <div class="so7-name">{p['name']}</div>
    <div class="so7-meta">{p['team']} · {p['position']} · {p['games_played']} match(s)</div>
  </div>
  <div class="so7-sc {sc_cls}">{sc:+.1f}</div>
</div>""", unsafe_allow_html=True)
                st.caption(days_detail)

        # Banc
        if bench:
            with st.expander(f"🪑 Banc — {len(bench)} joueur(s)"):
                for b in bench:
                    blocked = [s for s in b["eligible_slots"]
                               if s in lineup and lineup[s]["total_gw"] >= b["total_gw"]]
                    reason = (f"→ {', '.join(so7_mod.SLOT_LABELS[s] for s in blocked)}"
                              if blocked else "")
                    col_sc = "sc-pos" if b["total_gw"] >= 0 else "sc-neg"
                    st.markdown(
                        f"**{b['name']}** `{b['position']}` "
                        f"<span class='{col_sc}'>{b['total_gw']:+.1f} pts</span> "
                        f"({b['games_played']}G) {reason}",
                        unsafe_allow_html=True
                    )

    st.markdown("---")

    # ── Tableau cumulatif de la GW ────────────────────────────────────────────
    st.markdown("### 📊 Scores cumulés GW")

    if not roster:
        st.info("Roster vide.")
    else:
        nd   = (gw_end - gw_start).days + 1
        cols_dates = [(gw_start + datetime.timedelta(days=i)).isoformat() for i in range(nd)]

        rows = []
        for p in roster:
            pid  = p["player_id"]
            gws  = gw_scores_by_player.get(pid, {"total":0,"games":0,"days":{}})
            row  = {
                "Joueur":   p["name"],
                "Rôle":     "🥎 Pitcher" if p["role"] == "pitcher" else "🏏 Hitter",
                "Pos":      p["position"],
                "Total GW": gws["total"],
                "Matchs":   gws["games"],
            }
            for d in cols_dates:
                row[d[5:]] = gws["days"].get(d)
            rows.append(row)

        df = pd.DataFrame(rows).sort_values("Total GW", ascending=False)
        dc = [d[5:] for d in cols_dates]

        def _col(v):
            if pd.isna(v): return "color:#8b949e"
            if v > 30: return "background-color:#1a7f37;color:white"
            if v > 15: return "background-color:#196c2e;color:#7ee787"
            if v > 0:  return "color:#7ee787"
            if v < 0:  return "background-color:#6e1c1c;color:#ff7b72"
            return "color:#8b949e"

        st.dataframe(
            df.style
              .format("{:.1f}", subset=["Total GW"] + dc, na_rep="—")
              .applymap(_col, subset=dc),
            use_container_width=True, hide_index=True
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — Scores du jour, hitters et pitchers séparés
# ══════════════════════════════════════════════════════════════════════════════
with tab_day:
    t_today   = today()
    cur_gw    = gw.current_gw()
    gw_start  = datetime.date.fromisoformat(cur_gw["start_date"])
    gw_end    = datetime.date.fromisoformat(cur_gw["end_date"])

    selected  = st.date_input("Date", value=t_today, max_value=t_today, key="day_date")
    date_str  = selected.isoformat()

    # Synchro silencieuse
    if not db.is_date_synced(date_str) and db.get_roster():
        with st.spinner(f"Synchro {date_str}…"):
            sync.sync_date(selected, force=False)

    # Score GW cumulé
    roster = db.get_roster()
    range_end_day = min(t_today, gw_end).isoformat()
    gw_by_pid = {}
    for p in roster:
        sc_list = db.get_scores_range(p["player_id"], cur_gw["start_date"], range_end_day)
        gw_by_pid[p["player_id"]] = round(
            sum(s["total"] for s in sc_list if s.get("total") is not None), 2
        )

    scores = db.get_scores_for_date(date_str)
    if not scores:
        if not roster:
            st.warning("Roster vide.")
        else:
            st.info(f"Aucune donnée pour le {date_str}. Lance une synchronisation.")
        st.stop()

    valid    = [s for s in scores if s["total"] is not None]
    no_games = [s for s in scores if s["total"] is None]

    # Métriques
    if valid:
        td   = sum(s["total"] for s in valid)
        best = max(valid, key=lambda x: x["total"])
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("🏆 Score du jour", f"{td:.1f}")
        m2.metric("📊 Moy/joueur",    f"{td/len(valid):.1f}")
        m3.metric("⭐ Meilleur",       f"{best['player_name']} ({best['total']:.1f})")
        m4.metric("👥 Actifs",         f"{len(valid)}/{len(scores)}")

    # Historique 7j pour les pills
    hist_start = (selected - datetime.timedelta(days=6)).isoformat()
    all_hist   = {s["player_id"]: db.get_scores_range(s["player_id"], hist_start, date_str)
                  for s in scores}

    def render_cards(player_list: list, per_row: int = 6):
        """Affiche les cartes joueurs en grille."""
        sorted_pl = sorted(
            [s for s in player_list if s["total"] is not None],
            key=lambda x: x["total"], reverse=True
        ) + [s for s in player_list if s["total"] is None]

        for chunk in [sorted_pl[i:i+per_row] for i in range(0, len(sorted_pl), per_row)]:
            cols = st.columns(per_row)
            for col, s in zip(cols, chunk):
                pid   = s["player_id"]
                name  = s.get("player_name", "?")
                pos   = s.get("position", "?")
                total = s.get("total")
                rank  = sorted_pl.index(s) + 1

                rc = "r1" if rank==1 else "r2" if rank==2 else "r3" if rank==3 else ""
                rl = "🥇" if rank==1 else "🥈" if rank==2 else "🥉" if rank==3 else ""
                dns_cls = "" if total is not None else " dns"
                role    = s.get("role","hitter")
                p_cls   = " pitcher-card" if role=="pitcher" else ""

                if total is None:
                    sc_html = '<div class="sc-dns">DNS</div>'
                else:
                    c = "sc-pos" if total>=0 else "sc-neg"
                    sc_html = f'<div class="sc-val {c}">{total:+.1f}</div>'

                gv = gw_by_pid.get(pid, 0.0)
                gw_html = f'<div class="sc-gw">GW {gv:+.1f}</div>' if gv else ""

                hist   = sorted(all_hist.get(pid, []), key=lambda x: x["date"])
                pills  = "".join(
                    f'<span class="pill pill-{"pos" if (v or 0)>=0 else "neg"}">'
                    f'{h["date"][5:]} {v:+.0f}</span>'
                    if v is not None else
                    f'<span class="pill pill-nil">{h["date"][5:]}</span>'
                    for h in hist for v in [h.get("total")]
                )

                img = get_player_headshot_url(pid)
                fn  = name.split(" ")[0]

                with col:
                    st.markdown(f"""
<div class="pcard {rc}{p_cls}{dns_cls}">
  <div class="pc-header">
    <span class="pc-pos">{pos}</span>
    <span class="pc-rank">{rl}</span>
  </div>
  <div class="pc-photo">
    <img src="{img}" alt="{name}"
     onerror="this.src='https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/0/headshot/67/current'"/>
  </div>
  <div class="pc-name" title="{name}">{fn}</div>
  <div class="pc-score">{sc_html}{gw_html}</div>
  <div class="pills">{pills}</div>
</div>""", unsafe_allow_html=True)

                    bd = s.get("breakdown", {})
                    if bd and total is not None:
                        with st.expander("≡", expanded=False):
                            st.dataframe(
                                pd.DataFrame([{"Action": k, "Pts": v}
                                              for k,v in bd.items()])
                                  .sort_values("Pts", ascending=False),
                                hide_index=True, use_container_width=True)

    # Séparation Pitchers / Hitters
    pitchers_scores = [s for s in scores if s.get("role") == "pitcher"]
    hitters_scores  = [s for s in scores if s.get("role") != "pitcher"]

    if pitchers_scores:
        st.markdown('<div class="role-sep">⚾ Pitchers</div>', unsafe_allow_html=True)
        render_cards(pitchers_scores, per_row=min(6, len(pitchers_scores)))

    if hitters_scores:
        st.markdown('<div class="role-sep">🏏 Hitters</div>', unsafe_allow_html=True)
        render_cards(hitters_scores, per_row=6)

    if no_games:
        st.caption("⚫ DNS : " + " · ".join(s["player_name"] for s in no_games))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — Performance (IOPP) : surperf/sous-perf vs 2025
# ══════════════════════════════════════════════════════════════════════════════
with tab_iopp:
    st.subheader("📈 Index de Performance — L15 2026 vs moyenne 2025")
    st.caption(
        "**L15** = moyenne des 15 derniers matchs joués en 2026 (scores Sorare). "
        "**2025** = score moyen recalculé depuis les stats saison MLB 2025. "
        "Seuil ±15% → 🔥 Surperformance / ❄️ Sous-performance."
    )

    roster = db.get_roster()
    if not roster:
        st.warning("Roster vide.")
    else:
        col_btn, col_info = st.columns([1, 3])
        if col_btn.button("🔄 Calculer l'IOPP", type="primary"):
            with st.spinner("Calcul IOPP (appels API MLB 2025)…"):
                st.session_state["iopp"] = iopp_mod.compute_roster_iopp(roster)

        if "iopp" not in st.session_state:
            st.info("Clique sur **Calculer l'IOPP** pour lancer l'analyse.")
        else:
            ioppd = st.session_state["iopp"]

            surperf = [p for p in roster if (ioppd.get(p["player_id"],{}).get("pct") or 0) >= 15]
            sousp   = [p for p in roster if (ioppd.get(p["player_id"],{}).get("pct") or 0) <= -15]
            norme   = [p for p in roster if p not in surperf and p not in sousp]

            m1,m2,m3 = st.columns(3)
            m1.metric("🔥 Surperformance",  len(surperf))
            m2.metric("➡️ Dans la norme",   len(norme))
            m3.metric("❄️ Sous-performance", len(sousp))

            st.markdown("---")

            # Tri par % décroissant, avec pitchers/hitters mélangés mais identifiés
            def _pct(p): return -(ioppd.get(p["player_id"],{}).get("pct") or 0)
            sorted_r = sorted(roster, key=_pct)

            COLS_I = 3
            for chunk in [sorted_r[i:i+COLS_I] for i in range(0, len(sorted_r), COLS_I)]:
                cols = st.columns(COLS_I)
                for col, p in zip(cols, chunk):
                    pid  = p["player_id"]
                    ip   = ioppd.get(pid, {})
                    l15  = ip.get("l15_avg")
                    a25  = ip.get("avg_2025")
                    pct  = ip.get("pct")
                    dlt  = ip.get("delta")
                    sta  = ip.get("status", "❓")
                    scol = ip.get("status_color", "#8b949e")
                    g15  = ip.get("l15_games", 0)
                    g25  = ip.get("games_2025", 0)
                    img  = get_player_headshot_url(pid)
                    is_p = p["role"] == "pitcher"
                    role_tag = (
                        '<span style="background:#21262d;color:#388bfd;border:1px solid #388bfd;'
                        'border-radius:4px;padding:0 4px;font-size:.55rem;font-weight:700">SP/RP</span>'
                        if is_p else
                        '<span style="background:#1f6feb;color:#fff;'
                        'border-radius:4px;padding:0 4px;font-size:.55rem;font-weight:700">H</span>'
                    )
                    bar = int(min(max(l15/a25,0),2)/2*100) if (l15 and a25 and a25>0) else 50

                    with col:
                        st.markdown(f"""
<div class="iopp-card">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
    <img src="{img}" style="width:44px;height:40px;object-fit:cover;
      object-position:top;border-radius:5px;"
      onerror="this.style.display='none'"/>
    <div style="flex:1;min-width:0">
      <div style="font-weight:700;font-size:.88rem;color:#e6edf3;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
        {p['name']}</div>
      <div style="font-size:.65rem;color:#8b949e;">
        {p['position']} {role_tag}</div>
    </div>
    <div style="font-size:1.1rem">{sta}</div>
  </div>
  <div class="iopp-bar-bg">
    <div class="iopp-bar-fill" style="width:{bar}%;background:{scol}"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:.68rem;gap:4px;">
    <div>
      <div style="color:#8b949e">L{g15} 2026</div>
      <div style="color:#e6edf3;font-weight:800;font-size:.95rem">
        {f"{l15:+.1f}" if l15 is not None else "—"}</div>
    </div>
    <div style="text-align:center">
      <div style="color:#8b949e">Δ vs 2025</div>
      <div style="color:{scol};font-weight:800;font-size:.95rem">
        {f"{dlt:+.1f} ({pct:+.0f}%)" if dlt is not None else "—"}</div>
    </div>
    <div style="text-align:right">
      <div style="color:#8b949e">Moy 2025 ({g25}G)</div>
      <div style="color:#e6edf3;font-weight:800;font-size:.95rem">
        {f"{a25:.1f}" if a25 else "—"}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

            # Tableau récap
            st.markdown("---")
            rows_io = [{
                "Joueur":    p["name"],
                "Rôle":      "Pitcher" if p["role"]=="pitcher" else "Hitter",
                "Pos":       p["position"],
                "L15 2026":  ioppd.get(p["player_id"],{}).get("l15_avg"),
                "Moy 2025":  ioppd.get(p["player_id"],{}).get("avg_2025"),
                "Δ":         ioppd.get(p["player_id"],{}).get("delta"),
                "Δ%":        ioppd.get(p["player_id"],{}).get("pct"),
                "Statut":    ioppd.get(p["player_id"],{}).get("status","—"),
            } for p in sorted_r]

            def _cp(v):
                if pd.isna(v): return "color:#8b949e"
                if v >= 15: return "color:#3fb950;font-weight:700"
                if v <= -15: return "color:#f85149;font-weight:700"
                return "color:#8b949e"

            st.dataframe(
                pd.DataFrame(rows_io).style
                  .format("{:.1f}", subset=["L15 2026","Moy 2025","Δ"], na_rep="—")
                  .format("{:.0f}%", subset=["Δ%"], na_rep="—")
                  .applymap(_cp, subset=["Δ%"]),
                hide_index=True, use_container_width=True
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — Gestion : historique, GW sauvegardées, scheduler
# ══════════════════════════════════════════════════════════════════════════════
with tab_roster_mgmt:
    st.subheader("⚙️ Gestion & Historique")

    # ── Historique ────────────────────────────────────────────────────────────
    st.markdown("**📅 Historique des scores**")
    roster = db.get_roster()
    avail  = db.get_all_dates_with_scores()

    if not avail:
        st.info("Aucune donnée. Lance une synchronisation.")
    else:
        cur  = gw.current_gw()
        prev = gw.previous_gw()
        pmap = {
            f"GW en cours ({cur['label']})":    (cur["start_date"],  cur["end_date"]),
            f"GW précédente ({prev['label']})": (prev["start_date"], prev["end_date"]),
            "Personnalisé": None,
        }
        pk = st.selectbox("Période", list(pmap.keys()))
        pv = pmap[pk]
        if pv:
            hs = datetime.date.fromisoformat(pv[0])
            he = datetime.date.fromisoformat(pv[1])
        else:
            max_d = datetime.date.fromisoformat(avail[0])
            min_d = datetime.date.fromisoformat(avail[-1])
            c1, c2 = st.columns(2)
            hs = c1.date_input("Du", value=min_d, min_value=min_d, max_value=max_d, key="hs")
            he = c2.date_input("Au", value=max_d, min_value=min_d, max_value=max_d, key="he")

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
            dc  = [c for c in piv.columns if c not in ("TOTAL","MOY")]

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

            sel = st.selectbox("Zoom joueur", df_h["Joueur"].unique(), key="zoom")
            df_z = df_h[df_h["Joueur"] == sel].set_index("Date")["Score"].dropna()
            if not df_z.empty:
                st.bar_chart(df_z, use_container_width=True)
        else:
            st.info("Aucun score sur cette période.")

    st.markdown("---")

    # ── GW sauvegardées ────────────────────────────────────────────────────────
    st.markdown("**📁 Gameweeks sauvegardées**")
    col_a, col_b = st.columns(2)
    with col_a:
        gw_lbl = st.text_input("Nom", placeholder="ex: GW Midweek 30 mars")
        gw_s_  = st.date_input("Début", key="gw_save_s",
                               value=today()-datetime.timedelta(days=6))
        gw_e_  = st.date_input("Fin",   key="gw_save_e",
                               value=today()-datetime.timedelta(days=3))
        if st.button("💾 Sauvegarder la GW"):
            if gw_lbl:
                db.save_gameweek(gw_lbl, gw_s_.isoformat(), gw_e_.isoformat())
                st.success("✅ Sauvegardée"); st.rerun()

    with col_b:
        saved = db.get_gameweeks()
        if saved:
            for g in saved:
                c1, c2 = st.columns([3,1])
                c1.markdown(f"**{g['label']}**  \n`{g['start_date']}` → `{g['end_date']}`")
                if c2.button("🗑", key=f"del_{g['id']}"):
                    db.delete_gameweek(g["id"]); st.rerun()
        else:
            st.info("Aucune GW sauvegardée.")

    st.markdown("---")

    # ── Scheduler status ───────────────────────────────────────────────────────
    st.markdown("**🕐 Scheduler**")
    ok = sync._scheduler and sync._scheduler.running
    if ok:
        st.success("✅ Actif — synchro toutes les heures (Europe/Paris)")
        for j in sync._scheduler.get_jobs():
            st.code(f"Prochain run : {j.next_run_time}")
    else:
        st.warning("⚠️ Scheduler inactif.")
