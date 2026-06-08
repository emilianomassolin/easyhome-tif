"""
Analyze-all paralelo. Procesa propiedades pendientes con ThreadPoolExecutor.
Uso: .venv/bin/python -m backend.scripts.analyze_all_fast [--workers N] [--fuente F]
"""
import argparse
import logging
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from backend.database.connection import SessionLocal
from backend.database.models import Property
from backend.nlp.analyzer import analizar_texto
from backend.nlp.keyword_filter import VISION_VACIA
from backend.scoring.calculator import calcular_score
from backend.vision.image_analyzer import analizar_imagenes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_lock = threading.Lock()
_stats = {"analizadas": 0, "nlp": 0, "vision": 0, "errores": 0, "total": 0, "inicio": 0.0}
_progress_queue: queue.Queue | None = None

_VISION_LOGGERS = [
    "backend.vision.image_analyzer",
    "backend.nlp.analyzer",
]


class _QueueHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record):
        try:
            self.q.put_nowait(self.format(record))
        except queue.Full:
            pass


def _emit(msg: str) -> None:
    logger.info(msg)
    if _progress_queue:
        try:
            _progress_queue.put_nowait(msg)
        except queue.Full:
            pass


def _emit_progress() -> None:
    s = _stats
    elapsed = time.time() - s["inicio"]
    rate = s["analizadas"] / elapsed if elapsed > 0 else 0
    restantes = s["total"] - s["analizadas"]
    eta_s = int(restantes / rate) if rate > 0 else 0
    eta_str = f"{eta_s//3600}h {(eta_s%3600)//60}m" if eta_s > 3600 else f"{eta_s//60}m {eta_s%60}s"
    _emit(
        f"PROGRESS:{s['analizadas']}:{s['total']}:{s['nlp']}:{s['vision']}:{s['errores']} "
        f"| {s['analizadas']}/{s['total']} | visión={s['vision']} | err={s['errores']} | ETA {eta_str}"
    )


def _procesar(prop_id: int) -> None:
    db = SessionLocal()
    try:
        prop = db.query(Property).filter(Property.id == prop_id).first()
        if not prop or prop.analizado:
            return

        nlp = analizar_texto(prop.descripcion)
        with _lock:
            _stats["nlp"] += 1

        nlp_positivo = any(v for k, v in nlp.items() if k != "confianza" and v is True)
        if nlp_positivo:
            vision = analizar_imagenes(prop.fotos_urls)
            with _lock:
                _stats["vision"] += 1
        else:
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
            if _stats["analizadas"] % 25 == 0:
                _emit_progress()

    except Exception as e:
        db.rollback()
        with _lock:
            _stats["errores"] += 1
        logger.error(f"Error prop {prop_id}: {e}")
    finally:
        db.close()


def main(workers: int = 10, fuente: str | None = None, progress_queue: queue.Queue | None = None) -> int:
    global _progress_queue, _stats
    _progress_queue = progress_queue
    _stats = {"analizadas": 0, "nlp": 0, "vision": 0, "errores": 0, "total": 0, "inicio": time.time()}

    handler = None
    if progress_queue:
        handler = _QueueHandler(progress_queue)
        handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
        for name in _VISION_LOGGERS:
            logging.getLogger(name).addHandler(handler)

    db = SessionLocal()
    query = db.query(Property.id).filter(Property.activa == True, Property.analizado == False)
    if fuente:
        query = query.filter(Property.fuente == fuente)
    ids = [row[0] for row in query.all()]
    db.close()

    total = len(ids)
    _stats["total"] = total

    if not total:
        _emit("No hay propiedades pendientes.")
        return 0

    _emit(f"Procesando {total} propiedades con {workers} workers...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_procesar, pid): pid for pid in ids}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error inesperado: {e}")

    s = _stats
    _emit(f"Finalizado. {s['analizadas']} analizadas | {s['nlp']} NLP | {s['vision']} visión | {s['errores']} errores.")

    if handler:
        for name in _VISION_LOGGERS:
            logging.getLogger(name).removeHandler(handler)

    return s["analizadas"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--fuente", type=str, default=None)
    args = parser.parse_args()
    main(workers=args.workers, fuente=args.fuente)
