import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from backend.scrapers.mendozaprop_scraper import scrape_mendozaprop
from backend.scrapers.zonaprop_scraper import scrape_zonaprop
from backend.scrapers.argenprop_scraper import scrape_argenprop

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _run_all_sources():
    logger.info("=== Iniciando actualización de todas las fuentes ===")

    for nombre, funcion in [
        ("MendozaProp",  scrape_mendozaprop),
        ("ZonaProp",     scrape_zonaprop),
        ("Argenprop",    scrape_argenprop),
    ]:
        try:
            saved = funcion()
            logger.info(f"{nombre}: {saved} propiedades nuevas.")
        except Exception as e:
            logger.error(f"{nombre} falló: {e}")

    logger.info("=== Actualización completada ===")


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
