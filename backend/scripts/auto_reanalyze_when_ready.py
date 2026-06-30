"""
Dispara el re-análisis automáticamente cuando:
  1. Terminó el backfill de descripciones de ZonaProp (proceso ya no corre), y
  2. El modelo de NLP (gemma4-26b) volvió a responder correctamente.

Chequea cada 5 minutos. Cuando ambas condiciones se cumplen, llama al análisis
masivo con pocos workers (gentil con la GPU compartida de la facultad) y termina.

Uso: setsid nohup .venv/bin/python -m backend.scripts.auto_reanalyze_when_ready > /tmp/auto_reanalyze.log 2>&1 &
"""
import logging
import subprocess
import time

from backend.nlp.analyzer import analizar_texto

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

WORKERS = 5
INTERVALO = 300  # 5 min
DESC_PRUEBA = ("Casa en planta baja con rampa de acceso, baño adaptado con barras de apoyo, "
               "ducha italiana y pasamanos en el pasillo.")


def backfill_corriendo() -> bool:
    r = subprocess.run(["pgrep", "-f", "backfill_zonaprop_desc"], capture_output=True)
    return r.returncode == 0


def nlp_sano() -> bool:
    # analizar_texto devuelve None si la API falla; un dict si responde bien.
    res = analizar_texto(DESC_PRUEBA)
    return res is not None and any(v is True for k, v in res.items() if k != "confianza")


def lanzar_reanalisis():
    # Lo corremos en proceso (no por HTTP) para no depender del server.
    from backend.scripts.analyze_all_fast import main
    logger.info(f"Lanzando re-análisis con {WORKERS} workers...")
    n = main(workers=WORKERS)
    logger.info(f"Re-análisis terminado: {n} propiedades analizadas.")


def main():
    logger.info("Esperando a que termine el backfill y vuelva gemma4-26b...")
    while True:
        if backfill_corriendo():
            logger.info("Backfill todavía corriendo; espero.")
            time.sleep(INTERVALO)
            continue
        if not nlp_sano():
            logger.info("NLP (gemma4-26b) aún no responde bien; espero.")
            time.sleep(INTERVALO)
            continue
        logger.info("Backfill terminado y NLP OK. Disparando re-análisis.")
        lanzar_reanalisis()
        break


if __name__ == "__main__":
    main()
