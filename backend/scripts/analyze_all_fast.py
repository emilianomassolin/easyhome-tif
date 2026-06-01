"""
Analyze-all paralelo. Procesa propiedades pendientes con ThreadPoolExecutor
para hacer llamadas a la API de Claude concurrentemente.

Uso: .venv/bin/python -m backend.scripts.analyze_all_fast [--workers N] [--fuente F]
"""
import argparse
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from backend.database.connection import SessionLocal
from backend.database.models import Property
from backend.nlp.analyzer import analizar_texto
from backend.nlp.keyword_filter import tiene_keywords_accesibilidad, RESULTADO_VACIO, VISION_VACIA
from backend.scoring.calculator import calcular_score
from backend.vision.image_analyzer import analizar_imagenes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

_lock = threading.Lock()
_stats = {"analizadas": 0, "nlp": 0, "vision": 0, "errores": 0}


def _procesar(prop_id: int) -> None:
    db = SessionLocal()
    try:
        prop = db.query(Property).filter(Property.id == prop_id).first()
        if not prop or prop.analizado:
            return

        if tiene_keywords_accesibilidad(prop.titulo, prop.descripcion):
            nlp = analizar_texto(prop.descripcion)
            nlp_positivo = any(v for k, v in nlp.items() if k != "confianza" and v is True)
            with _lock:
                _stats["nlp"] += 1
            if nlp_positivo:
                vision = analizar_imagenes(prop.fotos_urls)
                with _lock:
                    _stats["vision"] += 1
            else:
                vision = VISION_VACIA
        else:
            nlp = RESULTADO_VACIO
            vision = VISION_VACIA

        resultado = calcular_score(nlp, vision, prop.titulo)
        prop.nlp_resultado = nlp
        prop.vision_resultado = vision
        prop.score_accesibilidad = resultado["score_accesibilidad"]
        prop.justificacion_score = resultado["justificacion"]
        prop.confianza_general = resultado["confianza"]
        prop.analizado = True
        prop.fecha_analisis = datetime.now(timezone.utc)
        db.commit()

        with _lock:
            _stats["analizadas"] += 1
            if _stats["analizadas"] % 500 == 0:
                logger.info(
                    f"Progreso: {_stats['analizadas']} analizadas | "
                    f"{_stats['nlp']} NLP | {_stats['vision']} visión | "
                    f"{_stats['errores']} errores"
                )
    except Exception as e:
        db.rollback()
        with _lock:
            _stats["errores"] += 1
        logger.error(f"Error prop {prop_id}: {e}")
    finally:
        db.close()


def main(workers: int = 10, fuente: str | None = None) -> None:
    db = SessionLocal()
    query = db.query(Property.id).filter(Property.activa == True, Property.analizado == False)
    if fuente:
        query = query.filter(Property.fuente == fuente)
    ids = [row[0] for row in query.all()]
    db.close()

    total = len(ids)
    if not total:
        logger.info("No hay propiedades pendientes.")
        return

    logger.info(f"Procesando {total} propiedades con {workers} workers en paralelo...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_procesar, pid): pid for pid in ids}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error inesperado: {e}")

    logger.info(
        f"Finalizado. {_stats['analizadas']} analizadas | "
        f"{_stats['nlp']} fueron a NLP | {_stats['vision']} fueron a visión | "
        f"{_stats['errores']} errores."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--fuente", type=str, default=None)
    args = parser.parse_args()
    main(workers=args.workers, fuente=args.fuente)
