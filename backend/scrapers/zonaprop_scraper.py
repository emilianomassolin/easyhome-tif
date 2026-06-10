import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from backend.database.connection import SessionLocal
from backend.database.models import Property
from backend.scrapers.dedup_utils import find_canonical

logger = logging.getLogger(__name__)

BASE_URL = "https://www.zonaprop.com.ar"
OPERACIONES = ["venta", "alquiler"]
FLARESOLVERR_URL = "http://localhost:8191/v1"
MAX_TIMEOUT = 60000  # ms


def _page_url(operacion: str, numero: int) -> str:
    if numero == 1:
        return f"{BASE_URL}/inmuebles-{operacion}-mendoza.html"
    return f"{BASE_URL}/inmuebles-{operacion}-mendoza-pagina-{numero}.html"


def _parse_price(texto: str | None) -> float | None:
    if not texto:
        return None
    try:
        numeros = re.sub(r"[^\d]", "", texto)
        return float(numeros) if numeros else None
    except Exception:
        return None


def _fs_get(session_id: str, url: str, retries: int = 3) -> str | None:
    """Obtiene HTML de una URL usando FlareSolverr (bypass Cloudflare)."""
    for intento in range(retries):
        try:
            resp = requests.post(
                FLARESOLVERR_URL,
                json={"cmd": "request.get", "url": url, "session": session_id, "maxTimeout": MAX_TIMEOUT},
                timeout=90,
            )
            data = resp.json()
            if data.get("status") == "ok":
                solution = data.get("solution", {})
                if solution.get("status") == 200:
                    return solution.get("response", "")
                logger.warning(f"FlareSolverr HTTP {solution.get('status')} en {url}")
            else:
                logger.warning(f"FlareSolverr error: {data.get('message')} en {url}")
        except Exception as e:
            logger.warning(f"FlareSolverr request error (intento {intento+1}): {e}")
        time.sleep(5 * (intento + 1))
    return None


def _extraer_fotos_detalle(html: str) -> list[str]:
    """Extrae todas las URLs de fotos de la página de detalle de ZonaProp."""
    # Buscar imágenes de imgar.zonapropcdn.com/avisos en tamaño 720x532 o 1200x1200
    urls = re.findall(
        r"https://imgar\.zonapropcdn\.com/avisos/[^\s\"']+\.jpg(?:\?[^\s\"']*)?",
        html,
    )
    # Deduplicar por ID de imagen (último segmento antes de ?)
    seen_ids: set[str] = set()
    result: list[str] = []
    for url in urls:
        base = url.split("?")[0]
        img_id = base.rsplit("/", 1)[-1]
        # Preferir 720x532 sobre 360x266; excluir logos de empresa
        if "empresas" in url or "logo" in url.lower():
            continue
        if img_id not in seen_ids:
            seen_ids.add(img_id)
            # Normalizar a 720x532 para consistencia
            url_norm = re.sub(r"/\d+x\d+/", "/720x532/", base)
            result.append(url_norm)
    return result[:20]


def _extraer_cards(html: str, operacion: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all(attrs={"data-id": True})
    propiedades = []

    for item in items:
        try:
            data_id = item.get("data-id", "").strip()
            if not data_id:
                continue

            link_el = item.find("a", href=re.compile(r"/propiedades/"))
            if not link_el:
                continue
            href = link_el.get("href", "").split("?")[0]
            permalink = BASE_URL + href if href.startswith("/") else href
            titulo = link_el.get_text(strip=True)[:200] or "Sin título"

            precio_el = item.find(class_=re.compile(r"[Pp]rice"))
            precio = _parse_price(precio_el.get_text()) if precio_el else None

            ubic_el = item.find(class_=re.compile(r"[Ll]ocation|[Aa]ddress"))
            ubicacion = ubic_el.get_text(strip=True).split("\n")[0][:200] if ubic_el else "Mendoza"

            img_el = item.find("img", src=True)
            foto_thumb = img_el["src"] if img_el else None

            propiedades.append({
                "ml_id":          f"zp-{data_id}",
                "titulo":         titulo,
                "precio":         precio,
                "descripcion":    titulo,
                "ubicacion":      ubicacion,
                "permalink_ml":   permalink,
                "fotos_urls":     [foto_thumb] if foto_thumb else [],
                "href":           href,  # para visitar detalle
                "fuente":         "zonaprop",
                "tipo_operacion": operacion,
            })
        except Exception as e:
            logger.warning(f"Error parseando card ZonaProp: {e}")
            continue

    return propiedades


def _scrape_operacion(operacion: str, max_paginas: int) -> tuple[int, set[str]]:
    db = SessionLocal()
    saved = 0
    ids_vistos: set[str] = set()
    session_id = f"zonaprop_{operacion}"

    # Crear sesión en FlareSolverr (mantiene cookies entre requests)
    try:
        requests.post(
            FLARESOLVERR_URL,
            json={"cmd": "sessions.create", "session": session_id},
            timeout=30,
        )
    except Exception as e:
        logger.warning(f"FlareSolverr sessions.create error: {e}")

    try:
        numero = 1
        consecutive_empty = 0
        consecutive_errors = 0
        logger.info(f"ZonaProp scrapeando: {operacion} (via FlareSolverr)")

        while True:
            if max_paginas and numero > max_paginas:
                logger.info(f"ZonaProp {operacion}: límite de {max_paginas} páginas.")
                break

            url = _page_url(operacion, numero)
            html = _fs_get(session_id, url)

            if html is None:
                consecutive_errors += 1
                logger.warning(f"ZonaProp {operacion} pág {numero}: sin respuesta. Errores: {consecutive_errors}/4")
                if consecutive_errors >= 4:
                    logger.error(f"ZonaProp {operacion}: demasiados errores. Parando.")
                    break
                continue

            consecutive_errors = 0
            items = _extraer_cards(html, operacion)

            if not items:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    logger.info(f"ZonaProp {operacion} pág {numero}: sin resultados. Fin.")
                    break
                numero += 1
                continue

            consecutive_empty = 0
            logger.info(f"ZonaProp {operacion} pág {numero}: {len(items)} propiedades.")

            for item in items:
                ids_vistos.add(item["ml_id"])
                href = item.pop("href", None)  # no es columna del modelo
                existing = db.query(Property).filter_by(ml_id=item["ml_id"]).first()
                if existing:
                    existing.activa = True
                    existing.tipo_operacion = operacion
                    if item.get("precio") and existing.precio != item["precio"]:
                        existing.precio = item["precio"]
                    if item.get("descripcion") and existing.descripcion != item["descripcion"]:
                        existing.descripcion = item["descripcion"]
                        existing.analizado = False
                else:
                    # Propiedad nueva → visitar detalle para obtener todas las fotos y descripción
                    if href:
                        detail_url = BASE_URL + href if href.startswith("/") else href
                        detail_html = _fs_get(session_id, detail_url)
                        if detail_html:
                            fotos_detalle = _extraer_fotos_detalle(detail_html)
                            if fotos_detalle:
                                item["fotos_urls"] = fotos_detalle
                            # Extraer descripción del detalle
                            soup_det = BeautifulSoup(detail_html, "html.parser")
                            desc_el = soup_det.find(class_=re.compile(r"[Dd]escription|[Dd]escripcion|[Dd]etalle"))
                            if desc_el:
                                texto = desc_el.get_text(separator=" ", strip=True)
                                if len(texto) > len(item.get("descripcion", "")):
                                    item["descripcion"] = texto[:2000]
                        time.sleep(1.5)
                    new_prop = Property(**item)
                    canonical_id = find_canonical(
                        db,
                        ubicacion=item.get("ubicacion", ""),
                        precio=item.get("precio"),
                        tipo_operacion=operacion,
                        fuente="zonaprop",
                    )
                    if canonical_id:
                        new_prop.duplicate_of = canonical_id
                    db.add(new_prop)
                saved += 1

            db.commit()
            numero += 1
            time.sleep(2)

    except Exception as e:
        logger.error(f"Error inesperado en ZonaProp [{operacion}]: {e}")
    finally:
        db.close()
        try:
            requests.post(
                FLARESOLVERR_URL,
                json={"cmd": "sessions.destroy", "session": session_id},
                timeout=10,
            )
        except Exception:
            pass

    logger.info(f"ZonaProp {operacion}: {saved} propiedades procesadas.")
    return saved, ids_vistos


def scrape_zonaprop(max_paginas: int = 600) -> int:
    logger.info("Iniciando scraping de ZonaProp (venta + alquiler en paralelo, via FlareSolverr)...")
    total_saved = 0
    ids_vistos: set[str] = set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(_scrape_operacion, op, max_paginas): op for op in OPERACIONES}
        for future in as_completed(futures):
            try:
                saved, ids_op = future.result()
                total_saved += saved
                ids_vistos.update(ids_op)
            except Exception as e:
                logger.error(f"ZonaProp thread error: {e}")

    if ids_vistos:
        db = SessionLocal()
        activas_actuales = db.query(Property).filter(
            Property.fuente == "zonaprop", Property.activa == True
        ).count()
        umbral = max(1000, int(activas_actuales * 0.3))
        if len(ids_vistos) >= umbral:
            inactivadas = db.query(Property).filter(
                Property.fuente == "zonaprop",
                ~Property.ml_id.in_(ids_vistos),
            ).update({"activa": False}, synchronize_session=False)
            db.commit()
            logger.info(f"ZonaProp: {inactivadas} propiedades no vistas marcadas como inactivas.")
        else:
            logger.warning(
                f"ZonaProp: scrape incompleto ({len(ids_vistos)} vistos vs {activas_actuales} activas, "
                f"umbral {umbral}). No se inactivaron propiedades."
            )
        db.close()

    logger.info(f"ZonaProp: {total_saved} propiedades totales.")
    return total_saved
