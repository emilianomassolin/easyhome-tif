"""
Actualiza fotos de ZonaProp existentes con ≤1 foto via FlareSolverr.
Usa múltiples workers en paralelo para mayor velocidad.

Uso en VM:
    cd /opt/easyhome
    python -m backend.scripts.update_zonaprop_photos --workers 2 --delay 2.0

Uso local (con SSH tunnel al PostgreSQL de la VM en puerto 5433):
    ssh -L 5433:localhost:5432 ubuntu@10.201.3.235 -N &
    cd /home/thinkpademi/Documentos/easyhome-tif
    python -m backend.scripts.update_zonaprop_photos \
        --workers 8 --delay 1.5 \
        --flaresolverr http://localhost:8192/v1 \
        --db postgresql://easyhome_user:easyhome2026@localhost:5433/easyhome \
        --log update_photos_local.log
"""

import argparse
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

BASE_URL = "https://www.zonaprop.com.ar"

# Se configuran en main() según args
FLARESOLVERR_URL = None
SessionLocal = None
SESSION_PREFIX = "zp_photo"
root_logger = logging.getLogger(__name__)


def _setup_logging(log_file: str):
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for h in handlers:
        h.setFormatter(h.formatter or fmt)
        h.setFormatter(fmt)
    root_logger.setLevel(logging.INFO)
    for h in handlers:
        root_logger.addHandler(h)


def _setup_db(db_url: str):
    global SessionLocal
    engine = create_engine(db_url, pool_size=10, max_overflow=5)
    SessionLocal = sessionmaker(bind=engine)


def _get_logger(worker_id: int):
    logger = logging.getLogger(f"worker_{worker_id}")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        for h in root_logger.handlers:
            logger.addHandler(h)
    prefix = f"[W{worker_id}]"

    class _Proxy:
        def info(self, msg):    logger.info(f"{prefix} {msg}")
        def warning(self, msg): logger.warning(f"{prefix} {msg}")
        def error(self, msg):   logger.error(f"{prefix} {msg}")
    return _Proxy()


def _fs_create_session(session_id: str):
    try:
        requests.post(FLARESOLVERR_URL, json={"cmd": "sessions.create", "session": session_id}, timeout=30)
    except Exception:
        pass


def _fs_destroy_session(session_id: str):
    try:
        requests.post(FLARESOLVERR_URL, json={"cmd": "sessions.destroy", "session": session_id}, timeout=10)
    except Exception:
        pass


def _fs_get(session_id: str, url: str, retries: int = 3) -> str | None:
    for intento in range(retries):
        try:
            resp = requests.post(
                FLARESOLVERR_URL,
                json={"cmd": "request.get", "url": url, "session": session_id, "maxTimeout": 60000},
                timeout=90,
            )
            data = resp.json()
            if data.get("status") == "ok" and data.get("solution", {}).get("status") == 200:
                return data["solution"]["response"]
        except Exception:
            pass
        time.sleep(4 * (intento + 1))
    return None


def _extraer_fotos(html: str) -> list[str]:
    urls = re.findall(
        r"https://imgar\.zonapropcdn\.com/avisos/[^\s\"']+\.jpg(?:\?[^\s\"']*)?",
        html,
    )
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        base = url.split("?")[0]
        img_id = base.rsplit("/", 1)[-1]
        if "empresas" in url or "logo" in url.lower():
            continue
        if img_id not in seen:
            seen.add(img_id)
            result.append(re.sub(r"/\d+x\d+/", "/720x532/", base))
    return result[:20]


def _extraer_descripcion(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    el = soup.find(class_=re.compile(r"[Dd]escription|[Dd]escripcion|[Dd]etalle"))
    if el:
        return el.get_text(separator=" ", strip=True)[:2000]
    return None


def _worker(worker_id: int, prop_rows: list[tuple], delay: float) -> tuple[int, int, int]:
    """prop_rows: lista de (id, permalink_ml)"""
    log = _get_logger(worker_id)
    session_id = f"{SESSION_PREFIX}_w{worker_id}"
    _fs_create_session(session_id)
    log.info(f"Iniciando. {len(prop_rows)} propiedades asignadas.")

    db = SessionLocal()
    actualizadas = sin_cambio = errores = 0

    try:
        for i, (prop_id, permalink) in enumerate(prop_rows):
            try:
                html = _fs_get(session_id, permalink)
                if not html:
                    errores += 1
                    time.sleep(delay)
                    continue

                fotos = _extraer_fotos(html)
                if len(fotos) <= 1:
                    sin_cambio += 1
                    time.sleep(delay)
                    continue

                desc = _extraer_descripcion(html)

                db.execute(
                    text("""
                        UPDATE properties
                        SET fotos_urls = CAST(:fotos AS jsonb),
                            descripcion = COALESCE(:desc, descripcion),
                            analizado = CASE
                                WHEN :desc IS NOT NULL AND descripcion IS DISTINCT FROM :desc
                                THEN false ELSE analizado END
                        WHERE id = :id
                    """),
                    {"fotos": __import__("json").dumps(fotos), "desc": desc, "id": prop_id},
                )
                db.commit()
                actualizadas += 1

                if (i + 1) % 50 == 0:
                    log.info(f"Progreso: {i+1}/{len(prop_rows)} — {actualizadas} actualizadas, {errores} errores")

                time.sleep(delay)

            except Exception as e:
                log.error(f"Error en prop {prop_id}: {e}")
                errores += 1
                db.rollback()
                time.sleep(delay * 2)

    finally:
        db.close()
        _fs_destroy_session(session_id)

    log.info(f"Finalizado: {actualizadas} actualizadas, {sin_cambio} sin cambio, {errores} errores")
    return actualizadas, sin_cambio, errores


def main():
    global FLARESOLVERR_URL, SESSION_PREFIX

    parser = argparse.ArgumentParser(description="Actualiza fotos ZonaProp vía FlareSolverr")
    parser.add_argument("--workers",        type=int,   default=4,
                        help="Workers paralelos (default: 4)")
    parser.add_argument("--delay",          type=float, default=2.0,
                        help="Segundos entre requests por worker (default: 2.0)")
    parser.add_argument("--limit",          type=int,   default=None,
                        help="Máx propiedades a procesar (default: todas)")
    parser.add_argument("--flaresolverr",   type=str,   default="http://localhost:8191/v1",
                        help="URL de FlareSolverr (default: http://localhost:8191/v1)")
    parser.add_argument("--db",             type=str,
                        default=os.getenv("DATABASE_URL", "postgresql://easyhome_user:easyhome2026@localhost:5432/easyhome"),
                        help="URL de PostgreSQL")
    parser.add_argument("--log",            type=str,   default=None,
                        help="Archivo de log (default: solo consola)")
    parser.add_argument("--session-prefix", type=str,   default="zp_photo",
                        help="Prefijo de sesiones FlareSolverr (default: zp_photo)")
    args = parser.parse_args()

    FLARESOLVERR_URL = args.flaresolverr
    SESSION_PREFIX = args.session_prefix
    _setup_logging(args.log)
    _setup_db(args.db)

    db = SessionLocal()
    rows = db.execute(
        text("""
            SELECT id, permalink_ml FROM properties
            WHERE fuente = 'zonaprop'
              AND activa = true
              AND permalink_ml IS NOT NULL
              AND (fotos_urls IS NULL OR jsonb_array_length(fotos_urls) <= 1)
            ORDER BY id
            LIMIT :lim
        """),
        {"lim": args.limit or 999999},
    ).fetchall()
    db.close()

    total = len(rows)
    root_logger.info(
        f"Total: {total} props | Workers: {args.workers} | "
        f"Delay: {args.delay}s | FS: {FLARESOLVERR_URL} | DB: {args.db[:40]}..."
    )

    if total == 0:
        root_logger.info("Nada que procesar.")
        return

    # Repartir en round-robin entre workers
    chunks = [list(rows[i::args.workers]) for i in range(args.workers)]

    total_act = total_sin = total_err = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_worker, i, chunk, args.delay): i
                   for i, chunk in enumerate(chunks) if chunk}
        for future in as_completed(futures):
            act, sin, err = future.result()
            total_act += act
            total_sin += sin
            total_err += err

    root_logger.info(
        f"\n=== COMPLETADO === "
        f"Actualizadas: {total_act} | Sin cambio: {total_sin} | Errores: {total_err}"
    )


if __name__ == "__main__":
    main()
