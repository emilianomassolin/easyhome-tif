"""
Backfill de descripciones de ZonaProp (versión rápida con curl_cffi).

Las propiedades viejas de ZonaProp tienen como 'descripcion' solo el snippet
del título (~200 chars). Este script revisita la página de detalle, trae la
descripción completa (#longDescription) y, si es más larga, la actualiza y
marca la propiedad como no analizada para re-análisis posterior.

Usa curl_cffi (impersona el fingerprint TLS de Chrome) para pasar Cloudflare
sin un navegador headless -> ~0.5s por página y alta concurrencia sin thrashing.

Env: DATABASE_URL (prod vía túnel).
Uso: .venv/bin/python -m backend.scripts.backfill_zonaprop_desc [--workers N] [--min-len N]
"""
import argparse
import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup
from curl_cffi import requests as creq
from sqlalchemy import func

from backend.database.connection import SessionLocal
from backend.database.models import Property

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_stats = {"ok": 0, "sin_cambio": 0, "error": 0, "total": 0, "inicio": 0.0}
_lock = threading.Lock()
_local = threading.local()


def _session() -> creq.Session:
    s = getattr(_local, "s", None)
    if s is None:
        s = creq.Session(impersonate="chrome", timeout=30)
        _local.s = s
    return s


def _fetch(url: str, retries: int = 3) -> str | None:
    for intento in range(retries):
        try:
            r = _session().get(url)
            if r.status_code == 200:
                return r.text
            if r.status_code in (403, 429):
                time.sleep(1.5 * (intento + 1) + random.random())
        except Exception:
            time.sleep(1.0 * (intento + 1))
    return None


def _procesar(prop_id: int, permalink: str):
    html = _fetch(permalink)
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
        if hechas % 200 == 0:
            elapsed = time.time() - _stats["inicio"]
            rate = hechas / elapsed if elapsed else 0
            eta = int((_stats["total"] - hechas) / rate) if rate else 0
            logger.info(f"{hechas}/{_stats['total']} | ok={_stats['ok']} sin_cambio={_stats['sin_cambio']} "
                        f"err={_stats['error']} | {rate:.1f}/s | ETA {eta//60}m{eta%60}s")


def main(workers: int = 25, min_len: int = 300):
    db = SessionLocal()
    pendientes = db.query(Property.id, Property.permalink_ml).filter(
        Property.fuente == "zonaprop",
        Property.activa == True,
        Property.permalink_ml.like("http%"),
        func.length(func.coalesce(Property.descripcion, "")) < min_len,
    ).all()
    db.close()

    pendientes = [(pid, url) for pid, url in pendientes]
    _stats["total"] = len(pendientes)
    _stats["inicio"] = time.time()
    logger.info(f"Backfill ZonaProp (curl_cffi): {len(pendientes)} props | {workers} workers")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_procesar, pid, url) for pid, url in pendientes]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                logger.error(f"Error inesperado: {e}")

    logger.info(f"Backfill terminado. ok={_stats['ok']} sin_cambio={_stats['sin_cambio']} "
                f"err={_stats['error']} de {_stats['total']}.")
    return _stats["ok"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=25)
    parser.add_argument("--min-len", type=int, default=300)
    args = parser.parse_args()
    main(workers=args.workers, min_len=args.min_len)
