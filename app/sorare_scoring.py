"""
sorare_scoring.py
Barême officiel Sorare MLB (hitters + pitchers).
Source vérifiée : sorarescout.com/mlb + sorare.com/help (2022-2025, inchangé)

HITTERS
  Run (R)           +3
  RBI               +3
  Single (1B)       +2
  Double (2B)       +5
  Triple (3B)       +8
  Home Run (HR)    +10
  Walk (BB)         +2
  Strikeout (K)     -1
  Stolen Base (SB)  +5
  Hit By Pitch(HBP) +2

PITCHERS
  Inning Pitched   +3     (par manche complète ou fraction)
  Strikeout (K)    +2
  Hit Allowed (H)  -0.5
  Earned Run (ER)  -2
  Walk (BB)        -1
  Hit Batsman(HBP) -1
  Win (W)          +5
  Save (S)         +10
  Hold (HLD)       +5
"""

# ─── HITTERS ──────────────────────────────────────────────────────────────────
HITTER_WEIGHTS = {
    "single":          2.0,    # ✅ officiel +2 (était +3 — CORRIGÉ)
    "double":          5.0,
    "triple":          8.0,
    "home_run":       10.0,
    "rbi":             3.0,    # ✅ officiel +3 (était +3.5 — CORRIGÉ)
    "run":             3.0,
    "stolen_base":     5.0,
    "walk":            2.0,
    "hit_by_pitch":    2.0,
    "strikeout":      -1.0,    # ✅ officiel -1 (était -1.5 — CORRIGÉ)
    # Caught stealing et sacrifice fly ne figurent pas dans le barême officiel publié
    "caught_stealing": 0.0,
    "sacrifice_fly":   0.0,
}

# Pas de bonus hits dans le barême officiel publié — désactivé
HITTER_HIT_BONUS = {}

# ─── PITCHERS ─────────────────────────────────────────────────────────────────
PITCHER_WEIGHTS = {
    "inning_pitched":   3.0,    # ✅ officiel +3/IP (était +2.25 — CORRIGÉ)
    "strikeout":        2.0,    # ✅ officiel +2 (était +3 — CORRIGÉ)
    "walk":            -1.0,    # ✅ officiel -1 (était -2 — CORRIGÉ)
    "hit_allowed":     -0.5,    # ✅ officiel -0.5 (était -0.6 — CORRIGÉ)
    "earned_run":      -2.0,    # ✅ officiel -2 (était -3 — CORRIGÉ)
    "home_run_allowed": 0.0,    # non listé séparément dans le barême officiel
    "hit_batsman":     -1.0,    # ✅ officiel -1 (manquait — AJOUTÉ)
    # Bonus résultat
    "win":              5.0,
    "loss":             0.0,    # non listé dans le barême officiel
    "save":            10.0,    # ✅ officiel +10 (était +7 — CORRIGÉ)
    "hold":             5.0,    # ✅ officiel +5 (était +4 — CORRIGÉ)
    "blown_save":       0.0,    # non listé dans le barême officiel
    # Bonus performance — non listés officiellement, désactivés
    "complete_game":    0.0,
    "shutout":          0.0,
    "no_hitter":        0.0,
}

# ─── Calcul ───────────────────────────────────────────────────────────────────
def compute_score(stats: dict) -> dict:
    """
    Prend un dict de stats (issu de mlb_fetcher) et retourne un dict avec :
      - breakdown : dict action → points
      - total     : score Sorare final (arrondi 2 décimales)
    """
    role = stats.get("role", "hitter")

    if role == "pitcher":
        return _score_pitcher(stats)
    else:
        return _score_hitter(stats)


def _score_hitter(s: dict) -> dict:
    w = HITTER_WEIGHTS
    breakdown = {}

    def add(label, value):
        if value != 0:
            breakdown[label] = round(value, 2)

    add("Singles",        s.get("singles", 0)        * w["single"])
    add("Doubles",        s.get("doubles", 0)        * w["double"])
    add("Triples",        s.get("triples", 0)        * w["triple"])
    add("Home Runs",      s.get("home_runs", 0)      * w["home_run"])
    add("RBI",            s.get("rbi", 0)            * w["rbi"])
    add("Runs",           s.get("runs", 0)           * w["run"])
    add("Stolen Bases",   s.get("stolen_bases", 0)   * w["stolen_base"])
    add("Walks (BB)",     s.get("walks_bat", 0)      * w["walk"])
    add("Hit By Pitch",   s.get("hit_by_pitch", 0)   * w["hit_by_pitch"])
    add("Strikeouts (K)", s.get("strikeouts_bat", 0) * w["strikeout"])

    total = round(sum(breakdown.values()), 2)
    return {"breakdown": breakdown, "total": total}


def _score_pitcher(s: dict) -> dict:
    w = PITCHER_WEIGHTS
    breakdown = {}

    def add(label, value):
        if value != 0:
            breakdown[label] = round(value, 2)

    ip = s.get("innings_pitched", 0.0)
    add(f"IP ({ip:.2f})",    ip                            * w["inning_pitched"])
    add("Strikeouts (K)",    s.get("strikeouts", 0)        * w["strikeout"])
    add("Walks (BB)",        s.get("walks", 0)             * w["walk"])
    add("Hits Allowed",      s.get("hits_allowed", 0)      * w["hit_allowed"])
    add("Earned Runs",       s.get("earned_runs", 0)       * w["earned_run"])
    add("Hit Batsmen (HBP)", s.get("hit_batsmen", 0)       * w["hit_batsman"])
    add("Win",               s.get("wins", 0)              * w["win"])
    add("Save",              s.get("saves", 0)             * w["save"])
    add("Hold",              s.get("holds", 0)             * w["hold"])

    total = round(sum(breakdown.values()), 2)
    return {"breakdown": breakdown, "total": total}
