import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from backend.database.connection import SessionLocal
from backend.database.models import Property

logger = logging.getLogger(__name__)

BASE_URL = "https://www.mendozaprop.com"
API_URL  = f"{BASE_URL}/api/properties"
OPERATION_TYPES = [1, 2]  # 1=alquiler, 2=venta
PAGE_SIZE = 50
DELAY_BETWEEN_REQUESTS = 0.3


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[áàä]", "a", text)
    text = re.sub(r"[éèë]", "e", text)
    text = re.sub(r"[íìï]", "i", text)
    text = re.sub(r"[óòö]", "o", text)
    text = re.sub(r"[úùü]", "u", text)
    text = re.sub(r"[ñ]", "n", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _build_permalink(item: dict) -> str:
    tipo_op   = _slugify(item.get("transaction_type_name", "propiedad"))
    tipo_prop = _slugify(item.get("property_type_name", ""))
    owner     = _slugify(item.get("owner_company", ""))
    prop_id   = item["id"]
    slug = f"{tipo_op}-{tipo_prop}-{owner}".strip("-")
    return f"{BASE_URL}/{slug}/{prop_id}"


def _build_descripcion(item: dict) -> str | None:
    partes = []

    caract = []
    if item.get("bedrooms"):
        caract.append(f"{item['bedrooms']} habitaciones")
    if item.get("bathrooms"):
        caract.append(f"{item['bathrooms']} baños")
    if item.get("parking"):
        caract.append(f"{item['parking']} cocheras")
    if item.get("m2_covered"):
        caract.append(f"{item['m2_covered']} m² Cub.")
    if item.get("m2"):
        caract.append(f"{item['m2']} m² Tot.")
    if caract:
        partes.append(" - ".join(caract))

    desc = (item.get("description") or "").strip()
    if desc:
        partes.append(desc)

    return "\n\n".join(partes) if partes else None


def _fetch_page(op_type: int, offset: int) -> list[dict]:
    try:
        resp = requests.get(
            API_URL,
            params={"limit": PAGE_SIZE, "offset": offset, "isMap": "false", "operationType": op_type},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json() or []
    except Exception as e:
        logger.warning(f"Error fetching offset {offset} operationType {op_type}: {e}")
        return []


def _scrape_op_type(op_type: int) -> tuple[int, set[str]]:
    """Scrapes un tipo de operación con su propia sesión DB. Pensado para correr en thread."""
    db = SessionLocal()
    saved = 0
    ids_vistos: set[str] = set()
    op_nombre = "alquiler" if op_type == 1 else "venta"
    tipo_op = op_nombre

    try:
        logger.info(f"MendozaProp scrapeando: {op_nombre} (operationType={op_type})...")
        offset = 0
        total_encontradas = 0

        while True:
            items = _fetch_page(op_type, offset)
            if not items:
                break

            for item in items:
                prop_id = f"mzprop-{item['id']}"
                existing = db.query(Property).filter_by(ml_id=prop_id).first()

                precio = float(item["price"]) if item.get("price") else None
                descripcion = _build_descripcion(item)
                fotos = item.get("images") or []
                ubicacion = (item.get("address") or "Mendoza").strip()
                titulo = (item.get("title") or item.get("property_type_name") or "Sin título").strip()
                permalink = _build_permalink(item)

                ids_vistos.add(prop_id)
                if existing:
                    existing.activa = True
                    existing.tipo_operacion = tipo_op
                    if existing.precio != precio:
                        existing.precio = precio
                    if descripcion and existing.descripcion != descripcion:
                        existing.descripcion = descripcion
                        existing.analizado = False
                    if fotos and existing.fotos_urls != fotos:
                        existing.fotos_urls = fotos
                else:
                    db.add(Property(
                        ml_id=prop_id,
                        titulo=titulo,
                        precio=precio,
                        descripcion=descripcion,
                        ubicacion=ubicacion,
                        permalink_ml=permalink,
                        fotos_urls=fotos if fotos else None,
                        fuente="mendozaprop",
                        tipo_operacion=tipo_op,
                        activa=True,
                    ))
                saved += 1

            total_encontradas += len(items)
            db.commit()
            offset += PAGE_SIZE
            time.sleep(DELAY_BETWEEN_REQUESTS)

            if len(items) < PAGE_SIZE:
                break

        logger.info(f"  MendozaProp {op_nombre}: {total_encontradas} propiedades procesadas.")

    except Exception as e:
        db.rollback()
        logger.error(f"Error en scraping MendozaProp [{op_nombre}]: {e}")
    finally:
        db.close()

    return saved, ids_vistos


def scrape_mendozaprop() -> int:
    logger.info("Iniciando scraping de MendozaProp (venta + alquiler en paralelo)...")
    total_saved = 0
    ids_vistos: set[str] = set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(_scrape_op_type, op): op for op in OPERATION_TYPES}
        for future in as_completed(futures):
            try:
                saved, ids_op = future.result()
                total_saved += saved
                ids_vistos.update(ids_op)
            except Exception as e:
                logger.error(f"MendozaProp thread error: {e}")

    if ids_vistos:
        db = SessionLocal()
        inactivadas = db.query(Property).filter(
            Property.fuente == "mendozaprop",
            ~Property.ml_id.in_(ids_vistos),
        ).update({"activa": False}, synchronize_session=False)
        db.commit()
        db.close()
        logger.info(f"MendozaProp: {inactivadas} propiedades no vistas marcadas como inactivas.")

    logger.info(f"MendozaProp: {total_saved} propiedades nuevas/actualizadas.")
    return total_saved
