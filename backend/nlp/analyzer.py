import json
import logging
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CRITERIOS_NLP = [
    "rampa", "ascensor", "bano_adaptado", "entrada_ancha",
    "sin_escalones", "piso_plano", "estacionamiento_adaptado",
    "ducha_nivel_piso", "pasamanos", "planta_baja",
    "piso_antideslizante", "pasillo_ancho",
]

PROMPT = """Analizá la siguiente descripción de una propiedad inmobiliaria y detectá si menciona
características de accesibilidad para personas con movilidad reducida, discapacidad o adultos mayores.

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
  "ducha_nivel_piso": true/false,
  "pasamanos": true/false,
  "planta_baja": true/false,
  "piso_antideslizante": true/false,
  "pasillo_ancho": true/false,
  "confianza": 0.0-1.0
}}

Criterios:
- rampa: menciona rampa o rampa de acceso en la entrada
- ascensor: menciona ascensor o elevador
- bano_adaptado: menciona baño adaptado, baño para discapacitados, barras de apoyo o ducha accesible
- entrada_ancha: menciona puerta ancha, entrada amplia o acceso amplio
- sin_escalones: menciona acceso sin escalones, entrada al mismo nivel o acceso directo
- piso_plano: menciona piso plano, sin desniveles o superficie uniforme
- estacionamiento_adaptado: menciona cochera adaptada, estacionamiento PMD o lugar para discapacitados
- ducha_nivel_piso: menciona ducha a nivel de piso, ducha sin bañera, ducha sin escalón o ducha italiana
- pasamanos: menciona pasamanos, baranda, barandal o baranda de seguridad en escalera
- planta_baja: menciona planta baja, piso bajo o sin escaleras internas
- piso_antideslizante: menciona piso antideslizante, piso de seguridad o superficie antideslizante
- pasillo_ancho: menciona pasillo ancho, pasillo amplio o corredor ancho
- confianza: qué tan seguro estás de tu análisis (1.0 = muy seguro, 0.0 = sin información)"""


def analizar_texto(descripcion: str | None) -> dict:
    if not descripcion or not descripcion.strip():
        logger.warning("Descripción vacía, devolviendo resultado nulo.")
        return {c: False for c in CRITERIOS_NLP} | {"confianza": 0.0}

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": PROMPT.format(descripcion=descripcion)}],
        )
        texto = response.content[0].text.strip()
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        resultado = json.loads(texto.strip())
        logger.info(f"NLP completado. Criterios detectados: {sum(1 for v in resultado.values() if v is True)}")
        return resultado

    except Exception as e:
        logger.error(f"Error en análisis NLP: {e}")
        return {c: False for c in CRITERIOS_NLP} | {"confianza": 0.0}
