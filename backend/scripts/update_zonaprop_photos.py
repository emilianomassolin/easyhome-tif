"""
Actualiza fotos de ZonaProp existentes con ≤1 foto via FlareSolverr.
Usa múltiples workers en paralelo para mayor velocidad.

Uso:
    python -m backend.scripts.update_zonaprop_photos
    python -m backend.scripts.update_zonaprop_photos --workers 4 --delay 2.0
    python -m backend.scripts.update_zonaprop_photos --limit 1000 --workers 3
"""

import argparse
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, "/opt/easyhome")

from backend.database.connection import SessionLocal
from backend.database.models import Property

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [W%(worker)s] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/opt/easyhome/update_photos.log"),
    ],
)

# Logger raíz sin el campo worker (lo agregamos en cada thread)
root_logger = logging.getLogger(__name__)

FLARESOLVERR_URL = "http://localhost:8191/v1"
BASE_URL = "https://www.zonaprop.com.ar"


def _get_logger(worker_id: int):
    logger = logging.getLogger(f"worker_{worker_id}")
    if not logger.handlers:
        for h in logging.getLogger(__name__).handlers:
            logger.addHandler(h)
        logger.setLevel(logging.INFO)
    logger.worker = worker_id
    # Patch para incluir worker id en mensajes
    old_info = logger.info
    old_warn = logger.warning
    old_err = logger.error
    logger.info  = lambda msg, *a, **k: old_info(f"[W{worker_id}] {msg}", *a, **k)
    logger.warning = lambda msg, *a, **k: old_warn(f"[W{worker_id}] {msg}", *a, **k)
    logger.error = lambda msg, *a, **k: old_err(f"[W{worker_id}] {msg}", *a, **k)
    return logger


def _fs_create_session(session_id: str):
    try:
        requests.post(FLARESOLVERR_URL, json={"cmd": "sessions.create", "session": session_id}, timeout=30)
    except Exception:
        pass


def _fs_destroy_session(session_id: str):
    try:
        requests.post(FLARESOLVERR_URL, json={"cmd": "sessions.destroy", "session": session_id}, timeout=10)
    except Exception:
        pass


def _fs_get(session_id: str, url: str, retries: int = 3) -> str | None:
    for intento in range(retries):
        try:
            resp = requests.post(
                FLARESOLVERR_URL,
                json={"cmd": "request.get", "url": url, "session": session_id, "maxTimeout": 60000},
                timeout=90,
            )
            data = resp.json()
            if data.get("status") == "ok" and data.get("solution", {}).get("status") == 200:
                return data["solution"]["response"]
        except Exception:
            pass
        time.sleep(4 * (intento + 1))
    return None


def _extraer_fotos(html: str) -> list[str]:
    urls = re.findall(
        r"https://imgar\.zonapropcdn\.com/avisos/[^\s\"']+\.jpg(?:\?[^\s\"']*)?",
        html,
    )
    seen_ids: set[str] = set()
    result: list[str] = []
    for url in urls:
        base = url.split("?")[0]
        img_id = base.rsplit("/", 1)[-1]
        if "empresas" in url or "logo" in url.lower():
            continue
        if img_id not in seen_ids:
            seen_ids.add(img_id)
            url_norm = re.sub(r"/\d+x\d+/", "/720x532/", base)
            result.append(url_norm)
    return result[:20]


def _extraer_descripcion(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    desc_el = soup.find(class_=re.compile(r"[Dd]escription|[Dd]escripcion|[Dd]etalle"))
    if desc_el:
        return desc_el.get_text(separator=" ", strip=True)[:2000]
    return None


def _worker(worker_id: int, prop_ids: list[int], delay: float) -> tuple[int, int, int]:
    """Procesa un subconjunto de propiedades. Devuelve (actualizadas, sin_cambio, errores)."""
    logger = _get_logger(worker_id)
    session_id = f"zp_photo_w{worker_id}"
    _fs_create_session(session_id)
    logger.info(f"Iniciando. {len(prop_ids)} propiedades asignadas.")

    db = SessionLocal()
    actualizadas = sin_cambio = errores = 0

    try:
        for i, prop_id in enumerate(prop_ids):
            prop = db.query(Property).filter(Property.id == prop_id).first()
            if not prop or not prop.permalink_ml:
                continue

            try:
                html = _fs_get(session_id, prop.permalink_ml)
                if not html:
                    errores += 1
                    time.sleep(delay)
                    continue

                fotos = _extraer_fotos(html)
                if len(fotos) <= 1:
                    sin_cambio += 1
                    time.sleep(delay)
                    continue

                desc = _extraer_descripcion(html)

                prop.fotos_urls = fotos
                if desc and prop.descripcion != desc:
                    prop.descripcion = desc
                    prop.analizado = False

                db.commit()
                actualizadas += 1

                if (i + 1) % 50 == 0:
                    logger.info(f"Progreso: {i+1}/{len(prop_ids)} — {actualizadas} actualizadas, {errores} errores")

                time.sleep(delay)

            except Exception as e:
                logger.error(f"Error en prop {prop_id}: {e}")
                errores += 1
                db.rollback()
                time.sleep(delay * 2)

    finally:
        db.close()
        _fs_destroy_session(session_id)

    logger.info(f"Finalizado: {actualizadas} actualizadas, {sin_cambio} sin cambio, {errores} errores")
    return actualizadas, sin_cambio, errores


def main(limit: int | None, workers: int, delay: float):
    from sqlalchemy import text
    db = SessionLocal()
    rows = db.execute(
        text("""
            SELECT id FROM properties
            WHERE fuente = 'zonaprop'
              AND activa = true
              AND permalink_ml IS NOT NULL
              AND (fotos_urls IS NULL OR jsonb_array_length(fotos_urls) <= 1)
            ORDER BY id
            LIMIT :lim
        """),
        {"lim": limit or 999999},
    ).fetchall()
    db.close()

    prop_ids = [r[0] for r in rows]
    total = len(prop_ids)
    root_logger.info(f"Total propiedades a procesar: {total} | Workers: {workers} | Delay: {delay}s")

    if total == 0:
        root_logger.info("Nada que procesar.")
        return

    # Repartir IDs entre workers en round-robin para balancear carga
    chunks = [prop_ids[i::workers] for i in range(workers)]

    total_act = total_sin = total_err = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_worker, i, chunk, delay): i for i, chunk in enumerate(chunks)}
        for future in as_completed(futures):
            act, sin, err = future.result()
            total_act += act
            total_sin += sin
            total_err += err

    root_logger.info(
        f"\n=== COMPLETADO ===\n"
        f"  Procesadas:  {total}\n"
        f"  Actualizadas: {total_act}\n"
        f"  Sin cambio:   {total_sin}\n"
        f"  Errores:      {total_err}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers",  type=int,   default=4,   help="Workers paralelos (default: 4)")
    parser.add_argument("--delay",    type=float, default=2.0, help="Segundos entre requests por worker (default: 2.0)")
    parser.add_argument("--limit",    type=int,   default=None, help="Máx propiedades a procesar")
    args = parser.parse_args()
    main(limit=args.limit, workers=args.workers, delay=args.delay)
