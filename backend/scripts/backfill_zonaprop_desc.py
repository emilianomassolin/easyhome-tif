"""
Backfill de descripciones de ZonaProp.

Las propiedades viejas de ZonaProp tienen como 'descripcion' solo el snippet
del título (~200 chars) porque el scraper extraía mal la descripción del
detalle. Este script revisita la página de detalle de cada propiedad ZonaProp
con descripción corta, trae la descripción completa (#longDescription) y, si es
más larga, la actualiza y marca la propiedad como no analizada para que el
próximo análisis la procese con el texto real.

Solo usa FlareSolverr (no depende de la API de NLP).

Uso: .venv/bin/python -m backend.scripts.backfill_zonaprop_desc [--workers N] [--min-len N]
"""
import argparse
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from backend.database.connection import SessionLocal
from backend.database.models import Property
from backend.scrapers.zonaprop_scraper import _fs_get, FLARESOLVERR_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_stats = {"ok": 0, "sin_cambio": 0, "error": 0, "total": 0}
_lock = threading.Lock()


def _crear_sesion(session_id: str):
    try:
        requests.post(FLARESOLVERR_URL, json={"cmd": "sessions.create", "session": session_id}, timeout=60)
    except Exception as e:
        logger.warning(f"No se pudo crear sesión {session_id}: {e}")


def _destruir_sesion(session_id: str):
    try:
        requests.post(FLARESOLVERR_URL, json={"cmd": "sessions.destroy", "session": session_id}, timeout=30)
    except Exception:
        pass


def _procesar(prop_id: int, permalink: str, session_id: str):
    html = _fs_get(session_id, permalink)
    if not html:
        with _lock:
            _stats["error"] += 1
        return

    soup = BeautifulSoup(html, "html.parser")
    desc_el = soup.find(id="longDescription") or soup.find(id="reactDescription")
    if not desc_el:
        with _lock:
            _stats["error"] += 1
        return

    texto = desc_el.get_text(separator=" ", strip=True)[:2000]

    db = SessionLocal()
    try:
        prop = db.query(Property).filter(Property.id == prop_id).first()
        if prop and len(texto) > len(prop.descripcion or ""):
            prop.descripcion = texto
            prop.analizado = False
            prop.fecha_analisis = None
            db.commit()
            with _lock:
                _stats["ok"] += 1
        else:
            with _lock:
                _stats["sin_cambio"] += 1
    except Exception as e:
        db.rollback()
        logger.error(f"Error guardando prop {prop_id}: {e}")
        with _lock:
            _stats["error"] += 1
    finally:
        db.close()

    with _lock:
        hechas = _stats["ok"] + _stats["sin_cambio"] + _stats["error"]
        if hechas % 50 == 0:
            logger.info(f"Progreso: {hechas}/{_stats['total']} | actualizadas={_stats['ok']} "
                        f"sin_cambio={_stats['sin_cambio']} error={_stats['error']}")
    time.sleep(0.5)


def main(workers: int = 3, min_len: int = 300):
    from sqlalchemy import func
    db = SessionLocal()
    # Solo las que tienen descripción corta (snippet del título); las que ya
    # tienen descripción completa (scrapeadas con el fix nuevo) se saltean.
    pendientes = db.query(Property.id, Property.permalink_ml).filter(
        Property.fuente == "zonaprop",
        Property.activa == True,
        Property.permalink_ml.like("http%"),
        func.length(func.coalesce(Property.descripcion, "")) < min_len,
    ).all()
    db.close()

    pendientes = [(pid, url) for pid, url in pendientes]
    _stats["total"] = len(pendientes)
    logger.info(f"Backfill ZonaProp: {len(pendientes)} propiedades a revisar con {workers} workers.")

    sesiones = [f"zp_bf_w{i}" for i in range(workers)]
    for s in sesiones:
        _crear_sesion(s)

    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [
                ex.submit(_procesar, pid, url, sesiones[i % workers])
                for i, (pid, url) in enumerate(pendientes)
            ]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    logger.error(f"Error inesperado: {e}")
    finally:
        for s in sesiones:
            _destruir_sesion(s)

    logger.info(f"Backfill terminado. actualizadas={_stats['ok']} sin_cambio={_stats['sin_cambio']} "
                f"error={_stats['error']} de {_stats['total']}.")
    return _stats["ok"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--min-len", type=int, default=300, help="Solo revisar descripciones más cortas que esto")
    args = parser.parse_args()
    main(workers=args.workers, min_len=args.min_len)
