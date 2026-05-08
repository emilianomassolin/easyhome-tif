import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.scrapers.mercadolibre_scraper import scrape_mercadolibre
from backend.scrapers.mendozaprop_scraper import scrape_mendozaprop
from backend.scrapers.zonaprop_scraper import scrape_zonaprop

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _run_all_sources():
    logger.info("=== Iniciando actualización de todas las fuentes ===")

    for nombre, funcion in [
        ("MercadoLibre", scrape_mercadolibre),
        ("MendozaProp",  scrape_mendozaprop),
        ("ZonaProp",     scrape_zonaprop),
    ]:
        try:
            saved = funcion()
            logger.info(f"{nombre}: {saved} propiedades nuevas.")
        except Exception as e:
            logger.error(f"{nombre} falló: {e}")

    logger.info("=== Actualización completada ===")


def start_scheduler():
    scheduler.add_job(
        func=_run_all_sources,
        trigger=IntervalTrigger(hours=24),
        id="fetch_all_sources",
        name="Fetch MercadoLibre + MendozaProp + ZonaProp cada 24hs",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler iniciado. Próxima actualización en 24 horas.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler detenido.")
