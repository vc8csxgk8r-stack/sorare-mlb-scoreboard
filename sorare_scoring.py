"""
sorare_scoring.py
Barême officiel Sorare MLB (hitters + pitchers).
Source : https://sorare.com/mlb/rules  (grille 2024-2025)
"""

# ─── HITTERS ──────────────────────────────────────────────────────────────────
HITTER_WEIGHTS = {
    # Offensif
    "single":          3.0,
    "double":          5.0,
    "triple":          8.0,
    "home_run":       10.0,
    "rbi":             3.5,
    "run":             3.0,
    "stolen_base":     5.0,
    "caught_stealing": -2.0,
    "walk":            2.0,
    "hit_by_pitch":    2.0,
    # Négatif
    "strikeout":      -1.5,
    "sacrifice_fly":   1.0,
}

# Bonus "hit" par tranche (optionnel Sorare — vérifiable in-app)
# 2H : +1, 3H: +2, 4H+: +3
HITTER_HIT_BONUS = {2: 1.0, 3: 2.0, 4: 3.0}

# ─── PITCHERS ─────────────────────────────────────────────────────────────────
PITCHER_WEIGHTS = {
    "inning_pitched":   2.25,   # par manche (fraction autorisée)
    "strikeout":        3.0,
    "walk":            -2.0,
    "hit_allowed":     -0.6,
    "earned_run":      -3.0,
    "home_run_allowed":-3.0,
    # Bonus résultat
    "win":              5.0,
    "loss":            -5.0,
    "save":             7.0,
    "hold":             4.0,
    "blown_save":      -4.0,
    # Bonus performance
    "complete_game":    5.0,
    "shutout":          5.0,    # s'additionne à complete_game
    "no_hitter":       15.0,    # s'additionne à shutout + complete_game
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

    def add(key, value, label=None):
        if value != 0:
            breakdown[label or key] = round(value, 2)

    add("single",          s.get("singles", 0)           * w["single"],      "Singles")
    add("double",          s.get("doubles", 0)           * w["double"],      "Doubles")
    add("triple",          s.get("triples", 0)           * w["triple"],      "Triples")
    add("home_run",        s.get("home_runs", 0)         * w["home_run"],    "Home Runs")
    add("rbi",             s.get("rbi", 0)               * w["rbi"],         "RBI")
    add("run",             s.get("runs", 0)              * w["run"],         "Runs")
    add("stolen_base",     s.get("stolen_bases", 0)      * w["stolen_base"], "Stolen Bases")
    add("caught_stealing", s.get("caught_stealing", 0)   * w["caught_stealing"], "Caught Stealing")
    add("walk",            s.get("walks_bat", 0)         * w["walk"],        "Walks")
    add("hit_by_pitch",    s.get("hit_by_pitch", 0)      * w["hit_by_pitch"],"Hit By Pitch")
    add("strikeout",       s.get("strikeouts_bat", 0)    * w["strikeout"],   "Strikeouts (K)")
    add("sacrifice_fly",   s.get("sacrifice_fly", 0)     * w["sacrifice_fly"],"Sacrifice Fly")

    # Bonus hits
    total_hits = s.get("hits", 0)
    for threshold in sorted(HITTER_HIT_BONUS.keys(), reverse=True):
        if total_hits >= threshold:
            bonus = HITTER_HIT_BONUS[threshold]
            breakdown[f"Hit Bonus ({threshold}H)"] = bonus
            break

    total = round(sum(breakdown.values()), 2)
    return {"breakdown": breakdown, "total": total}


def _score_pitcher(s: dict) -> dict:
    w = PITCHER_WEIGHTS
    breakdown = {}

    def add(key, value, label=None):
        if value != 0:
            breakdown[label or key] = round(value, 2)

    ip = s.get("innings_pitched", 0.0)
    add("ip",   ip                               * w["inning_pitched"],   f"IP ({ip:.2f})")
    add("k",    s.get("strikeouts", 0)           * w["strikeout"],        "Strikeouts (K)")
    add("bb",   s.get("walks", 0)                * w["walk"],             "Walks (BB)")
    add("h",    s.get("hits_allowed", 0)         * w["hit_allowed"],      "Hits Allowed")
    add("er",   s.get("earned_runs", 0)          * w["earned_run"],       "Earned Runs")
    add("hr",   s.get("home_runs_allowed", 0)    * w["home_run_allowed"], "HR Allowed")
    add("win",  s.get("wins", 0)                 * w["win"],              "Win")
    add("loss", s.get("losses", 0)               * w["loss"],             "Loss")
    add("sv",   s.get("saves", 0)                * w["save"],             "Save")
    add("hld",  s.get("holds", 0)                * w["hold"],             "Hold")
    add("bsv",  s.get("blown_saves", 0)          * w["blown_save"],       "Blown Save")
    add("cg",   s.get("complete_game", 0)        * w["complete_game"],    "Complete Game")
    add("sho",  s.get("shutout", 0)              * w["shutout"],          "Shutout")
    add("nh",   s.get("no_hitter", 0)            * w["no_hitter"],        "No-Hitter")

    total = round(sum(breakdown.values()), 2)
    return {"breakdown": breakdown, "total": total}
