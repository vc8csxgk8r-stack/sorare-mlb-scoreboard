"""
gameweek.py
Calcule les gameweeks Sorare MLB automatiquement.

Règle officielle Sorare MLB (bi-weekly) :
  GW "midweek" : Lundi → Jeudi  (4 jours)
  GW "weekend" : Vendredi → Dimanche (3 jours)

Toutes les dates sont manipulées en Europe/Paris (timezone de l'utilisateur).
La saison MLB commence fin mars, se termine fin septembre.
"""

import datetime
import zoneinfo

TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")
MLB_SEASON_START = datetime.date(2026, 3, 25)   # Opening Night 2026
MLB_SEASON_END   = datetime.date(2026, 9, 28)   # fin saison régulière 2026


def now_paris() -> datetime.datetime:
    return datetime.datetime.now(tz=TZ_PARIS)


def today_paris() -> datetime.date:
    return now_paris().date()


def _gw_bounds_for_date(d: datetime.date) -> tuple[datetime.date, datetime.date]:
    """
    Retourne (start, end) de la gameweek contenant la date d.
    Lundi(0)..Jeudi(3) → GW midweek : lundi au jeudi
    Vendredi(4)..Dimanche(6) → GW weekend : vendredi au dimanche
    """
    wd = d.weekday()  # 0=lundi … 6=dimanche
    if wd <= 3:  # lundi-jeudi
        start = d - datetime.timedelta(days=wd)        # lundi
        end   = start + datetime.timedelta(days=3)     # jeudi
    else:        # vendredi-dimanche
        start = d - datetime.timedelta(days=wd - 4)   # vendredi
        end   = start + datetime.timedelta(days=2)     # dimanche
    return start, end


def current_gw() -> dict:
    """GW en cours (basée sur aujourd'hui Paris)."""
    today = today_paris()
    start, end = _gw_bounds_for_date(today)
    label = _gw_label(start, end)
    return {
        "label":      label,
        "start_date": start.isoformat(),
        "end_date":   end.isoformat(),
        "type":       "midweek" if start.weekday() == 0 else "weekend",
        "is_current": True,
        "days_left":  max(0, (end - today).days),
    }


def previous_gw() -> dict:
    """GW précédente."""
    today = today_paris()
    start, end = _gw_bounds_for_date(today)
    # reculer d'un jour avant le début de la GW courante
    prev_day = start - datetime.timedelta(days=1)
    p_start, p_end = _gw_bounds_for_date(prev_day)
    return {
        "label":      _gw_label(p_start, p_end),
        "start_date": p_start.isoformat(),
        "end_date":   p_end.isoformat(),
        "type":       "midweek" if p_start.weekday() == 0 else "weekend",
        "is_current": False,
        "days_left":  0,
    }


def next_gw() -> dict:
    """GW suivante."""
    today = today_paris()
    start, end = _gw_bounds_for_date(today)
    next_day = end + datetime.timedelta(days=1)
    n_start, n_end = _gw_bounds_for_date(next_day)
    return {
        "label":      _gw_label(n_start, n_end),
        "start_date": n_start.isoformat(),
        "end_date":   n_end.isoformat(),
        "type":       "midweek" if n_start.weekday() == 0 else "weekend",
        "is_current": False,
        "days_left":  None,
    }


def list_gws_for_season(year: int = 2026) -> list[dict]:
    """Génère toutes les GW d'une saison MLB."""
    start = MLB_SEASON_START if year == 2026 else datetime.date(year, 3, 28)
    end   = MLB_SEASON_END   if year == 2026 else datetime.date(year, 9, 30)
    gws   = []
    cursor = start
    seen   = set()
    while cursor <= end:
        gs, ge = _gw_bounds_for_date(cursor)
        key = gs.isoformat()
        if key not in seen:
            seen.add(key)
            gws.append({
                "label":      _gw_label(gs, ge),
                "start_date": gs.isoformat(),
                "end_date":   ge.isoformat(),
                "type":       "midweek" if gs.weekday() == 0 else "weekend",
            })
        cursor = ge + datetime.timedelta(days=1)
    return gws


def _gw_label(start: datetime.date, end: datetime.date) -> str:
    FR_MONTHS = ["jan", "fév", "mar", "avr", "mai", "juin",
                 "juil", "août", "sep", "oct", "nov", "déc"]
    FR_DAYS   = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    gw_type   = "Midweek" if start.weekday() == 0 else "Weekend"
    s_str = f"{FR_DAYS[start.weekday()]} {start.day} {FR_MONTHS[start.month-1]}"
    e_str = f"{FR_DAYS[end.weekday()]} {end.day} {FR_MONTHS[end.month-1]}"
    return f"{gw_type} · {s_str} → {e_str}"
