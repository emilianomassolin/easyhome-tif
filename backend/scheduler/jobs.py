import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from backend.scrapers.mendozaprop_scraper import scrape_mendozaprop
from backend.scrapers.zonaprop_scraper import scrape_zonaprop
from backend.scrapers.argenprop_scraper import scrape_argenprop

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _run_all_sources():
    logger.info("=== Iniciando actualización de todas las fuentes ===")

    for fuente, nombre, funcion in [
        ("mendozaprop", "MendozaProp", scrape_mendozaprop),
        ("zonaprop",    "ZonaProp",    scrape_zonaprop),
        ("argenprop",   "Argenprop",   scrape_argenprop),
    ]:
        _run_scraper_logged(fuente, nombre, funcion)

    _record_snapshots()
    logger.info("=== Actualización completada ===")


def _run_scraper_logged(fuente: str, nombre: str, funcion):
    """Corre un scraper y registra un ScraperLog, igual que el endpoint manual,
    para que las corridas automáticas también aparezcan en el dashboard."""
    from backend.database.connection import SessionLocal
    from backend.database.models import ScraperLog
    db = SessionLocal()
    log = ScraperLog(fuente=fuente, inicio=datetime.now(timezone.utc), estado="running", cantidad=0)
    db.add(log)
    db.commit()
    db.refresh(log)
    try:
        saved = funcion()
        log.fin = datetime.now(timezone.utc)
        log.estado = "ok"
        log.cantidad = saved or 0
        db.commit()
        logger.info(f"{nombre}: {saved} propiedades nuevas.")
    except Exception as e:
        log.fin = datetime.now(timezone.utc)
        log.estado = "error"
        log.mensaje_error = str(e)
        db.commit()
        logger.error(f"{nombre} falló: {e}")
    finally:
        db.close()


def _record_snapshots():
    """Graba un snapshot diario de todas las fuentes para el timeline."""
    from backend.api.admin_routes import _record_snapshot
    from backend.database.connection import SessionLocal
    db = SessionLocal()
    try:
        for fuente in ["mendozaprop", "zonaprop", "argenprop"]:
            _record_snapshot(db, fuente)
        logger.info("Snapshots de timeline grabados.")
    except Exception as e:
        logger.error(f"Error grabando snapshots: {e}")
    finally:
        db.close()


def start_scheduler():
    # Hora fija (06:00 UTC = 03:00 Argentina) en vez de intervalo: un intervalo
    # arranca a contar desde el inicio del servicio, así que cada deploy/reinicio
    # reseteaba el timer y el scraping nunca llegaba a ejecutarse.
    scheduler.add_job(
        func=_run_all_sources,
        trigger=CronTrigger(hour=6, minute=0),
        id="fetch_all_sources",
        name="Fetch MendozaProp + ZonaProp + Argenprop diario a las 03:00 ART",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler iniciado. Scraping diario a las 06:00 UTC (03:00 ART).")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler detenido.")
