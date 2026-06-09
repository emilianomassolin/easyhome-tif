import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from backend.database.connection import SessionLocal
from backend.database.models import Property

logger = logging.getLogger(__name__)

BASE_URL = "https://www.zonaprop.com.ar"
OPERACIONES = ["venta", "alquiler"]

# User agents reales de Windows/Mac (más comunes que Linux)
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


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
            if not data_id:
                continue

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
                "ml_id":          f"zp-{data_id}",
                "titulo":         titulo or "Sin título",
                "precio":         precio,
                "descripcion":    titulo,
                "ubicacion":      ubicacion,
                "permalink_ml":   permalink,
                "fotos_urls":     fotos,
                "fuente":         "zonaprop",
                "tipo_operacion": operacion,
            })
        except Exception as e:
            logger.warning(f"Error parseando card ZonaProp: {e}")
            continue

    return propiedades


def _scrape_operacion(operacion: str, max_paginas: int) -> tuple[int, set[str]]:
    """Scrapes una operación con sesión persistente + stealth. Corre en thread."""
    db = SessionLocal()
    saved = 0
    ids_vistos: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        # Un solo context por sesión → mantiene cookies y parece usuario real
        ctx = browser.new_context(
            user_agent=random.choice(_USER_AGENTS),
            locale="es-AR",
            timezone_id="America/Argentina/Mendoza",
            viewport={"width": random.randint(1280, 1920), "height": random.randint(768, 1080)},
            extra_http_headers={
                "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "DNT": "1",
            },
        )

        stealth = Stealth(navigator_platform_override="Win32")
        page = ctx.new_page()
        stealth.apply_stealth_sync(page)  # oculta navigator.webdriver y otros indicadores de bot

        try:
            numero = 1
            consecutive_empty = 0
            consecutive_errors = 0
            logger.info(f"ZonaProp scrapeando: {operacion}")

            # Visita la home primero para parecer un usuario que navegó al sitio
            try:
                page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(1.5, 3.0))
            except Exception:
                pass

            while True:
                if max_paginas and numero > max_paginas:
                    logger.info(f"ZonaProp {operacion}: límite de {max_paginas} páginas.")
                    break

                try:
                    url = _page_url(operacion, numero)
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)

                    titulo = page.title().lower()
                    # ZonaProp muestra "un momento..." cuando detecta bot → esperar más
                    if "moment" in titulo or "checking" in titulo or "captcha" in titulo:
                        logger.warning(f"ZonaProp [{operacion}] pág {numero}: challenge detectado, esperando...")
                        time.sleep(random.uniform(15, 25))
                        page.reload(wait_until="domcontentloaded", timeout=60000)
                        time.sleep(random.uniform(5, 8))

                    # Scroll humano para activar lazy-load
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    time.sleep(random.uniform(0.8, 1.5))
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(random.uniform(1.0, 2.0))

                    items = _extraer_cards(page, operacion)
                    consecutive_errors = 0

                except Exception as e:
                    consecutive_errors += 1
                    logger.warning(f"ZonaProp {operacion} pág {numero}: error ({e}). Intento {consecutive_errors}/4")
                    time.sleep(random.uniform(8, 15) * consecutive_errors)
                    if consecutive_errors >= 4:
                        logger.error(f"ZonaProp {operacion}: demasiados errores consecutivos. Parando.")
                        break
                    continue

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
                        db.add(Property(**item))
                    saved += 1

                db.commit()
                numero += 1

                # Delay humano entre páginas (más largo cada 10 páginas)
                if numero % 10 == 0:
                    pausa = random.uniform(8, 15)
                    logger.info(f"ZonaProp [{operacion}]: pausa larga ({pausa:.0f}s) en pág {numero}...")
                    time.sleep(pausa)
                else:
                    time.sleep(random.uniform(2.5, 5.0))

        except Exception as e:
            logger.error(f"Error inesperado en ZonaProp [{operacion}]: {e}")
        finally:
            ctx.close()
            browser.close()

    db.close()
    logger.info(f"ZonaProp {operacion}: {saved} propiedades procesadas.")
    return saved, ids_vistos


def scrape_zonaprop(max_paginas: int = 600) -> int:
    logger.info("Iniciando scraping de ZonaProp (venta + alquiler en paralelo)...")
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
