"""
Actualiza las fotos de propiedades ZonaProp existentes que solo tienen 1 foto.
Visita cada página de detalle via FlareSolverr y extrae todas las imágenes.

Uso:
    python -m backend.scripts.update_zonaprop_photos
    python -m backend.scripts.update_zonaprop_photos --limit 500
    python -m backend.scripts.update_zonaprop_photos --batch-size 50 --delay 2.0
"""

import argparse
import logging
import re
import sys
import time

import requests
from bs4 import BeautifulSoup
from sqlalchemy import and_

sys.path.insert(0, "/opt/easyhome")

from backend.database.connection import SessionLocal
from backend.database.models import Property

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/opt/easyhome/update_photos.log"),
    ],
)
logger = logging.getLogger(__name__)

FLARESOLVERR_URL = "http://localhost:8191/v1"
BASE_URL = "https://www.zonaprop.com.ar"
SESSION_ID = "zp_photo_update"


def _fs_get(url: str, retries: int = 3) -> str | None:
    for intento in range(retries):
        try:
            resp = requests.post(
                FLARESOLVERR_URL,
                json={"cmd": "request.get", "url": url, "session": SESSION_ID, "maxTimeout": 60000},
                timeout=90,
            )
            data = resp.json()
            if data.get("status") == "ok" and data.get("solution", {}).get("status") == 200:
                return data["solution"]["response"]
            logger.warning(f"FlareSolverr error en {url}: {data.get('message') or data.get('solution',{}).get('status')}")
        except Exception as e:
            logger.warning(f"Request error (intento {intento+1}): {e}")
        time.sleep(5 * (intento + 1))
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


def main(limit: int | None, batch_size: int, delay: float):
    # Crear sesión FlareSolverr
    try:
        requests.post(FLARESOLVERR_URL, json={"cmd": "sessions.create", "session": SESSION_ID}, timeout=30)
        logger.info("Sesión FlareSolverr creada.")
    except Exception as e:
        logger.error(f"No se pudo crear sesión FlareSolverr: {e}")
        return

    db = SessionLocal()

    # Propiedades ZonaProp activas con solo 1 foto o sin fotos
    query = db.query(Property).filter(
        and_(
            Property.fuente == "zonaprop",
            Property.activa == True,
            Property.permalink_ml.isnot(None),
        )
    )
    # Filtrar las que tienen 1 o 0 fotos (jsonb array length)
    from sqlalchemy import func, cast
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy import text

    # Usar SQL raw para filtrar por longitud del array JSONB
    props = db.execute(
        text("""
            SELECT id, permalink_ml, fotos_urls
            FROM properties
            WHERE fuente = 'zonaprop'
              AND activa = true
              AND permalink_ml IS NOT NULL
              AND (fotos_urls IS NULL OR jsonb_array_length(fotos_urls) <= 1)
            ORDER BY id
            LIMIT :lim
        """),
        {"lim": limit or 999999},
    ).fetchall()

    total = len(props)
    logger.info(f"Propiedades a actualizar: {total}")

    actualizadas = 0
    sin_cambio = 0
    errores = 0

    for i, row in enumerate(props):
        prop_id, permalink, _ = row

        try:
            html = _fs_get(permalink)
            if not html:
                logger.warning(f"[{i+1}/{total}] Sin respuesta para {permalink}")
                errores += 1
                continue

            fotos = _extraer_fotos(html)

            if len(fotos) <= 1:
                sin_cambio += 1
                logger.debug(f"[{i+1}/{total}] ID {prop_id}: solo {len(fotos)} foto(s) en detalle.")
                time.sleep(delay)
                continue

            desc = _extraer_descripcion(html)

            db.execute(
                text("""
                    UPDATE properties
                    SET fotos_urls = CAST(:fotos AS jsonb),
                        descripcion = COALESCE(:desc, descripcion),
                        analizado = CASE WHEN :desc IS NOT NULL AND descripcion IS DISTINCT FROM :desc THEN false ELSE analizado END
                    WHERE id = :id
                """),
                {
                    "fotos": __import__("json").dumps(fotos),
                    "desc": desc,
                    "id": prop_id,
                },
            )
            actualizadas += 1

            if actualizadas % batch_size == 0:
                db.commit()
                logger.info(f"  Progreso: {i+1}/{total} procesadas, {actualizadas} actualizadas, {errores} errores.")

            time.sleep(delay)

        except Exception as e:
            logger.error(f"[{i+1}/{total}] Error en ID {prop_id}: {e}")
            errores += 1
            db.rollback()
            time.sleep(delay * 2)

    db.commit()
    db.close()

    logger.info(
        f"\n=== Finalizado ===\n"
        f"  Total procesadas: {total}\n"
        f"  Actualizadas con más fotos: {actualizadas}\n"
        f"  Sin cambio (1 foto en detalle): {sin_cambio}\n"
        f"  Errores: {errores}"
    )

    # Destruir sesión
    try:
        requests.post(FLARESOLVERR_URL, json={"cmd": "sessions.destroy", "session": SESSION_ID}, timeout=10)
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Actualiza fotos ZonaProp vía FlareSolverr")
    parser.add_argument("--limit", type=int, default=None, help="Máximo de propiedades a procesar")
    parser.add_argument("--batch-size", type=int, default=50, help="Commit cada N propiedades (default: 50)")
    parser.add_argument("--delay", type=float, default=2.0, help="Segundos entre requests (default: 2.0)")
    args = parser.parse_args()

    main(limit=args.limit, batch_size=args.batch_size, delay=args.delay)
