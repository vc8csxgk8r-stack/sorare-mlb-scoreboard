"""
so7.py
Calcule la meilleure lineup So7 possible depuis le roster sur une plage de dates (gameweek).

Format So7 :
  SP    – Starting Pitcher (position: SP)
  RP    – Relief/Closer Pitcher (position: RP, CL)
  C/MI  – Catcher ou Middle Infielder (positions: C, 2B, SS)
  CI    – Corner Infielder (positions: 1B, 3B, DH)
  OF    – Outfielder (positions: LF, CF, RF, OF)
  XH    – Extra Hitter (n'importe quel hitter)
  FLEX  – Flex (n'importe qui, hitter ou pitcher)

Règles :
  - Chaque joueur ne peut occuper qu'UN seul slot
  - On cumule les scores sur tous les jours de la gameweek
  - On cherche la combinaison maximisant le total d'équipe
"""

from itertools import permutations
import db

# ─── Mapping position → slots éligibles ──────────────────────────────────────
# Clé = abréviation MLB officielle, Valeur = liste de slots So7 acceptables
POSITION_ELIGIBILITY: dict[str, list[str]] = {
    # Pitchers
    "SP":  ["SP", "FLEX"],
    "RP":  ["RP", "FLEX"],
    "CL":  ["RP", "FLEX"],
    "P":   ["SP", "RP", "FLEX"],  # générique
    # Catchers / Middle IF
    "C":   ["C_MI", "XH", "FLEX"],
    "2B":  ["C_MI", "XH", "FLEX"],
    "SS":  ["C_MI", "XH", "FLEX"],
    # Corner IF
    "1B":  ["CI", "XH", "FLEX"],
    "3B":  ["CI", "XH", "FLEX"],
    "DH":  ["CI", "XH", "FLEX"],
    # Outfield
    "LF":  ["OF", "XH", "FLEX"],
    "CF":  ["OF", "XH", "FLEX"],
    "RF":  ["OF", "XH", "FLEX"],
    "OF":  ["OF", "XH", "FLEX"],
    # Infield générique
    "IF":  ["C_MI", "CI", "XH", "FLEX"],
    "UTL": ["C_MI", "CI", "OF", "XH", "FLEX"],
}

SO7_SLOTS = ["SP", "RP", "C_MI", "CI", "OF", "XH", "FLEX"]

SLOT_LABELS = {
    "SP":   "⚾ Starting Pitcher",
    "RP":   "🔥 Relief Pitcher",
    "C_MI": "🎯 C / Middle IF",
    "CI":   "💪 Corner IF",
    "OF":   "🏃 Outfielder",
    "XH":   "🏏 Extra Hitter",
    "FLEX": "⚡ Flex",
}


def get_eligible_slots(position: str, role: str = "") -> list[str]:
    """
    Retourne les slots So7 éligibles.
    La position MLB est la source de vérité absolue.
    Si SP/RP/CL → slots pitcher, quelle que soit la valeur de role.
    """
    pos = position.upper().strip()
    # La position prime toujours sur le rôle
    slots = POSITION_ELIGIBILITY.get(pos)
    if slots:
        return slots
    # Position inconnue → fallback sur le rôle
    if role == "pitcher" or pos in PITCHER_POSITIONS:
        return ["SP", "RP", "FLEX"]
    return ["XH", "FLEX"]


PITCHER_POSITIONS = {"SP", "RP", "CL", "P", "TWP", "LHP", "RHP"}

def _role_from_position(position: str, fallback: str = "hitter") -> str:
    """Dérive le rôle depuis la position MLB. Plus fiable que le champ role du roster."""
    return "pitcher" if position.upper() in PITCHER_POSITIONS else fallback


def compute_gameweek_scores(start_date: str, end_date: str) -> list[dict]:
    """
    Cumule les scores sur la plage de dates.
    Le rôle est dérivé de la POSITION MLB (SP/RP → pitcher),
    ce qui est plus fiable que le champ role qui peut être mal défini.
    """
    roster = db.get_roster()
    result = []

    for player in roster:
        pid      = player["player_id"]
        position = player.get("position", "?")
        # Rôle dérivé de la position en priorité, fallback sur le champ role
        role     = _role_from_position(position, fallback=player.get("role","hitter"))

        scores   = db.get_scores_range(pid, start_date, end_date)
        played   = [s for s in scores if s.get("total") is not None]

        total_gw     = round(sum(s["total"] for s in played), 2)
        games_played = len(played)
        days_detail  = {s["date"]: s.get("total") for s in scores}

        result.append({
            "player_id":      pid,
            "name":           player["name"],
            "position":       position,
            "role":           role,
            "team":           player.get("team", ""),
            "total_gw":       total_gw,
            "games_played":   games_played,
            "days":           days_detail,
            "eligible_slots": get_eligible_slots(position, role),
        })

    return sorted(result, key=lambda x: x["total_gw"], reverse=True)


def optimize_so7(player_scores: list[dict]) -> dict | None:
    """
    Algorithme glouton + backtracking léger pour trouver la meilleure lineup So7.

    Retourne un dict :
      {
        "lineup": { slot: player_dict },
        "total":  float,
        "bench":  [player_dict, ...]   ← joueurs non sélectionnés
      }
    ou None si roster insuffisant.
    """
    # On trie par score décroissant — les meilleurs en premier
    players = sorted(player_scores, key=lambda x: x["total_gw"], reverse=True)

    best_result = _backtrack(players, SO7_SLOTS, {}, set())
    if best_result is None:
        return None

    lineup, used_ids = best_result
    bench = [p for p in players if p["player_id"] not in used_ids]
    total = sum(lineup[slot]["total_gw"] for slot in lineup)

    return {
        "lineup": lineup,
        "total":  round(total, 2),
        "bench":  bench,
    }


def _backtrack(
    players: list[dict],
    remaining_slots: list[str],
    current_lineup: dict,
    used_ids: set,
) -> tuple[dict, set] | None:
    """
    Backtracking récursif.
    remaining_slots = slots encore à remplir, dans l'ordre de priorité.
    Retourne (lineup_dict, used_ids) ou None.
    """
    if not remaining_slots:
        return current_lineup.copy(), used_ids.copy()

    slot = remaining_slots[0]
    rest = remaining_slots[1:]

    best_total = -1e9
    best_solution = None

    for player in players:
        pid = player["player_id"]
        if pid in used_ids:
            continue
        if slot not in player["eligible_slots"]:
            continue

        # Essayer ce joueur dans ce slot
        used_ids.add(pid)
        current_lineup[slot] = player

        solution = _backtrack(players, rest, current_lineup, used_ids)
        if solution is not None:
            lineup_sol, used_sol = solution
            sol_total = sum(lineup_sol[s]["total_gw"] for s in lineup_sol)
            if sol_total > best_total:
                best_total = sol_total
                best_solution = (lineup_sol, used_sol)

        used_ids.remove(pid)
        del current_lineup[slot]

    return best_solution


def _slot_priority_order() -> list[str]:
    """
    Ordre dans lequel on remplit les slots.
    Les slots les plus contraints (SP, RP) en premier pour éviter de les bloquer.
    """
    return ["SP", "RP", "C_MI", "CI", "OF", "XH", "FLEX"]
