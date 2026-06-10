import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from backend.database.connection import SessionLocal
from backend.database.models import Property
from backend.scrapers.dedup_utils import find_canonical
from backend.scrapers.extract_utils import extraer_superficie, extraer_ambientes

logger = logging.getLogger(__name__)

BASE_URL   = "https://www.argenprop.com"
OPERACIONES = ["alquiler", "venta"]
DELAY       = 0.6   # segundos entre requests
MAX_PAGES   = 150   # techo de seguridad

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
}

# idmoneda=1 → ARS, idmoneda=2 → USD (se guarda el monto sin conversión)
MONEDAS = {"1": "ARS", "2": "USD"}


def _get(url: str, retries: int = 3) -> requests.Response | None:
    for intento in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (404, 405):
                return None
            logger.warning(f"HTTP {resp.status_code} en {url} (intento {intento+1})")
        except requests.RequestException as e:
            logger.warning(f"Error en {url} (intento {intento+1}): {e}")
        time.sleep(2 ** intento)
    return None


# ── Extracción del listado ─────────────────────────────────────────────────────

def _parse_cards(html: str) -> list[dict]:
    """Extrae los datos básicos de cada card del listado."""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all("div", class_="listing__item")
    cards = []

    for item in items:
        prop_id = item.get("id", "").strip()
        if not prop_id or not prop_id.isdigit():
            continue

        anchor = item.find("a", attrs={"data-item-card": True})
        if not anchor:
            continue

        link     = anchor.get("href", "")
        tipo_op  = "venta" if anchor.get("idtipooperacion") == "1" else "alquiler"
        monto    = anchor.get("montooperacion", "")
        idmoneda = anchor.get("idmoneda", "1")

        # Precio
        try:
            precio = float(monto) if monto else None
        except ValueError:
            precio = None

        # Título
        titulo_tag = item.find(class_="card__title--primary")
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else f"Propiedad Argenprop {prop_id}"

        # Dirección
        dir_tag = item.find(attrs={"data-card-direccion": True})
        direccion = dir_tag.get_text(strip=True) if dir_tag else ""

        # Fotos: primera visible + lazy (thumbnail → medium)
        fotos_small = []
        for img in item.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if "static-content" in src and "camera.svg" not in src:
                fotos_small.append(src)

        fotos = [f.replace("_u_small.jpg", "_u_medium.jpg") for f in fotos_small]

        cards.append({
            "ap_id":     prop_id,
            "ml_id":     f"ap-{prop_id}",
            "link":      link,
            "tipo_op":   tipo_op,
            "precio":    precio,
            "moneda":    MONEDAS.get(idmoneda, "ARS"),
            "titulo":    titulo,
            "direccion": direccion,
            "fotos":     fotos,
        })

    return cards


def _fetch_listing_page(operacion: str, pagina: int) -> list[dict]:
    url = f"{BASE_URL}/inmuebles/{operacion}/mendoza?pagina-{pagina}"
    resp = _get(url)
    if not resp:
        return []
    cards = _parse_cards(resp.text)
    logger.debug(f"  Pág {pagina} ({operacion}): {len(cards)} propiedades")
    return cards


# ── Extracción del detalle ─────────────────────────────────────────────────────

def _parse_detail(html: str) -> dict:
    """Extrae descripción y fotos de alta resolución de la página de detalle."""
    soup = BeautifulSoup(html, "html.parser")

    # Descripción: JSON-LD primero (más limpio), luego meta description
    descripcion = ""
    jsonld_tag = soup.find("script", type="application/ld+json")
    if jsonld_tag:
        try:
            data = json.loads(jsonld_tag.string or "")
            descripcion = data.get("description", "")
        except (json.JSONDecodeError, AttributeError):
            pass

    if not descripcion:
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            descripcion = meta.get("content", "")

    # Descripción extendida en el cuerpo de la página
    cuerpo = soup.find("div", class_=re.compile(r"ficha.*descrip|property.*descrip|aviso.*descrip", re.I))
    if not cuerpo:
        cuerpo = soup.find("section", id=re.compile(r"descrip", re.I))
    if cuerpo:
        texto_cuerpo = cuerpo.get_text(separator=" ", strip=True)
        if len(texto_cuerpo) > len(descripcion):
            descripcion = texto_cuerpo

    # Fotos únicas en calidad medium
    fotos_set = []
    seen = set()
    for img in soup.find_all("img"):
        for attr in ("src", "data-src"):
            src = img.get(attr, "")
            if "static-content" in src and "camera.svg" not in src:
                # Normalizar a medium
                src_med = re.sub(r'_u_(small|large)\.jpg', '_u_medium.jpg', src)
                src_med = src_med.rstrip(",)")  # limpiar artefactos de CSS
                # Extraer UUID para deduplicar
                uuid_m = re.search(r'/([a-f0-9-]{36})_?', src_med)
                if uuid_m:
                    uuid = uuid_m.group(1)
                    if uuid not in seen:
                        seen.add(uuid)
                        fotos_set.append(src_med)

    return {
        "descripcion": descripcion.strip() or None,
        "fotos":       fotos_set[:20],
    }


def _fetch_detail(link: str) -> dict:
    url = f"{BASE_URL}{link}" if link.startswith("/") else link
    resp = _get(url)
    if not resp:
        return {"descripcion": None, "fotos": []}
    return _parse_detail(resp.text)


# ── Guardado en BD ─────────────────────────────────────────────────────────────

def _save_cards(db, cards: list[dict], fetch_detail: bool = True) -> int:
    saved = 0
    for card in cards:
        existing = db.query(Property).filter_by(ml_id=card["ml_id"]).first()

        if existing:
            existing.activa = True
            if card["precio"] is not None and existing.precio != card["precio"]:
                existing.precio = card["precio"]
            if card["fotos"] and existing.fotos_urls != card["fotos"]:
                existing.fotos_urls = card["fotos"]
            saved += 1
        else:
            # Propiedad nueva: buscar descripción y fotos completas
            detail = {"descripcion": None, "fotos": card["fotos"]}
            if fetch_detail and card["link"]:
                detail = _fetch_detail(card["link"])
                # El listing card tiene más fotos (lazy-load en detalle no es parseable)
                if len(card["fotos"]) >= len(detail["fotos"]):
                    detail["fotos"] = card["fotos"]
                time.sleep(DELAY)

            ubicacion = card["direccion"] or "Mendoza"
            if "mendoza" not in ubicacion.lower():
                ubicacion = f"{ubicacion}, Mendoza"

            sup = extraer_superficie(detail["descripcion"] or "")
            amb = extraer_ambientes(detail["descripcion"] or "")
            new_prop = Property(
                ml_id          = card["ml_id"],
                titulo         = card["titulo"],
                precio         = card["precio"],
                descripcion    = detail["descripcion"],
                ubicacion      = ubicacion,
                permalink_ml   = f"{BASE_URL}{card['link']}",
                fotos_urls     = detail["fotos"] or None,
                fuente         = "argenprop",
                tipo_operacion = card["tipo_op"],
                activa         = True,
                superficie_m2  = sup,
                ambientes      = amb,
            )
            canonical_id = find_canonical(db, ubicacion, card["precio"], card["tipo_op"], "argenprop", sup, amb)
            if canonical_id:
                new_prop.duplicate_of = canonical_id
            db.add(new_prop)
            saved += 1

    db.commit()
    return saved


# ── Punto de entrada ───────────────────────────────────────────────────────────

def _scrape_operacion_argenprop(operacion: str) -> tuple[int, set[str]]:
    """Scrapes una operación con su propia sesión DB. Pensado para correr en thread."""
    db = SessionLocal()
    total_op = 0
    ids_op: set[str] = set()

    try:
        logger.info(f"Argenprop scrapeando: {operacion}...")
        for pagina in range(1, MAX_PAGES + 1):
            cards = _fetch_listing_page(operacion, pagina)
            if not cards:
                logger.info(f"  {operacion}: sin más resultados en página {pagina}, fin.")
                break

            ids_pagina = {c["ml_id"] for c in cards}
            nuevos = ids_pagina - ids_op
            if not nuevos:
                logger.info(f"  {operacion}: página {pagina} repite IDs, fin real del listado.")
                break
            ids_op.update(ids_pagina)

            saved = _save_cards(db, cards)
            total_op += saved
            logger.info(f"  {operacion} pág {pagina}: {saved} guardadas (total op: {total_op})")

            time.sleep(DELAY)

        logger.info(f"  {operacion}: {total_op} propiedades procesadas.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error en scraping Argenprop [{operacion}]: {e}", exc_info=True)
    finally:
        db.close()

    return total_op, ids_op


def scrape_argenprop() -> int:
    logger.info("Iniciando scraping de Argenprop (venta + alquiler en paralelo)...")
    total_saved = 0
    ids_vistos: set[str] = set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(_scrape_operacion_argenprop, op): op for op in OPERACIONES}
        for future in as_completed(futures):
            try:
                saved, ids_op = future.result()
                total_saved += saved
                ids_vistos.update(ids_op)
            except Exception as e:
                logger.error(f"Argenprop thread error: {e}")

    if ids_vistos:
        db = SessionLocal()
        activas_actuales = db.query(Property).filter(
            Property.fuente == "argenprop", Property.activa == True
        ).count()
        umbral = max(200, int(activas_actuales * 0.3))
        if len(ids_vistos) >= umbral:
            inactivadas = db.query(Property).filter(
                Property.fuente == "argenprop",
                ~Property.ml_id.in_(ids_vistos),
            ).update({"activa": False}, synchronize_session=False)
            db.commit()
            logger.info(f"Argenprop: {inactivadas} propiedades no vistas marcadas como inactivas.")
        else:
            logger.warning(
                f"Argenprop: scrape incompleto ({len(ids_vistos)} vistos vs {activas_actuales} activas, "
                f"umbral {umbral}). No se inactivaron propiedades para evitar pérdida de datos."
            )
        db.close()

    logger.info(f"Argenprop finalizado: {total_saved} propiedades nuevas/actualizadas.")
    return total_saved
