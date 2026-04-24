import base64
import json
import logging
import os

import anthropic
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROMPT_VISION = """Analizá esta imagen de una propiedad inmobiliaria y detectá visualmente
características de accesibilidad para personas con movilidad reducida.

Respondé ÚNICAMENTE con un JSON válido con esta estructura (sin texto adicional):
{{
  "rampa": true/false,
  "ascensor": true/false,
  "bano_adaptado": true/false,
  "entrada_ancha": true/false,
  "sin_escalones": true/false,
  "piso_plano": true/false,
  "estacionamiento_adaptado": true/false,
  "descripcion_visual": "breve descripción de lo que ves relevante para accesibilidad"
}}"""


def _url_a_base64(url: str) -> tuple[str, str] | None:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        data = base64.standard_b64encode(resp.content).decode("utf-8")
        return data, content_type
    except Exception as e:
        logger.warning(f"No se pudo descargar imagen {url}: {e}")
        return None


def _analizar_imagen(url: str) -> dict | None:
    resultado = _url_a_base64(url)
    if not resultado:
        return None

    data, content_type = resultado

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": content_type, "data": data}},
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


def analizar_imagenes(fotos_urls: list[str] | None) -> dict:
    criterios_base = ["rampa", "ascensor", "bano_adaptado", "entrada_ancha",
                      "sin_escalones", "piso_plano", "estacionamiento_adaptado"]

    if not fotos_urls:
        logger.warning("Sin fotos para analizar.")
        return {c: False for c in criterios_base} | {"imagenes_analizadas": 0, "descripciones": []}

    resultados = []
    for url in fotos_urls[:5]:  # máximo 5 fotos por propiedad
        r = _analizar_imagen(url)
        if r:
            resultados.append(r)

    if not resultados:
        return {c: False for c in criterios_base} | {"imagenes_analizadas": 0, "descripciones": []}

    # Un criterio se considera detectado si aparece en AL MENOS una imagen
    combinado = {c: any(r.get(c, False) for r in resultados) for c in criterios_base}
    combinado["imagenes_analizadas"] = len(resultados)
    combinado["descripciones"] = [r.get("descripcion_visual", "") for r in resultados if r.get("descripcion_visual")]

    logger.info(f"Visión completada. {len(resultados)} imágenes analizadas.")
    return combinado
