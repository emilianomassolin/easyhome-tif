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

CRITERIOS_VISION = [
    "rampa", "ascensor", "bano_adaptado", "entrada_ancha",
    "estacionamiento_adaptado", "ducha_nivel_piso", "pasamanos",
]

PROMPT_VISION = """Analizá esta imagen de una propiedad inmobiliaria y detectá visualmente
características de accesibilidad para personas con movilidad reducida, discapacidad o adultos mayores.

Respondé ÚNICAMENTE con un JSON válido con esta estructura (sin texto adicional):
{{
  "rampa": true/false,
  "ascensor": true/false,
  "bano_adaptado": true/false,
  "entrada_ancha": true/false,
  "estacionamiento_adaptado": true/false,
  "ducha_nivel_piso": true/false,
  "pasamanos": true/false,
  "descripcion_visual": "breve descripción de lo que ves relevante para accesibilidad"
}}

Criterios visuales:
- rampa: ves una rampa de acceso en la entrada
- ascensor: ves un ascensor o cabina elevadora
- bano_adaptado: ves barras de apoyo, asientos en la ducha o baño con adaptaciones
- entrada_ancha: ves una puerta de acceso peatonal a la vivienda claramente amplia (apta para silla de ruedas). NO aplica a cocheras, garajes ni entradas vehiculares
- estacionamiento_adaptado: ves claramente el símbolo internacional de discapacidad (silla de ruedas) pintado en el piso o una señal de accesibilidad/PMD visible en el espacio de estacionamiento. NO lo marques si solo ves una cochera o garaje sin esa señalización
- ducha_nivel_piso: ves una ducha italiana, a nivel del piso, sin escalón ni bañera
- pasamanos: ves pasamanos o barandas en escaleras, rampas o pasillos
"""


def _url_a_base64(url: str) -> tuple[str, str] | None:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()

        if len(resp.content) > 5 * 1024 * 1024:
            logger.warning(f"Imagen muy grande ({len(resp.content)//1024}KB), saltando: {url}")
            return None

        # Detectar tipo real por magic bytes en lugar de confiar en el header
        content = resp.content
        if content[:8] == b'\x89PNG\r\n\x1a\n':
            content_type = "image/png"
        elif content[:2] == b'\xff\xd8':
            content_type = "image/jpeg"
        elif content[:6] in (b'GIF87a', b'GIF89a'):
            content_type = "image/gif"
        elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
            content_type = "image/webp"
        else:
            content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]

        data = base64.standard_b64encode(content).decode("utf-8")
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
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
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
    if not fotos_urls:
        logger.warning("Sin fotos para analizar.")
        return {c: False for c in CRITERIOS_VISION} | {"imagenes_analizadas": 0, "descripciones": []}

    resultados = []
    for url in fotos_urls[:3]:
        r = _analizar_imagen(url)
        if r:
            resultados.append(r)

    if not resultados:
        return {c: False for c in CRITERIOS_VISION} | {"imagenes_analizadas": 0, "descripciones": []}

    combinado = {c: any(r.get(c, False) for r in resultados) for c in CRITERIOS_VISION}
    combinado["imagenes_analizadas"] = len(resultados)
    combinado["descripciones"] = [r.get("descripcion_visual", "") for r in resultados if r.get("descripcion_visual")]

    logger.info(f"Visión completada. {len(resultados)} imágenes analizadas.")
    return combinado
