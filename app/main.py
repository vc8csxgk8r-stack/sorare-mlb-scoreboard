"""
Sorare MLB Scoreboard v2
Page d'accueil : Scores du jour · Pitchers séparés des hitters
Timezone : Europe/Paris · Synchro auto toutes les heures
"""

import streamlit as st
import datetime, zoneinfo, logging, pandas as pd

import db, sync, gameweek as gw, so7 as so7_mod, iopp as iopp_mod
from mlb_fetcher import search_player, get_player_headshot_url

TZ = zoneinfo.ZoneInfo("Europe/Paris")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

st.set_page_config(page_title="Sorare MLB", page_icon="⚾",
                   layout="wide", initial_sidebar_state="expanded")
db.init_db()
db.fix_roster_roles()   # corrige SP/RP mal catégorisés en hitters
sync.start_scheduler()

def today() -> datetime.date:
    return datetime.datetime.now(tz=TZ).date()

def fmt(d): # 26 mar
    M=["jan","fév","mar","avr","mai","juin","juil","août","sep","oct","nov","déc"]
    return f"{d.day} {M[d.month-1]}"

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background:#0d1117; }

/* Éviter que le header Streamlit rogne le contenu */
.block-container { padding-top:1.5rem !important; padding-bottom:1rem; }
header[data-testid="stHeader"] { background:rgba(13,17,23,.95); }

/* Cartes joueurs — taille fixe pour que le score soit toujours visible */
.pc {
  background:#161b22;
  border:2px solid #30363d;
  border-radius:9px;
  overflow:hidden;
  text-align:center;
  transition:border-color .15s;
  display:flex;
  flex-direction:column;
  min-height:165px;   /* hauteur minimale garantie */
}
.pc:hover{border-color:#388bfd;}
.pc.r1{border-color:#f1c40f;box-shadow:0 0 8px #f1c40f33;}
.pc.r2{border-color:#95a5a6;}
.pc.r3{border-color:#cd7f32;}
.pc.sp{border-color:#388bfd55;}
.pc.rp{border-color:#79c0ff55;}
.pc.dns{opacity:.45;}

.pc-top{flex-shrink:0;display:flex;justify-content:space-between;align-items:center;
  padding:3px 6px;background:rgba(0,0,0,.4);}
.pc-pos{font-size:.55rem;font-weight:700;color:#8b949e;}
.pc-rnk{font-size:.58rem;font-weight:800;color:#f1c40f;}
.p-tag{font-size:.48rem;font-weight:800;padding:0 3px;border-radius:3px;
  background:#21262d;color:#79c0ff;border:1px solid #79c0ff;}
.h-tag{font-size:.48rem;font-weight:800;padding:0 3px;border-radius:3px;
  background:#1f6feb;color:#fff;}

/* Photo — hauteur fixe */
.pc-img{flex-shrink:0;background:linear-gradient(180deg,#1a2030,#111820);
  display:flex;align-items:flex-end;justify-content:center;
  height:80px;overflow:hidden;padding:4px 2px 0;}
.pc-img img{width:72px;height:76px;object-fit:cover;
  object-position:top;border-radius:4px 4px 0 0;}

.pc-name{flex-shrink:0;font-size:.65rem;font-weight:700;padding:3px 4px 1px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

/* Score — toujours visible, ne se fait pas rogner */
.pc-score{
  flex-shrink:0;
  background:#0a0e14;
  border-top:1px solid #30363d;
  padding:5px 4px 6px;
}
.sv{font-size:1.05rem;font-weight:900;line-height:1.1;}
.sv.pos{color:#3fb950;} .sv.neg{color:#f85149;} .sv.dns{color:#8b949e;font-size:.7rem;}
.sg{font-size:.55rem;color:#79c0ff;font-weight:700;margin-top:2px;}

/* Séparateur rôle */
.rsep{display:flex;align-items:center;gap:8px;margin:12px 0 7px;
  font-size:.6rem;font-weight:800;color:#8b949e;text-transform:uppercase;letter-spacing:.1em;}
.rsep::before,.rsep::after{content:'';flex:1;height:1px;background:#30363d;}

/* Pills */
.pills{flex-shrink:0;display:flex;flex-wrap:wrap;gap:2px;justify-content:center;
  padding:2px 3px 4px;}
.pill{font-size:.5rem;font-weight:700;padding:1px 3px;border-radius:3px;white-space:nowrap;}
.p-pos{background:#196c2e;color:#7ee787;}
.p-neg{background:#6e1c1c;color:#ff7b72;}
.p-nil{background:#21262d;color:#8b949e;}

/* GW banner */
.gw-banner{background:linear-gradient(135deg,#161b22,#1c2128);
  border:1px solid #30363d;border-radius:9px;padding:14px 20px;margin-bottom:16px;
  display:flex;align-items:center;gap:16px;flex-wrap:wrap;}
.gw-lbl{font-size:.55rem;font-weight:700;color:#8b949e;
  text-transform:uppercase;letter-spacing:.07em;}
.gw-name{font-size:.95rem;font-weight:800;color:#e6edf3;}
.gw-dt  {font-size:.7rem;color:#8b949e;}
.gw-tot {font-size:1.5rem;font-weight:900;}
.gw-pill{background:#21262d;color:#79c0ff;border-radius:5px;
  padding:2px 8px;font-size:.65rem;font-weight:700;}

/* So7 */
.so7-slot{background:#161b22;border:1px solid #30363d;border-radius:8px;
  padding:8px 12px;display:flex;align-items:center;gap:10px;margin-bottom:5px;}
.s-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;}
.s-lbl{font-size:.52rem;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.06em;}
.s-name{font-size:.83rem;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.s-meta{font-size:.58rem;color:#8b949e;}
.s-sc  {font-size:.95rem;font-weight:900;white-space:nowrap;margin-left:auto;}
.sc-pos{color:#3fb950;} .sc-neg{color:#f85149;}

/* IOPP */
.icard{background:#161b22;border:1px solid #30363d;border-radius:9px;padding:13px;}
.i-bar-bg{background:#21262d;border-radius:4px;height:7px;margin:7px 0 5px;overflow:hidden;}
.i-bar   {height:100%;border-radius:4px;}
</style>
""", unsafe_allow_html=True)

SLOT_COLORS = {"SP":"#388bfd","RP":"#79c0ff","C_MI":"#d2a8ff",
               "CI":"#f0883e","OF":"#3fb950","XH":"#ffa657","FLEX":"#ff7b72"}

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚾ Sorare MLB")

    # GW
    cur = gw.current_gw()
    st.markdown(f"""
<div style="background:#161b22;border:1px solid #30363d;border-radius:7px;
  padding:8px 12px;margin-bottom:10px;">
  <div style="font-size:.52rem;color:#8b949e;text-transform:uppercase;letter-spacing:.07em">GW EN COURS</div>
  <div style="font-size:.82rem;font-weight:700;margin:2px 0">{cur['label']}</div>
  <div style="font-size:.62rem;color:#79c0ff">⏱ {cur['days_left']} jour(s) restant(s)</div>
</div>""", unsafe_allow_html=True)

    # Synchro
    sched_ok = sync._scheduler and sync._scheduler.running
    if sched_ok:
        jobs = sync._scheduler.get_jobs()
        nxt  = jobs[0].next_run_time.strftime("%H:%M") if jobs else "?"
        st.caption(f"✅ Auto toutes les heures · prochain {nxt}")
    else:
        st.caption("⚠️ Scheduler inactif")

    force = st.checkbox("Forcer re-fetch", value=False)
    if st.button("🔄 Synchroniser", use_container_width=True, type="primary"):
        cur2     = gw.current_gw()
        gw_start = datetime.date.fromisoformat(cur2["start_date"])
        gw_end   = datetime.date.fromisoformat(cur2["end_date"])
        dates, d = [], gw_start
        while d <= min(today(), gw_end):
            dates.append(d); d += datetime.timedelta(days=1)
        yest = today() - datetime.timedelta(days=1)
        if yest not in dates: dates.append(yest)

        synced = dns = errors = 0
        with st.spinner("Synchro…"):
            for date in sorted(set(dates)):
                if not force and db.is_date_synced(date.isoformat()): continue
                r = sync.sync_date(date, force=force)
                synced += r.get("synced",0); dns += r.get("no_game",0); errors += r.get("errors",0)

        if errors:     st.error(f"⚠️ {errors} erreur(s)")
        elif synced==0 and dns==0: st.info("✅ Déjà à jour")
        else:          st.success(f"✅ {synced} score(s) · {dns} DNS")

    st.markdown("---")

    # Roster
    st.subheader("👥 Roster")
    roster = db.get_roster()
    pitchers = [p for p in roster if p["role"]=="pitcher"]
    hitters  = [p for p in roster if p["role"]!="pitcher"]
    if pitchers:
        st.caption("🥎 Pitchers")
        for p in pitchers:
            c1,c2=st.columns([3,1])
            c1.markdown(f"**{p['name']}** `{p['position']}`")
            if c2.button("✕",key=f"rm_{p['player_id']}"):
                db.remove_player(p["player_id"]); st.rerun()
    if hitters:
        st.caption("🏏 Hitters")
        for p in hitters:
            c1,c2=st.columns([3,1])
            c1.markdown(f"**{p['name']}** `{p['position']}`")
            if c2.button("✕",key=f"rm_{p['player_id']}"):
                db.remove_player(p["player_id"]); st.rerun()
    if not roster: st.info("Roster vide.")

    st.markdown("---")
    st.subheader("➕ Ajouter")
    q = st.text_input("Rechercher", placeholder="Shohei Ohtani",
                      label_visibility="collapsed")
    if q and len(q)>=3:
        with st.spinner("…"):
            try:
                for r in search_player(q)[:5]:
                    rg = "pitcher" if r["position"] in ("SP","RP","P","CL") else "hitter"
                    c1,c2=st.columns([3,1])
                    c1.markdown(f"{'🥎' if rg=='pitcher' else '🏏'} **{r['name']}** `{r['position']}`")
                    if c2.button("＋",key=f"add_{r['id']}"):
                        db.add_player(r["id"],r["name"],r["team"],r["position"],rg)
                        st.success(f"✅ Ajouté"); st.rerun()
            except Exception as e: st.error(str(e))


# ── Onglets ────────────────────────────────────────────────────────────────────
tab_day, tab_gw, tab_iopp, tab_admin = st.tabs(
    ["📊 Scores du jour", "🏆 GW & So7", "📈 Performance", "⚙️ Gestion"]
)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Scores du jour  ← PAGE D'ACCUEIL
# ══════════════════════════════════════════════════════════════════════════════
with tab_day:
    t = today()
    cur_gw   = gw.current_gw()
    gw_start = datetime.date.fromisoformat(cur_gw["start_date"])
    gw_end   = datetime.date.fromisoformat(cur_gw["end_date"])

    selected = st.date_input("Date", value=t, max_value=t, key="day_date",
                             label_visibility="collapsed")
    date_str = selected.isoformat()

    # Synchro silencieuse
    if not db.is_date_synced(date_str) and db.get_roster():
        with st.spinner(f"Synchro {date_str}…"):
            sync.sync_date(selected, force=False)

    # Score GW cumulé par joueur
    range_end = min(t, gw_end).isoformat()
    gw_by_pid = {}
    for p in db.get_roster():
        sc_list = db.get_scores_range(p["player_id"], cur_gw["start_date"], range_end)
        gw_by_pid[p["player_id"]] = round(
            sum(s["total"] for s in sc_list if s.get("total") is not None), 2)

    scores = db.get_scores_for_date(date_str)
    if not scores:
        if not db.get_roster():
            st.warning("Roster vide — ajoute des joueurs dans la sidebar.")
        else:
            st.info(f"Aucune donnée pour le {date_str}. Clique sur **🔄 Synchroniser**.")
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

        hist_start = (selected - datetime.timedelta(days=6)).isoformat()
        all_hist   = {s["player_id"]: db.get_scores_range(s["player_id"], hist_start, date_str)
                      for s in scores}

        def make_card_html(s, rank=0):
            pid   = s["player_id"]
            name  = s.get("player_name","?")
            pos   = s.get("position","?")
            total = s.get("total")
            role  = s.get("role","hitter")
            is_p  = role == "pitcher"

            rc = "r1" if rank==1 else "r2" if rank==2 else "r3" if rank==3 else ""
            rl = "🥇" if rank==1 else "🥈" if rank==2 else "🥉" if rank==3 else ""
            dns_cls = "" if total is not None else " dns"
            p_cls   = (" sp" if pos=="SP" else " rp" if pos in ("RP","CL") else "") if is_p else ""
            badge   = f'<span class="p-tag">{pos}</span>' if is_p else '<span class="h-tag">H</span>'

            if total is None:
                sc_html = '<div class="sv dns">DNS</div>'
            else:
                c = "pos" if total>=0 else "neg"
                sc_html = f'<div class="sv {c}">{total:+.1f}</div>'

            gv = gw_by_pid.get(pid,0.0)
            gw_html = f'<div class="sg">GW {gv:+.1f}</div>' if gv else ""

            hist  = sorted(all_hist.get(pid,[]), key=lambda x: x["date"])
            pills = "".join(
                f'<span class="pill {"p-pos" if (h.get("total") or 0)>=0 else "p-neg"}">'
                f'{h["date"][5:]} {h["total"]:+.0f}</span>'
                if h.get("total") is not None else
                f'<span class="pill p-nil">{h["date"][5:]}</span>'
                for h in hist
            )

            img = get_player_headshot_url(pid)
            fn  = name.split()[-1]  # nom de famille

            return f"""
<div class="pc {rc}{p_cls}{dns_cls}">
  <div class="pc-top">
    <span class="pc-pos">{badge}</span>
    <span class="pc-rnk">{rl}</span>
  </div>
  <div class="pc-img">
    <img src="{img}" alt="{name}"
     onerror="this.src='https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/0/headshot/67/current'"/>
  </div>
  <div class="pc-name" title="{name}">{fn}</div>
  <div class="pc-score">{sc_html}{gw_html}</div>
  <div class="pills">{pills}</div>
</div>"""

        # ── Pitchers en premier, puis hitters ────────────────────────────────
        pitcher_scores = sorted(
            [s for s in scores if s.get("role")=="pitcher"],
            key=lambda x: (x["total"] is None, -(x["total"] or 0))
        )
        hitter_scores = sorted(
            [s for s in scores if s.get("role")!="pitcher"],
            key=lambda x: (x["total"] is None, -(x["total"] or 0))
        )

        if pitcher_scores:
            st.markdown('<div class="rsep">⚾ Pitchers</div>', unsafe_allow_html=True)
            N = len(pitcher_scores)
            cols = st.columns(max(N, 2))
            for i, s in enumerate(pitcher_scores):
                with cols[i]:
                    st.markdown(make_card_html(s, rank=i+1 if s.get("total") else 0),
                                unsafe_allow_html=True)
                    bd = s.get("breakdown",{})
                    if bd and s.get("total") is not None:
                        with st.expander("Détail", expanded=False):
                            st.dataframe(
                                pd.DataFrame([{"Action":k,"Pts":v} for k,v in bd.items()])
                                  .sort_values("Pts",ascending=False),
                                hide_index=True, use_container_width=True)

        if hitter_scores:
            st.markdown('<div class="rsep">🏏 Hitters</div>', unsafe_allow_html=True)
            COLS = 6
            ranked = [s for s in hitter_scores if s.get("total") is not None]
            for chunk in [hitter_scores[i:i+COLS] for i in range(0,len(hitter_scores),COLS)]:
                cols = st.columns(COLS)
                for col, s in zip(cols, chunk):
                    rank = ranked.index(s)+1 if s in ranked else 0
                    with col:
                        st.markdown(make_card_html(s, rank=rank), unsafe_allow_html=True)
                        bd = s.get("breakdown",{})
                        if bd and s.get("total") is not None:
                            with st.expander("≡", expanded=False):
                                st.dataframe(
                                    pd.DataFrame([{"Action":k,"Pts":v} for k,v in bd.items()])
                                      .sort_values("Pts",ascending=False),
                                    hide_index=True, use_container_width=True)

        if no_games:
            st.caption("⚫ DNS : " + " · ".join(s["player_name"] for s in no_games))


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — GW & So7
# ══════════════════════════════════════════════════════════════════════════════
with tab_gw:
    cur_gw  = gw.current_gw()
    prev_gw = gw.previous_gw()

    choice = st.selectbox("Gameweek", ["current","previous"],
        format_func=lambda x: f"✅ GW en cours — {cur_gw['label']}"
                               if x=="current" else f"⬅️ GW précédente — {prev_gw['label']}",
        label_visibility="collapsed")

    ref      = cur_gw if choice=="current" else prev_gw
    gw_start = datetime.date.fromisoformat(ref["start_date"])
    gw_end   = datetime.date.fromisoformat(ref["end_date"])
    t        = today()
    range_end= min(t, gw_end).isoformat()

    roster   = db.get_roster()
    gw_by_p  = {}
    for p in roster:
        sc = db.get_scores_range(p["player_id"], ref["start_date"], range_end)
        gw_by_p[p["player_id"]] = {
            "total": round(sum(s["total"] for s in sc if s.get("total") is not None),2),
            "games": sum(1 for s in sc if s.get("total") is not None),
            "days":  {s["date"]:s.get("total") for s in sc},
        }

    team_tot  = sum(v["total"] for v in gw_by_p.values())
    days_done = max(0,(min(t,gw_end)-gw_start).days+1)
    days_tot  = (gw_end-gw_start).days+1

    st.markdown(f"""
<div class="gw-banner">
  <div>
    <div class="gw-lbl">Gameweek</div>
    <div class="gw-name">{ref['label']}</div>
    <div class="gw-dt">{fmt(gw_start)} → {fmt(gw_end)} {gw_end.year}</div>
  </div>
  <div style="flex:1"></div>
  <div style="text-align:right">
    <div class="gw-lbl">Score équipe</div>
    <div class="gw-tot {'sc-pos' if team_tot>=0 else 'sc-neg'}"
         style="color:{'#3fb950' if team_tot>=0 else '#f85149'}">{team_tot:+.1f} pts</div>
    <div class="gw-pill">J{days_done}/{days_tot} · {ref['days_left']} restant(s)</div>
  </div>
</div>""", unsafe_allow_html=True)

    # So7
    st.markdown("### 🏟️ Meilleure lineup So7")
    gw_sc    = so7_mod.compute_gameweek_scores(ref["start_date"], range_end)
    so7_res  = so7_mod.optimize_so7(gw_sc)

    if not so7_res:
        st.warning("Roster insuffisant pour une So7 complète.")
    else:
        lineup = so7_res["lineup"]
        best_p = max(lineup.values(), key=lambda x: x["total_gw"])
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("🏆 Score So7", f"{so7_res['total']:.1f} pts")
        m2.metric("⭐ MVP",        f"{best_p['name']} ({best_p['total_gw']:.1f})")
        m3.metric("🎮 Matchs",     sum(p["games_played"] for p in lineup.values()))
        m4.metric("👥 Slots",      f"{len(lineup)}/7")

        cp,ch = st.columns(2)
        for slot in so7_mod.SO7_SLOTS:
            if slot not in lineup: continue
            p   = lineup[slot]
            col = SLOT_COLORS.get(slot,"#8b949e")
            sc  = p["total_gw"]
            days_str = "  ".join(
                f"`{d[5:]}` **{v:+.0f}**" if v is not None else f"`{d[5:]}` —"
                for d,v in sorted(p["days"].items()))
            tgt = cp if slot in ("SP","RP") else ch
            with tgt:
                st.markdown(f"""
<div class="so7-slot">
  <div class="s-dot" style="background:{col}"></div>
  <div style="flex:1;min-width:0">
    <div class="s-lbl">{so7_mod.SLOT_LABELS[slot]}</div>
    <div class="s-name">{p['name']}</div>
    <div class="s-meta">{p['team']} · {p['position']} · {p['games_played']} match(s)</div>
  </div>
  <div class="s-sc {'sc-pos' if sc>=0 else 'sc-neg'}">{sc:+.1f}</div>
</div>""", unsafe_allow_html=True)
                st.caption(days_str)

        if so7_res["bench"]:
            with st.expander(f"🪑 Banc — {len(so7_res['bench'])} joueur(s)"):
                for b in so7_res["bench"]:
                    bl = [s for s in b["eligible_slots"]
                          if s in lineup and lineup[s]["total_gw"]>=b["total_gw"]]
                    reason = f"→ {', '.join(so7_mod.SLOT_LABELS[s] for s in bl)}" if bl else ""
                    st.markdown(f"**{b['name']}** `{b['position']}` "
                                f"**{b['total_gw']:+.1f} pts** ({b['games_played']}G) {reason}")

    # Tableau GW
    st.markdown("---")
    st.markdown("### 📊 Scores cumulés GW")
    nd   = (gw_end-gw_start).days+1
    dcols= [(gw_start+datetime.timedelta(days=i)).isoformat() for i in range(nd)]
    rows = []
    for p in roster:
        pid = p["player_id"]
        gd  = gw_by_p.get(pid,{"total":0,"games":0,"days":{}})
        row = {"Joueur":p["name"],
               "Rôle":"🥎 P" if p["role"]=="pitcher" else "🏏 H",
               "Pos":p["position"],"Total GW":gd["total"],"G":gd["games"]}
        for d in dcols: row[d[5:]] = gd["days"].get(d)
        rows.append(row)
    df   = pd.DataFrame(rows).sort_values("Total GW",ascending=False)
    dc   = [d[5:] for d in dcols]
    def _c(v):
        if pd.isna(v): return "color:#8b949e"
        if v>30: return "background-color:#1a7f37;color:white"
        if v>15: return "background-color:#196c2e;color:#7ee787"
        if v>0:  return "color:#7ee787"
        if v<0:  return "background-color:#6e1c1c;color:#ff7b72"
        return "color:#8b949e"
    st.dataframe(
        df.style.format("{:.1f}",subset=["Total GW"]+dc,na_rep="—").applymap(_c,subset=dc),
        use_container_width=True,hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Performance IOPP
# ══════════════════════════════════════════════════════════════════════════════
with tab_iopp:
    st.subheader("📈 Performance — L15 2026 vs saison 2025")
    st.caption("Seuil ±15% : 🔥 Surperformance / ❄️ Sous-performance vs la moyenne 2025.")

    roster = db.get_roster()
    if not roster:
        st.warning("Roster vide.")
    else:
        if st.button("🔄 Calculer l'IOPP", type="primary"):
            with st.spinner("Appels API MLB 2025…"):
                st.session_state["iopp"] = iopp_mod.compute_roster_iopp(roster)

        if "iopp" not in st.session_state:
            st.info("Clique sur **Calculer l'IOPP**.")
        else:
            ioppd  = st.session_state["iopp"]
            surp   = [p for p in roster if (ioppd.get(p["player_id"],{}).get("pct") or 0)>=15]
            sousp  = [p for p in roster if (ioppd.get(p["player_id"],{}).get("pct") or 0)<=-15]
            m1,m2,m3 = st.columns(3)
            m1.metric("🔥 Surperf",  len(surp))
            m2.metric("➡️ Norme",    len(roster)-len(surp)-len(sousp))
            m3.metric("❄️ Sous-perf",len(sousp))
            st.markdown("---")

            sorted_r = sorted(roster, key=lambda p:-(ioppd.get(p["player_id"],{}).get("pct") or 0))
            for chunk in [sorted_r[i:i+3] for i in range(0,len(sorted_r),3)]:
                cols = st.columns(3)
                for col,p in zip(cols,chunk):
                    pid  = p["player_id"]
                    ip   = ioppd.get(pid,{})
                    l15  = ip.get("l15_avg")
                    a25  = ip.get("avg_2025")
                    pct  = ip.get("pct")
                    dlt  = ip.get("delta")
                    sta  = ip.get("status","❓")
                    scol = ip.get("status_color","#8b949e")
                    g15  = ip.get("l15_games",0)
                    g25  = ip.get("games_2025",0)
                    is_p = p["role"]=="pitcher"
                    tag  = (f'<span style="background:#21262d;color:#79c0ff;border:1px solid #79c0ff;'
                            f'border-radius:3px;padding:0 4px;font-size:.5rem;font-weight:700">'
                            f'{p["position"]}</span>'
                            if is_p else
                            f'<span style="background:#1f6feb;color:#fff;'
                            f'border-radius:3px;padding:0 4px;font-size:.5rem;font-weight:700">H</span>')
                    bar  = int(min(max(l15/a25,0),2)/2*100) if (l15 and a25 and a25>0) else 50
                    img  = get_player_headshot_url(pid)

                    with col:
                        st.markdown(f"""
<div class="icard">
  <div style="display:flex;align-items:center;gap:9px;margin-bottom:8px;">
    <img src="{img}" style="width:42px;height:38px;object-fit:cover;
      object-position:top;border-radius:5px;" onerror="this.style.display='none'"/>
    <div style="flex:1;min-width:0">
      <div style="font-weight:700;font-size:.85rem;white-space:nowrap;
        overflow:hidden;text-overflow:ellipsis">{p['name']}</div>
      <div style="font-size:.62rem;color:#8b949e">{tag}</div>
    </div>
    <div style="font-size:1rem">{sta}</div>
  </div>
  <div class="i-bar-bg">
    <div class="i-bar" style="width:{bar}%;background:{scol}"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:.65rem;gap:4px;">
    <div><div style="color:#8b949e">L{g15} 2026</div>
      <div style="font-weight:800;font-size:.92rem">
        {f"{l15:+.1f}" if l15 is not None else "—"}</div></div>
    <div style="text-align:center"><div style="color:#8b949e">Δ vs 2025</div>
      <div style="color:{scol};font-weight:800;font-size:.92rem">
        {f"{dlt:+.1f} ({pct:+.0f}%)" if dlt is not None else "—"}</div></div>
    <div style="text-align:right"><div style="color:#8b949e">2025 ({g25}G)</div>
      <div style="font-weight:800;font-size:.92rem">
        {f"{a25:.1f}" if a25 else "—"}</div></div>
  </div>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Gestion
# ══════════════════════════════════════════════════════════════════════════════
with tab_admin:
    st.subheader("⚙️ Historique & Gestion")

    avail = db.get_all_dates_with_scores()
    roster = db.get_roster()

    if avail:
        cur  = gw.current_gw(); prev = gw.previous_gw()
        pmap = {
            f"GW en cours ({cur['label']})":    (cur["start_date"],  cur["end_date"]),
            f"GW précédente ({prev['label']})": (prev["start_date"], prev["end_date"]),
            "Personnalisé": None,
        }
        pk = st.selectbox("Période", list(pmap.keys()))
        pv = pmap[pk]
        if pv:
            hs=datetime.date.fromisoformat(pv[0]); he=datetime.date.fromisoformat(pv[1])
        else:
            max_d=datetime.date.fromisoformat(avail[0]); min_d=datetime.date.fromisoformat(avail[-1])
            c1,c2=st.columns(2)
            hs=c1.date_input("Du",value=min_d,min_value=min_d,max_value=max_d,key="hs")
            he=c2.date_input("Au",value=max_d,min_value=min_d,max_value=max_d,key="he")

        rows_h=[]
        for p in roster:
            for sc in db.get_scores_range(p["player_id"],hs.isoformat(),he.isoformat()):
                rows_h.append({"Joueur":p["name"],"Date":sc["date"],"Score":sc["total"]})

        if rows_h:
            df_h = pd.DataFrame(rows_h)
            piv  = df_h.pivot_table(index="Joueur",columns="Date",values="Score",aggfunc="first")
            piv["TOTAL"] = piv.sum(axis=1,skipna=True)
            piv["MOY"]   = piv.drop(columns=["TOTAL"]).mean(axis=1,skipna=True).round(1)
            piv = piv.sort_values("TOTAL",ascending=False)
            dc  = [c for c in piv.columns if c not in ("TOTAL","MOY")]
            def _cs(v):
                if pd.isna(v): return "color:#8b949e"
                if v>30: return "background-color:#1a7f37;color:white"
                if v>15: return "background-color:#196c2e;color:#7ee787"
                if v>0:  return "color:#7ee787"
                if v<0:  return "background-color:#6e1c1c;color:#ff7b72"
                return "color:#8b949e"
            st.dataframe(
                piv.style.format("{:.1f}",na_rep="DNS")
                          .applymap(_cs,subset=pd.IndexSlice[:,dc])
                          .format("{:.1f}",subset=["TOTAL","MOY"]),
                use_container_width=True)
            sel=st.selectbox("Zoom",df_h["Joueur"].unique(),key="zoom")
            df_z=df_h[df_h["Joueur"]==sel].set_index("Date")["Score"].dropna()
            if not df_z.empty: st.bar_chart(df_z,use_container_width=True)
        else:
            st.info("Aucun score sur cette période.")
    else:
        st.info("Aucune donnée. Lance une synchronisation.")

    st.markdown("---")

    # GW sauvegardées
    st.markdown("**📁 GW sauvegardées**")
    ca,cb = st.columns(2)
    with ca:
        lbl=st.text_input("Nom",placeholder="ex: GW Midweek mars")
        gs =st.date_input("Début",key="gs",value=today()-datetime.timedelta(days=6))
        ge =st.date_input("Fin",  key="ge",value=today()-datetime.timedelta(days=3))
        if st.button("💾 Sauvegarder"):
            if lbl: db.save_gameweek(lbl,gs.isoformat(),ge.isoformat()); st.success("✅"); st.rerun()
    with cb:
        saved=db.get_gameweeks()
        for g in saved:
            c1,c2=st.columns([3,1])
            c1.markdown(f"**{g['label']}**  \n`{g['start_date']}` → `{g['end_date']}`")
            if c2.button("🗑",key=f"del_{g['id']}"): db.delete_gameweek(g["id"]); st.rerun()
        if not saved: st.info("Aucune sauvegarde.")

    st.markdown("---")
    st.markdown("**🕐 Scheduler**")
    ok=sync._scheduler and sync._scheduler.running
    if ok:
        st.success("✅ Actif — toutes les heures · Europe/Paris")
        for j in sync._scheduler.get_jobs():
            st.code(f"Prochain run : {j.next_run_time}")
    else:
        st.warning("⚠️ Inactif.")
