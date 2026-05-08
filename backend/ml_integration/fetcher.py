import logging
import time

import requests

from backend.database.connection import SessionLocal
from backend.database.models import Property
from backend.ml_integration.auth import get_auth_headers

logger = logging.getLogger(__name__)

MELI_SEARCH_URL = "https://api.mercadolibre.com/sites/MLA/search"
MELI_ITEMS_URL  = "https://api.mercadolibre.com/items"

SEARCH_PARAMS = {
    "category": "MLA1459",
    "state":    "AR-M",
    "limit":    50,
}

MAX_DAILY_CALLS = 14_000
_daily_calls = 0


def _request(url: str, params: dict = None, retries: int = 3) -> requests.Response | None:
    global _daily_calls

    if _daily_calls >= MAX_DAILY_CALLS:
        raise RuntimeError("Límite diario de llamadas a MercadoLibre alcanzado.")

    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=get_auth_headers(), timeout=15)
            _daily_calls += 1

            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                logger.warning(f"Rate limit. Esperando {wait}s...")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp

        except requests.HTTPError as e:
            if e.response.status_code == 403:
                logger.error("API de MercadoLibre respondió 403. Verificá acceso al endpoint.")
                return None
            raise
        except requests.Timeout:
            logger.warning(f"Timeout (intento {attempt + 1}/{retries})")
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)

    return None


def _get_descriptions_bulk(ml_ids: list[str]) -> dict[str, str | None]:
    """Obtiene descripciones en bulk usando multiget."""
    if not ml_ids:
        return {}

    results = {}
    chunk_size = 20
    for i in range(0, len(ml_ids), chunk_size):
        chunk = ml_ids[i:i + chunk_size]
        resp = _request(MELI_ITEMS_URL, params={"ids": ",".join(chunk)})
        if not resp:
            for mid in chunk:
                results[mid] = None
            continue
        for entry in resp.json():
            mid  = entry.get("body", {}).get("id", "")
            desc = entry.get("body", {}).get("plain_text")
            results[mid] = desc
    return results


def _build_location(item: dict) -> str | None:
    address = item.get("seller_address", {})
    parts = [
        address.get("city", {}).get("name"),
        address.get("state", {}).get("name"),
    ]
    return ", ".join(p for p in parts if p) or None


def fetch_properties() -> int:
    logger.info("Iniciando fetch de propiedades desde MercadoLibre...")
    db = SessionLocal()
    saved = 0

    try:
        offset = 0
        while True:
            resp = _request(MELI_SEARCH_URL, params={**SEARCH_PARAMS, "offset": offset})
            if not resp:
                logger.warning("Sin respuesta del search. Abortando fetch.")
                break

            data  = resp.json()
            items = data.get("results", [])
            if not items:
                break

            # Filtrar solo los que no existen aún
            new_items = [
                item for item in items
                if not db.query(Property).filter_by(ml_id=item["id"]).first()
            ]

            # Obtener descripciones en bulk
            descriptions = _get_descriptions_bulk([it["id"] for it in new_items])

            for item in new_items:
                ml_id = item["id"]

                fotos = [
                    pic.get("secure_url") or pic.get("url")
                    for pic in item.get("pictures", [])
                    if pic.get("secure_url") or pic.get("url")
                ]
                if not fotos and item.get("thumbnail"):
                    fotos = [item["thumbnail"]]

                db.add(Property(
                    ml_id=ml_id,
                    titulo=item.get("title", "Sin título"),
                    precio=item.get("price"),
                    descripcion=descriptions.get(ml_id),
                    ubicacion=_build_location(item),
                    permalink_ml=item.get("permalink", ""),
                    fotos_urls=fotos or None,
                ))
                saved += 1

            db.commit()

            total  = data.get("paging", {}).get("total", 0)
            offset += len(items)
            if offset >= total:
                break

    except RuntimeError as e:
        logger.warning(str(e))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error durante el fetch: {e}")
        raise
    finally:
        db.close()

    logger.info(f"Fetch completado. Propiedades nuevas: {saved}")
    return saved
