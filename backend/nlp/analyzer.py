import json
import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

FACU_API_BASE = os.getenv("FACU_API_BASE", "https://ai.cloud.um.edu.ar")
FACU_API_KEY  = os.getenv("FACU_API_KEY")
FACU_MODEL    = os.getenv("FACU_MODEL", "gemma4-26b")

CRITERIOS_NLP = [
    "rampa", "ascensor", "bano_adaptado", "entrada_ancha",
    "estacionamiento_adaptado", "ducha_nivel_piso",
    "pasamanos", "planta_baja",
]

PROMPT = """Descripción de propiedad: {descripcion}

Detectá si la descripción menciona estas características de accesibilidad. Respondé SOLO con JSON válido:
{{"rampa":false,"ascensor":false,"bano_adaptado":false,"entrada_ancha":false,"estacionamiento_adaptado":false,"ducha_nivel_piso":false,"pasamanos":false,"planta_baja":false,"confianza":0.5}}

Reglas: rampa=true si menciona rampa. ascensor=true si menciona ascensor/elevador. bano_adaptado=true si menciona baño adaptado/barras de apoyo/ducha accesible. entrada_ancha=true si menciona puerta/entrada ancha. estacionamiento_adaptado=true si menciona cochera/estacionamiento PMD. ducha_nivel_piso=true si menciona ducha italiana/a nivel/sin escalón. pasamanos=true si menciona pasamanos/baranda. planta_baja=true si menciona planta baja/sin escaleras internas. confianza: 0.9 si hay menciones claras, 0.5 si es dudoso, 0.1 si no hay nada.

JSON:"""


def analizar_texto(descripcion: str | None) -> dict | None:
    """Devuelve los criterios detectados en el texto, o None si la API de NLP
    falló (timeout, error HTTP, respuesta inesperada). El caller debe tratar
    None como 'no analizado' y reintentar luego, en vez de marcar la propiedad
    como analizada sin accesibilidad (falso negativo)."""
    vacio = {c: False for c in CRITERIOS_NLP} | {"confianza": 0.0}

    if not descripcion or not descripcion.strip():
        logger.warning("Descripción vacía, devolviendo resultado nulo.")
        return vacio

    try:
        resp = requests.post(
            f"{FACU_API_BASE}/openai/chat/completions",
            headers={"Authorization": f"Bearer {FACU_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": FACU_MODEL,
                "messages": [{"role": "user", "content": PROMPT.format(descripcion=descripcion)}],
                "max_tokens": 2000,
                "temperature": 0,
            },
            timeout=20,
        )
    except Exception as e:
        logger.error(f"NLP: fallo de conexión con la API: {e}")
        return None

    if resp.status_code != 200:
        logger.error(f"NLP: HTTP {resp.status_code} — {resp.text[:200]}")
        return None

    try:
        texto = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        # La API respondió 200 pero sin el formato esperado (sin 'choices',
        # cuerpo de error, etc.). Logueamos el cuerpo para diagnosticar.
        logger.error(f"NLP: respuesta inesperada ({e}) — {resp.text[:200]}")
        return None

    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    try:
        resultado = json.loads(texto.strip())
    except Exception as e:
        logger.error(f"NLP: JSON inválido del modelo ({e}) — {texto[:200]}")
        return None

    detectados = sum(1 for k, v in resultado.items() if k != "confianza" and v is True)
    logger.info(f"NLP completado. Criterios detectados: {detectados}")
    return resultado
