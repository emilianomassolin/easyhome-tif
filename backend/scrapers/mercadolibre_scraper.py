import logging
import re
import time

import requests
from playwright.sync_api import sync_playwright

from backend.database.connection import SessionLocal
from backend.database.models import Property

logger = logging.getLogger(__name__)

BASE_URL    = "https://inmuebles.mercadolibre.com.ar"
SEARCH_URL  = "https://api.mercadolibre.com/sites/MLA/search"
ITEMS_URL   = "https://api.mercadolibre.com/items"

OPERACIONES = ["venta", "alquiler"]

# Subcategorías — cada una permite hasta 1.000 resultados independientes en la API
CATEGORIAS = {
    "MLA1466":  "Casas",
    "MLA1472":  "Departamentos",
    "MLA105179": "PH",
    "MLA1493":  "Terrenos y Lotes",
    "MLA50547": "Quintas",
    "MLA1496":  "Campos",
    "MLA50541": "Cocheras",
    "MLA79242": "Locales",
    "MLA50538": "Oficinas",
}

# Slugs para Playwright (fallback web)
TIPOS_WEB = [
    "casas", "departamentos", "ph", "quintas",
    "terrenos-y-lotes", "campos", "cocheras", "locales", "oficinas",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_token() -> str | None:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    access = os.getenv("ML_ACCESS_TOKEN", "").strip()
    if not access:
        return None
    # Intentar refrescar
    try:
        from backend.ml_integration.auth import get_access_token
        return get_access_token()
    except Exception:
        return access


def _parse_price(texto: str | None) -> float | None:
    if not texto:
        return None
    try:
        return float(re.sub(r"[^\d]", "", texto)) or None
    except Exception:
        return None


def _save_items(db, items: list[dict]) -> int:
    saved = 0
    for item in items:
        existing = db.query(Property).filter_by(ml_id=item["ml_id"]).first()
        if existing:
            existing.activa = True
            if item.get("precio") and existing.precio != item["precio"]:
                existing.precio = item["precio"]
        else:
            db.add(Property(**item))
        saved += 1
    db.commit()
    return saved


# ── Modo API ──────────────────────────────────────────────────────────────────

def _scrape_api(db, token: str) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    total_saved = 0

    for cat_id, nombre in CATEGORIAS.items():
        offset = 0
        logger.info(f"ML API → {nombre}")
        while True:
            try:
                resp = requests.get(SEARCH_URL, params={
                    "category": cat_id,
                    "state":    "AR-M",
                    "limit":    50,
                    "offset":   offset,
                }, headers=headers, timeout=15)

                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limit. Esperando {wait}s...")
                    time.sleep(wait)
                    continue

                if resp.status_code != 200:
                    logger.warning(f"ML API {nombre}: status {resp.status_code}. Saltando.")
                    break

                data  = resp.json()
                items_raw = data.get("results", [])
                if not items_raw:
                    break

                total = data.get("paging", {}).get("total", 0)

                items = []
                for it in items_raw:
                    ml_id = f"ml-{it['id']}"
                    fotos = [
                        p.get("secure_url") or p.get("url")
                        for p in it.get("pictures", [])
                        if p.get("secure_url") or p.get("url")
                    ] or ([it["thumbnail"]] if it.get("thumbnail") else [])

                    addr = it.get("seller_address", {})
                    ubicacion = ", ".join(
                        p for p in [
                            addr.get("city", {}).get("name"),
                            addr.get("state", {}).get("name"),
                        ] if p
                    ) or "Mendoza"

                    titulo = it.get("title", "Sin título")[:200]
                    tipo_op = "alquiler" if "alquil" in titulo.lower() else "venta"

                    items.append({
                        "ml_id":           ml_id,
                        "titulo":          titulo,
                        "precio":          it.get("price"),
                        "descripcion":     titulo,
                        "ubicacion":       ubicacion,
                        "permalink_ml":    it.get("permalink", ""),
                        "fotos_urls":      fotos or None,
                        "fuente":          "mercadolibre",
                        "tipo_operacion":  tipo_op,
                        "activa":          True,
                    })

                saved = _save_items(db, items)
                total_saved += saved
                logger.info(f"  {nombre} offset={offset}: {saved} props (total={total})")

                offset += len(items_raw)
                time.sleep(0.3)

                if offset >= min(total, 1000):
                    break

            except Exception as e:
                logger.error(f"Error API ML {nombre}: {e}")
                break

    return total_saved


# ── Modo Playwright (fallback) ────────────────────────────────────────────────

def _extraer_cards_web(page, operacion: str) -> list[dict]:
    propiedades = []
    for item in page.query_selector_all("li.ui-search-layout__item"):
        try:
            link_el = item.query_selector("a.poly-component__title")
            if not link_el:
                continue
            permalink = (link_el.get_attribute("href") or "").split("#")[0]
            titulo    = link_el.inner_text().strip()[:200]
            ml_match  = re.search(r"MLA-?(\d+)", permalink)
            if not ml_match:
                continue
            ml_id     = f"ml-MLA{ml_match.group(1)}"
            precio_el = item.query_selector(".andes-money-amount__fraction")
            precio    = _parse_price(precio_el.inner_text()) if precio_el else None
            ubic_el   = item.query_selector(".poly-component__location")
            ubicacion = ubic_el.inner_text().strip()[:200] if ubic_el else "Mendoza"
            img_el    = item.query_selector("img.poly-component__picture")
            fotos     = [img_el.get_attribute("src")] if img_el else []
            propiedades.append({
                "ml_id":          ml_id,
                "titulo":         titulo or "Sin título",
                "precio":         precio,
                "descripcion":    titulo,
                "ubicacion":      ubicacion,
                "permalink_ml":   permalink,
                "fotos_urls":     fotos,
                "fuente":         "mercadolibre",
                "tipo_operacion": operacion,
            })
        except Exception as e:
            logger.warning(f"Error parseando card ML: {e}")
    return propiedades


def _scrape_web(db, max_paginas: int | None) -> int:
    total_saved = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--no-sandbox", "--disable-blink-features=AutomationControlled",
        ])
        try:
            for operacion in OPERACIONES:
                for tipo in TIPOS_WEB:
                    pagina = 0
                    logger.info(f"ML Web → {tipo}/{operacion}")
                    while True:
                        if max_paginas and pagina >= max_paginas:
                            break
                        offset = pagina * 50
                        base = f"{BASE_URL}/{tipo}/{operacion}/mendoza"
                        url = base + "/" if offset == 0 else f"{base}/_Desde_{offset + 1}_NoIndex_True"

                        ctx = browser.new_context(
                            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                            viewport={"width": 1280, "height": 800},
                            locale="es-AR",
                            timezone_id="America/Argentina/Mendoza",
                        )
                        try:
                            page = ctx.new_page()
                            page.goto(url, wait_until="domcontentloaded", timeout=60000)
                            page.wait_for_timeout(3000)
                            # Detectar bloqueo
                            if "account-verification" in page.url:
                                logger.warning("ML Web: bloqueado por verificación de cuenta. Abortando web scraping.")
                                return total_saved
                            items = _extraer_cards_web(page, operacion)
                        finally:
                            ctx.close()

                        if not items:
                            break

                        saved = _save_items(db, items)
                        total_saved += saved
                        logger.info(f"  {tipo}/{operacion} pág {pagina + 1}: {saved} props.")
                        pagina += 1
                        if offset + 50 >= 1000:
                            break
        finally:
            browser.close()
    return total_saved


# ── Entrada principal ─────────────────────────────────────────────────────────

def scrape_mercadolibre(max_paginas: int = None) -> int:
    logger.info("Iniciando scraping MercadoLibre...")
    db = SessionLocal()
    total_saved = 0

    db.query(Property).filter_by(fuente="mercadolibre").update({"activa": False})
    db.commit()
    logger.info("MercadoLibre: propiedades existentes marcadas como inactivas.")

    try:
        token = _get_token()
        if token:
            logger.info("Usando ML API (OAuth token disponible)")
            total_saved = _scrape_api(db, token)
        else:
            logger.info("Sin token OAuth — usando Playwright (web scraping)")
            total_saved = _scrape_web(db, max_paginas)
    except Exception as e:
        db.rollback()
        logger.error(f"Error en scraping ML: {e}")
        raise
    finally:
        db.close()

    logger.info(f"MercadoLibre: {total_saved} propiedades totales.")
    return total_saved
