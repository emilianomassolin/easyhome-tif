import json
import logging
from playwright.sync_api import sync_playwright
from backend.database.connection import SessionLocal
from backend.database.models import Property

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.zonaprop.com.ar/inmuebles-venta-mendoza.html"


def _parse_price(precio_str: str | None) -> float | None:
    if not precio_str:
        return None
    try:
        limpio = precio_str.replace("USD", "").replace("$", "").replace(".", "").replace(",", "").strip()
        return float(limpio)
    except Exception:
        return None


def _scrape_with_playwright() -> list[dict]:
    propiedades = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="es-AR",
        )
        page = context.new_page()

        try:
            page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)
            # Esperar a que Cloudflare resuelva el challenge
            page.wait_for_timeout(8000)
            # Si sigue en el challenge, esperar más
            if "Just a moment" in page.title():
                page.wait_for_timeout(10000)

            # ZonaProp embebe los datos en __NEXT_DATA__
            next_data = page.evaluate("() => window.__NEXT_DATA__")

            if next_data:
                props = _extract_from_next_data(next_data)
                propiedades.extend(props)
            else:
                # Fallback: parsear HTML directamente
                propiedades.extend(_extract_from_html(page))

        except Exception as e:
            logger.error(f"Error en Playwright ZonaProp: {e}")
        finally:
            browser.close()

    return propiedades


def _extract_from_next_data(data: dict) -> list[dict]:
    propiedades = []
    try:
        # Navegar la estructura de Next.js para encontrar los listings
        listings = (
            data.get("props", {})
                .get("pageProps", {})
                .get("initialSearch", {})
                .get("search", {})
                .get("postings", [])
        )

        for item in listings:
            try:
                permalink = "https://www.zonaprop.com.ar" + item.get("url", "")
                fotos = [f.get("url") for f in item.get("photos", []) if f.get("url")]

                propiedades.append({
                    "ml_id":        f"zp-{item.get('id', '')}",
                    "titulo":       item.get("title") or item.get("formattedTitle", "Sin título"),
                    "precio":       _parse_price(str(item.get("price", {}).get("amount", ""))),
                    "descripcion":  item.get("description"),
                    "ubicacion":    item.get("address") or item.get("location", {}).get("name"),
                    "permalink_ml": permalink,
                    "fotos_urls":   fotos,
                    "fuente":       "zonaprop",
                })
            except Exception as e:
                logger.warning(f"Error parseando item ZonaProp: {e}")
                continue
    except Exception as e:
        logger.error(f"Error extrayendo __NEXT_DATA__: {e}")

    return propiedades


def _extract_from_html(page) -> list[dict]:
    propiedades = []
    cards = page.query_selector_all("[data-id], .posting-card, article.posting")

    for card in cards:
        try:
            titulo_el = card.query_selector("h2, h3, .posting-title")
            titulo = titulo_el.inner_text().strip() if titulo_el else "Sin título"

            precio_el = card.query_selector(".price-value, [class*='price']")
            precio = _parse_price(precio_el.inner_text()) if precio_el else None

            ubicacion_el = card.query_selector(".posting-location, [class*='location']")
            ubicacion = ubicacion_el.inner_text().strip() if ubicacion_el else "Mendoza"

            enlace_el = card.query_selector("a[href]")
            permalink = "https://www.zonaprop.com.ar" + enlace_el.get_attribute("href") if enlace_el else ""

            foto_el = card.query_selector("img[src]")
            fotos = [foto_el.get_attribute("src")] if foto_el else []

            data_id = card.get_attribute("data-id") or permalink.split("-")[-1].replace(".html", "")

            propiedades.append({
                "ml_id":        f"zp-{data_id}",
                "titulo":       titulo,
                "precio":       precio,
                "descripcion":  None,
                "ubicacion":    ubicacion,
                "permalink_ml": permalink,
                "fotos_urls":   fotos,
                "fuente":       "zonaprop",
            })
        except Exception as e:
            logger.warning(f"Error parseando card ZonaProp: {e}")
            continue

    return propiedades


def scrape_zonaprop() -> int:
    logger.info("Iniciando scraping de ZonaProp...")
    db = SessionLocal()
    saved = 0

    try:
        items = _scrape_with_playwright()
        logger.info(f"Propiedades encontradas en ZonaProp: {len(items)}")

        for item in items:
            if not item.get("ml_id") or not item.get("permalink_ml"):
                continue
            if db.query(Property).filter_by(ml_id=item["ml_id"]).first():
                continue
            db.add(Property(**item))
            saved += 1

        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Error en scraping de ZonaProp: {e}")
        raise
    finally:
        db.close()

    logger.info(f"ZonaProp: {saved} propiedades nuevas guardadas.")
    return saved
