"""
sync.py
Orchestre : récupère les stats MLB → calcule les scores Sorare → sauvegarde en DB.
Peut être appelé manuellement ou par le scheduler APScheduler.
"""

import datetime
import logging
import threading
from typing import Callable

from mlb_fetcher import get_player_stats_for_date, get_game_ids_for_date
from sorare_scoring import compute_score
import db

logger = logging.getLogger(__name__)

# Lock pour éviter les synchros concurrentes
_sync_lock = threading.Lock()

# Callback optionnel pour mettre à jour une barre de progression Streamlit
_progress_cb: Callable[[int, int, str], None] | None = None


def set_progress_callback(cb: Callable[[int, int, str], None]):
    global _progress_cb
    _progress_cb = cb


def _notify(current: int, total: int, msg: str):
    if _progress_cb:
        try:
            _progress_cb(current, total, msg)
        except Exception:
            pass


def sync_date(date: datetime.date, force: bool = False) -> dict:
    """
    Synchronise tous les joueurs du roster pour une date donnée.
    Retourne un résumé : {'synced': N, 'skipped': N, 'errors': N, 'no_game': N}
    """
    date_str = date.isoformat()

    if not force and db.is_date_synced(date_str):
        logger.info(f"[sync] {date_str} déjà synchro, skip (force={force})")
        return {"synced": 0, "skipped": 0, "errors": 0, "no_game": 0, "cached": True}

    if not _sync_lock.acquire(blocking=False):
        logger.warning("[sync] Synchro déjà en cours, ignorée.")
        return {"synced": 0, "skipped": 0, "errors": 0, "no_game": 0, "running": True}

    result = {"synced": 0, "skipped": 0, "errors": 0, "no_game": 0}
    try:
        roster = db.get_roster()
        if not roster:
            logger.warning("[sync] Roster vide, rien à synchroniser.")
            return result

        # Vérifier qu'il y a des matchs ce jour-là
        try:
            game_ids = get_game_ids_for_date(date)
        except Exception as e:
            logger.error(f"[sync] Impossible de récupérer les matchs : {e}")
            return {"synced": 0, "skipped": 0, "errors": 1, "no_game": 0, "error_msg": str(e)}

        total = len(roster)
        for i, player in enumerate(roster):
            pid   = player["player_id"]
            name  = player["name"]
            _notify(i, total, f"⏳ {name}…")

            if not game_ids:
                # Pas de matchs ce jour — on enregistre quand même pour ne pas re-fetcher
                db.upsert_no_game(pid, date_str)
                result["no_game"] += 1
                continue

            try:
                stats = get_player_stats_for_date(pid, date)
                if stats is None:
                    db.upsert_no_game(pid, date_str)
                    result["no_game"] += 1
                    logger.debug(f"[sync] {name} : pas joué le {date_str}")
                    continue

                scored = compute_score(stats)
                db.upsert_score(
                    player_id=pid,
                    date=date_str,
                    game_pk=stats.get("game_pk"),
                    role=stats.get("role", "hitter"),
                    total=scored["total"],
                    breakdown=scored["breakdown"],
                    raw_stats=stats,
                )
                # Mettre à jour le rôle dans le roster si le fetcher l'a détecté
                detected_role = stats.get("role", "")
                if detected_role and detected_role != player.get("role", ""):
                    db.update_player_role(pid, detected_role)
                    logger.info(f"[sync] Rôle mis à jour pour {name}: {detected_role}")
                result["synced"] += 1
                logger.info(f"[sync] {name} : {scored['total']} pts le {date_str}")

            except Exception as e:
                logger.error(f"[sync] Erreur pour {name} ({pid}) : {e}")
                result["errors"] += 1

        _notify(total, total, "✅ Terminé")
        return result

    finally:
        _sync_lock.release()


def sync_last_n_days(n: int = 7, force: bool = False) -> list[dict]:
    """Synchronise les N derniers jours (utile au premier démarrage)."""
    results = []
    import zoneinfo
    today = datetime.datetime.now(tz=zoneinfo.ZoneInfo("Europe/Paris")).date()
    for i in range(1, n + 1):
        d = today - datetime.timedelta(days=i)
        r = sync_date(d, force=force)
        r["date"] = d.isoformat()
        results.append(r)
    return results


# ─── Scheduler (APScheduler) ──────────────────────────────────────────────────
_scheduler = None


def start_scheduler():
    """Lance le scheduler : synchro auto toutes les heures, timezone Europe/Paris."""
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        import pytz
    except ImportError:
        logger.warning("[scheduler] APScheduler/pytz non installé, synchro auto désactivée.")
        return

    if _scheduler and _scheduler.running:
        logger.info("[scheduler] Déjà en cours.")
        return

    tz = pytz.timezone("Europe/Paris")
    _scheduler = BackgroundScheduler(timezone=tz)

    first_run = datetime.datetime.now(tz) + datetime.timedelta(seconds=30)

    _scheduler.add_job(
        _auto_sync_job,
        IntervalTrigger(hours=1, timezone=tz),
        id="mlb_sync_hourly",
        replace_existing=True,
        max_instances=1,
        next_run_time=first_run,
    )
    _scheduler.start()
    logger.info(f"[scheduler] Démarré — Europe/Paris, premier run dans 30s, puis toutes les heures")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] Arrêté.")


def _auto_sync_job():
    """Job automatique toutes les heures : synchro d'aujourd'hui et d'hier (Europe/Paris)."""
    import zoneinfo
    tz    = zoneinfo.ZoneInfo("Europe/Paris")
    now   = datetime.datetime.now(tz)
    today = now.date()
    yesterday = today - datetime.timedelta(days=1)

    logger.info(f"[auto_sync] Lancement — {now.strftime('%H:%M Europe/Paris')} "
                f"(today={today}, yesterday={yesterday})")

    for d in [today, yesterday]:
        try:
            r = sync_date(d, force=False)
            if r.get("cached"):
                logger.info(f"[auto_sync] {d} : déjà synchro, skip")
            else:
                logger.info(f"[auto_sync] {d} : "
                            f"{r.get('synced',0)} synchro, "
                            f"{r.get('no_game',0)} DNS, "
                            f"{r.get('errors',0)} erreurs")
        except Exception as e:
            logger.error(f"[auto_sync] Erreur pour {d}: {e}")
