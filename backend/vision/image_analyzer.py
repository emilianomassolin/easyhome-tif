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
    "sin_escalones", "piso_plano", "estacionamiento_adaptado",
    "ducha_nivel_piso", "pasamanos", "planta_baja",
    "piso_antideslizante", "pasillo_ancho",
]

PROMPT_VISION = """Analizá esta imagen de una propiedad inmobiliaria y detectá visualmente
características de accesibilidad para personas con movilidad reducida, discapacidad o adultos mayores.

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
  "descripcion_visual": "breve descripción de lo que ves relevante para accesibilidad"
}}

Criterios visuales:
- rampa: ves una rampa de acceso en la entrada
- ascensor: ves un ascensor o cabina elevadora
- bano_adaptado: ves barras de apoyo, asientos en la ducha o baño con adaptaciones
- entrada_ancha: ves una puerta o entrada claramente amplia (apta para silla de ruedas)
- sin_escalones: la entrada está al mismo nivel, sin escalones visibles
- piso_plano: el piso es completamente plano sin desniveles
- estacionamiento_adaptado: ves señalización PMD o espacio adaptado para discapacitados
- ducha_nivel_piso: ves una ducha italiana, a nivel del piso, sin escalón ni bañera
- pasamanos: ves pasamanos o barandas en escaleras, rampas o pasillos
- planta_baja: la propiedad es claramente en planta baja o el acceso es sin escaleras
- piso_antideslizante: el piso tiene textura antideslizante visible o cerámica rugosa
- pasillo_ancho: los pasillos o corredores son claramente amplios"""


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
