"""
Re-analiza las top N propiedades por score usando claude-sonnet para visión.
Uso: .venv/bin/python -m backend.scripts.reanalyze_top_sonnet [--top N]
"""
import argparse
import base64
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import anthropic
import requests
from dotenv import load_dotenv

from backend.database.connection import SessionLocal
from backend.database.models import Property
from backend.nlp.analyzer import analizar_texto
from backend.scoring.calculator import calcular_score
from backend.vision.image_analyzer import CRITERIOS_VISION, PROMPT_VISION

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_lock = threading.Lock()
_stats = {"ok": 0, "errores": 0}


def _url_a_base64(url: str):
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        if len(resp.content) > 5 * 1024 * 1024:
            return None
        content = resp.content
        if content[:8] == b'\x89PNG\r\n\x1a\n':
            ct = "image/png"
        elif content[:2] == b'\xff\xd8':
            ct = "image/jpeg"
        elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
            ct = "image/webp"
        else:
            ct = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        return base64.standard_b64encode(content).decode("utf-8"), ct
    except Exception as e:
        logger.warning(f"No se pudo descargar {url}: {e}")
        return None


def _analizar_imagen_sonnet(url: str):
    resultado = _url_a_base64(url)
    if not resultado:
        return None
    data, ct = resultado
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": ct, "data": data}},
                    {"type": "text", "text": PROMPT_VISION},
                ],
            }],
        )
        texto = response.content[0].text.strip()
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        return json.loads(texto.strip())
    except Exception as e:
        logger.error(f"Error analizando imagen {url}: {e}")
        return None


def _analizar_imagenes_sonnet(fotos_urls):
    if not fotos_urls:
        return {c: False for c in CRITERIOS_VISION} | {"imagenes_analizadas": 0, "descripciones": []}
    resultados = []
    for url in fotos_urls[:3]:
        r = _analizar_imagen_sonnet(url)
        if r:
            resultados.append(r)
    if not resultados:
        return {c: False for c in CRITERIOS_VISION} | {"imagenes_analizadas": 0, "descripciones": []}
    combinado = {c: any(r.get(c, False) for r in resultados) for c in CRITERIOS_VISION}
    combinado["imagenes_analizadas"] = len(resultados)
    combinado["descripciones"] = [r.get("descripcion_visual", "") for r in resultados if r.get("descripcion_visual")]
    return combinado


def _procesar(prop_id: int) -> None:
    db = SessionLocal()
    try:
        prop = db.query(Property).filter(Property.id == prop_id).first()
        if not prop:
            return

        nlp = analizar_texto(prop.descripcion)
        if nlp is None:
            logger.warning(f"Prop {prop_id}: NLP no disponible, se omite (queda pendiente).")
            return
        vision = _analizar_imagenes_sonnet(prop.fotos_urls)
        resultado = calcular_score(nlp, vision, prop.titulo)

        prop.nlp_resultado = nlp
        prop.vision_resultado = vision
        prop.score_accesibilidad = resultado["score_accesibilidad"]
        prop.justificacion_score = resultado["justificacion"]
        prop.confianza_general = resultado["confianza"]
        prop.fecha_analisis = datetime.now(timezone.utc)
        db.commit()

        with _lock:
            _stats["ok"] += 1
            if _stats["ok"] % 50 == 0:
                logger.info(f"Progreso: {_stats['ok']} re-analizadas | {_stats['errores']} errores")
    except Exception as e:
        db.rollback()
        with _lock:
            _stats["errores"] += 1
        logger.error(f"Error prop {prop_id}: {e}")
    finally:
        db.close()


def main(top: int = 370, workers: int = 5) -> None:
    db = SessionLocal()
    ids = [
        row[0] for row in
        db.query(Property.id)
        .filter(Property.analizado == True, Property.activa == True)
        .order_by(Property.score_accesibilidad.desc())
        .limit(top)
        .all()
    ]
    db.close()

    logger.info(f"Re-analizando top {len(ids)} propiedades con Sonnet...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_procesar, pid): pid for pid in ids}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error inesperado: {e}")

    logger.info(f"Finalizado. {_stats['ok']} re-analizadas | {_stats['errores']} errores.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=370)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()
    main(top=args.top, workers=args.workers)
