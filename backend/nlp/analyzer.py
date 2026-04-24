import json
import logging
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROMPT = """Analizá la siguiente descripción de una propiedad inmobiliaria y detectá si menciona
características de accesibilidad para personas con movilidad reducida.

Descripción:
{descripcion}

Respondé ÚNICAMENTE con un JSON válido con esta estructura (sin texto adicional):
{{
  "rampa": true/false,
  "ascensor": true/false,
  "bano_adaptado": true/false,
  "entrada_ancha": true/false,
  "sin_escalones": true/false,
  "piso_plano": true/false,
  "estacionamiento_adaptado": true/false,
  "confianza": 0.0-1.0
}}

Criterios:
- rampa: menciona rampa, rampa de acceso o acceso sin escalones en la entrada
- ascensor: menciona ascensor o elevador
- bano_adaptado: menciona baño adaptado, baño para discapacitados o barras de apoyo
- entrada_ancha: menciona puerta ancha, entrada amplia o acceso amplio
- sin_escalones: menciona planta baja, sin escalones o entrada al mismo nivel
- piso_plano: menciona piso plano, sin desniveles o superficie uniforme
- estacionamiento_adaptado: menciona cochera adaptada, estacionamiento PMD o lugar para discapacitados
- confianza: qué tan seguro estás de tu análisis (1.0 = muy seguro, 0.0 = sin información)"""


def analizar_texto(descripcion: str | None) -> dict:
    if not descripcion or not descripcion.strip():
        logger.warning("Descripción vacía, devolviendo resultado nulo.")
        return {c: False for c in ["rampa", "ascensor", "bano_adaptado", "entrada_ancha",
                                    "sin_escalones", "piso_plano", "estacionamiento_adaptado"]} | {"confianza": 0.0}

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": PROMPT.format(descripcion=descripcion)}],
        )
        texto = response.content[0].text.strip()
        # Eliminar bloques markdown si Claude los incluye
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        resultado = json.loads(texto.strip())
        logger.info(f"NLP completado. Criterios detectados: {sum(1 for v in resultado.values() if v is True)}")
        return resultado

    except Exception as e:
        logger.error(f"Error en análisis NLP: {e}")
        return {c: False for c in ["rampa", "ascensor", "bano_adaptado", "entrada_ancha",
                                    "sin_escalones", "piso_plano", "estacionamiento_adaptado"]} | {"confianza": 0.0}
