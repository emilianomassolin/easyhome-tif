import json
import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

FACU_API_BASE = os.getenv("FACU_API_BASE", "https://ai.cloud.um.edu.ar")
FACU_API_KEY  = os.getenv("FACU_API_KEY")
FACU_MODEL    = os.getenv("FACU_MODEL", "gemma4-e2b")

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


def analizar_texto(descripcion: str | None) -> dict:
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
        texto = resp.json()["choices"][0]["message"]["content"].strip()
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        resultado = json.loads(texto.strip())
        detectados = sum(1 for k, v in resultado.items() if k != "confianza" and v is True)
        logger.info(f"NLP completado. Criterios detectados: {detectados}")
        return resultado

    except Exception as e:
        logger.error(f"Error en análisis NLP: {e}")
        return vacio
