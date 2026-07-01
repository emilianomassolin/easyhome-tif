"""
Re-análisis ONE-OFF de texto con Claude Haiku, corrido desde la PC local
contra la BD de producción (vía túnel SSH). No toca la arquitectura desplegada
(que sigue usando gemma): es una pasada puntual para resolver el catálogo ya.

Para cada propiedad pendiente (analizado=False):
  - sin keywords de accesibilidad -> RESULTADO_VACIO, sin llamar a la IA
  - con keywords -> Claude Haiku detecta los criterios en la descripción
La visión existente se conserva; el score se recalcula con texto + visión.

Env: DATABASE_URL (prod vía túnel), ANTHROPIC_API_KEY.
Uso: .venv/bin/python -m backend.scripts.reanalyze_claude_local [--workers N] [--fuente F]
"""
import argparse
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic
from dotenv import load_dotenv

from backend.database.connection import SessionLocal
from backend.database.models import Property
from backend.nlp.analyzer import PROMPT, CRITERIOS_NLP
from backend.nlp.keyword_filter import tiene_keywords_accesibilidad, RESULTADO_VACIO, VISION_VACIA
from backend.scoring.calculator import calcular_score

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"
client = anthropic.Anthropic(max_retries=8)

_stats = {"claude": 0, "vacias": 0, "error": 0, "total": 0, "inicio": 0.0}
_lock = threading.Lock()
_vacio = {c: False for c in CRITERIOS_NLP} | {"confianza": 0.0}


def _claude_nlp(descripcion: str) -> dict | None:
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": PROMPT.format(descripcion=descripcion)}],
        )
        texto = resp.content[0].text.strip()
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        return json.loads(texto.strip())
    except Exception as e:
        logger.error(f"Claude NLP error: {e}")
        return None


def _procesar(prop_id: int):
    db = SessionLocal()
    try:
        prop = db.query(Property).filter(Property.id == prop_id).first()
        if not prop or prop.analizado:
            return

        if tiene_keywords_accesibilidad(prop.titulo, prop.descripcion):
            nlp = _claude_nlp(prop.descripcion)
            if nlp is None:
                with _lock:
                    _stats["error"] += 1
                return
            with _lock:
                _stats["claude"] += 1
        else:
            nlp = dict(RESULTADO_VACIO)
            with _lock:
                _stats["vacias"] += 1

        vision = prop.vision_resultado or VISION_VACIA
        resultado = calcular_score(nlp, vision, prop.titulo, prop.manual_override or None)
        prop.nlp_resultado = nlp
        prop.vision_resultado = vision
        prop.score_accesibilidad = resultado["score_accesibilidad"]
        prop.justificacion_score = resultado["justificacion"]
        prop.confianza_general = resultado["confianza"]
        prop.analizado = True
        from datetime import datetime, timezone
        prop.fecha_analisis = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error prop {prop_id}: {e}")
        with _lock:
            _stats["error"] += 1
    finally:
        db.close()

    with _lock:
        hechas = _stats["claude"] + _stats["vacias"] + _stats["error"]
        if hechas % 100 == 0:
            elapsed = time.time() - _stats["inicio"]
            rate = hechas / elapsed if elapsed else 0
            eta = int((_stats["total"] - hechas) / rate) if rate else 0
            logger.info(f"{hechas}/{_stats['total']} | claude={_stats['claude']} vacias={_stats['vacias']} "
                        f"err={_stats['error']} | {rate:.1f}/s | ETA {eta//60}m")


def main(workers: int = 20, fuente: str | None = None):
    db = SessionLocal()
    q = db.query(Property.id).filter(Property.activa == True, Property.analizado == False)
    if fuente:
        q = q.filter(Property.fuente == fuente)
    ids = [r[0] for r in q.all()]
    db.close()

    _stats["total"] = len(ids)
    _stats["inicio"] = time.time()
    logger.info(f"Re-análisis Claude ({MODEL}): {len(ids)} pendientes | {workers} workers"
                + (f" | fuente={fuente}" if fuente else ""))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_procesar, pid) for pid in ids]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                logger.error(f"Error inesperado: {e}")

    logger.info(f"Terminado. claude={_stats['claude']} vacias={_stats['vacias']} "
                f"err={_stats['error']} de {_stats['total']}.")
    return _stats["claude"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--fuente", type=str, default=None)
    args = parser.parse_args()
    main(workers=args.workers, fuente=args.fuente)
