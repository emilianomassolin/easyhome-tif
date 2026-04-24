import logging
import re
import requests
from bs4 import BeautifulSoup
from backend.database.connection import SessionLocal
from backend.database.models import Property

logger = logging.getLogger(__name__)

BASE_URL = "https://www.mendozaprop.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-AR,es;q=0.9",
}


def _parse_price(texto: str) -> float | None:
    try:
        numeros = re.sub(r"[^\d]", "", texto)
        return float(numeros) if numeros else None
    except Exception:
        return None


def _scrape_page(url: str) -> list[dict]:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    propiedades = []
    cards = soup.select("a[href*='/venta-']")

    for card in cards:
        try:
            href = card["href"]
            permalink = BASE_URL + href if not href.startswith("http") else href

            # Texto del card separado por pipes: Tipo|Fotos|Ubicación|Título|Features|Precio|CTA
            partes = [p.strip() for p in card.get_text(separator="|", strip=True).split("|") if p.strip()]

            if len(partes) < 3:
                continue

            # El título es la parte más larga que no sea precio ni "Contactar"
            titulo = next(
                (p for p in partes if len(p) > 15 and "USD" not in p and "$" not in p and p != "Contactar"),
                partes[0],
            )

            # Precio: parte que contiene USD o $ seguido de números
            precio_txt = next((p for p in partes if "USD" in p or re.search(r"\d{3}", p) and "$" in p), None)
            precio = _parse_price(precio_txt) if precio_txt else None

            # Ubicación: segunda o tercera parte (no es el tipo de propiedad)
            ubicacion = partes[2] if len(partes) > 2 else "Mendoza"

            foto_el = card.select_one("img[src]")
            fotos = [foto_el["src"]] if foto_el else []

            slug_id = href.rstrip("/").split("/")[-1]

            propiedades.append({
                "ml_id":        f"mzprop-{slug_id}",
                "titulo":       titulo,
                "precio":       precio,
                "descripcion":  None,
                "ubicacion":    ubicacion,
                "permalink_ml": permalink,
                "fotos_urls":   fotos,
                "fuente":       "mendozaprop",
            })
        except Exception as e:
            logger.warning(f"Error parseando card MendozaProp: {e}")
            continue

    return propiedades


def scrape_mendozaprop() -> int:
    logger.info("Iniciando scraping de MendozaProp...")
    db = SessionLocal()
    saved = 0

    try:
        items = _scrape_page(BASE_URL)
        logger.info(f"Propiedades encontradas en MendozaProp: {len(items)}")

        for item in items:
            if db.query(Property).filter_by(ml_id=item["ml_id"]).first():
                continue
            db.add(Property(**item))
            saved += 1

        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Error en scraping de MendozaProp: {e}")
        raise
    finally:
        db.close()

    logger.info(f"MendozaProp: {saved} propiedades nuevas guardadas.")
    return saved
