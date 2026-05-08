import logging
import re
import time
from playwright.sync_api import sync_playwright
from backend.database.connection import SessionLocal
from backend.database.models import Property

logger = logging.getLogger(__name__)

BASE_URL = "https://www.zonaprop.com.ar"

OPERACIONES = ["venta", "alquiler"]


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


def _extraer_cards(page, operacion: str) -> list[dict]:
    propiedades = []
    items = page.query_selector_all("[data-id]")

    for item in items:
        try:
            data_id = item.get_attribute("data-id")

            link_el = item.query_selector("a[href*='/propiedades/']")
            if not link_el:
                continue
            href = link_el.get_attribute("href").split("?")[0]
            permalink = BASE_URL + href
            titulo = link_el.inner_text().strip()[:200]

            precio_el = item.query_selector("[class*='Price'], [class*='price']")
            precio = _parse_price(precio_el.inner_text()) if precio_el else None

            ubic_el = item.query_selector("[class*='Location'], [class*='location'], [class*='address']")
            ubicacion = ubic_el.inner_text().strip().split("\n")[0][:200] if ubic_el else "Mendoza"

            img_el = item.query_selector("img[src]")
            fotos = [img_el.get_attribute("src")] if img_el else []

            propiedades.append({
                "ml_id":           f"zp-{data_id}",
                "titulo":          titulo or "Sin título",
                "precio":          precio,
                "descripcion":     titulo,
                "ubicacion":       ubicacion,
                "permalink_ml":    permalink,
                "fotos_urls":      fotos,
                "fuente":          "zonaprop",
                "tipo_operacion":  operacion,
            })
        except Exception as e:
            logger.warning(f"Error parseando card ZonaProp: {e}")
            continue

    return propiedades


def _scrape_page(browser, operacion: str, numero: int) -> list[dict]:
    """Carga una página en un contexto nuevo para evitar bloqueos de Cloudflare."""
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="es-AR",
    )
    try:
        page = ctx.new_page()
        url = _page_url(operacion, numero)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        titulo = page.title()
        if "moment" in titulo.lower():
            page.wait_for_timeout(12000)
        page.wait_for_timeout(4000)

        return _extraer_cards(page, operacion)
    finally:
        ctx.close()


def scrape_zonaprop(max_paginas: int = 600) -> int:
    logger.info("Iniciando scraping de ZonaProp (venta + alquiler)...")
    db = SessionLocal()
    saved = 0

    db.query(Property).filter_by(fuente="zonaprop").update({"activa": False})
    db.commit()
    logger.info("ZonaProp: propiedades existentes marcadas como inactivas.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        def _restart_browser():
            nonlocal browser
            try:
                browser.close()
            except Exception:
                pass
            browser = p.chromium.launch(headless=True)
            logger.info("ZonaProp: browser reiniciado.")

        try:
            for operacion in OPERACIONES:
                numero = 1
                logger.info(f"ZonaProp scrapeando: {operacion}")

                consecutive_errors = 0
                total_restarts = 0
                while True:
                    if max_paginas and numero > max_paginas:
                        logger.info(f"ZonaProp {operacion}: límite de {max_paginas} páginas alcanzado.")
                        break

                    try:
                        items = _scrape_page(browser, operacion, numero)
                        consecutive_errors = 0
                    except Exception as e:
                        consecutive_errors += 1
                        logger.warning(f"ZonaProp {operacion} pág {numero}: error ({e}). Reintentando ({consecutive_errors}/3)...")
                        time.sleep(5 * consecutive_errors)
                        if consecutive_errors >= 3:
                            if total_restarts >= 3:
                                logger.error(f"ZonaProp {operacion}: demasiados reinicios. Abandonando operacion.")
                                break
                            logger.warning("ZonaProp: reiniciando browser...")
                            _restart_browser()
                            consecutive_errors = 0
                            total_restarts += 1
                            time.sleep(10)
                        continue

                    if not items:
                        logger.info(f"ZonaProp {operacion} pág {numero}: sin resultados. Fin.")
                        break

                    logger.info(f"ZonaProp {operacion} pág {numero}: {len(items)} propiedades.")

                    for item in items:
                        existing = db.query(Property).filter_by(ml_id=item["ml_id"]).first()
                        if existing:
                            existing.activa = True
                            existing.tipo_operacion = operacion
                            if item.get("precio") and existing.precio != item["precio"]:
                                existing.precio = item["precio"]
                            if item.get("descripcion") and existing.descripcion != item["descripcion"]:
                                existing.descripcion = item["descripcion"]
                                existing.analizado = False
                            saved += 1
                        else:
                            db.add(Property(**item))
                            saved += 1

                    db.commit()
                    numero += 1

        except Exception as e:
            logger.error(f"Error inesperado en scraping ZonaProp: {e}")
        finally:
            browser.close()
            db.close()

    logger.info(f"ZonaProp: {saved} propiedades totales.")
    return saved
