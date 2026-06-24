import base64
import io
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import anthropic
import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

logger = logging.getLogger(__name__)
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

FACU_API_BASE = os.getenv("FACU_API_BASE", "https://ai.cloud.um.edu.ar")
FACU_API_KEY = os.getenv("FACU_API_KEY")
FACU_MODEL = os.getenv("FACU_MODEL", "gemma4-26b")

CRITERIOS_VISION = [
    "rampa", "ascensor", "bano_adaptado", "entrada_ancha",
    "estacionamiento_adaptado", "ducha_nivel_piso", "pasamanos",
]

PROMPT_SCORE = """Mirá esta imagen de una propiedad inmobiliaria y evaluá si muestra alguno de estos elementos:
- Rampa de acceso en la entrada
- Ascensor o elevador
- Baño adaptado (barras de apoyo, asiento de ducha, inodoro elevado)
- Puerta o entrada ancha (apta para silla de ruedas)
- Estacionamiento con símbolo de discapacidad (PMD)
- Ducha italiana / a nivel del piso / sin escalón
- Pasamanos o baranda en escalera, rampa o pasillo

Si la imagen muestra claramente alguno de estos elementos → score alto (7-10).
Si la imagen muestra zonas que PODRÍAN tenerlos (entrada, baño, escalera, pasillo) → score medio (4-6).
Si la imagen muestra dormitorio, cocina, living, patio u otras zonas irrelevantes → score bajo (0-3).

Respondé SOLO con un número entero del 0 al 10. Sin texto adicional."""

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


def _a_jpeg_base64(data: str, content_type: str) -> str:
    if content_type == "image/jpeg":
        return data
    raw = base64.standard_b64decode(data)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


_GEMMA_ERROR = -1.0  # centinela: falló la llamada, distinto de score real 0


def _score_imagen_facu(url: str) -> float:
    resultado = _url_a_base64(url)
    if not resultado:
        return _GEMMA_ERROR
    data, content_type = resultado
    try:
        jpeg_data = _a_jpeg_base64(data, content_type)
    except Exception as e:
        logger.warning(f"No se pudo convertir imagen a JPEG {url}: {e}")
        return _GEMMA_ERROR
    try:
        resp = requests.post(
            f"{FACU_API_BASE}/openai/chat/completions",
            headers={
                "Authorization": f"Bearer {FACU_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": FACU_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{jpeg_data}"}},
                        {"type": "text", "text": PROMPT_SCORE},
                    ],
                }],
                "max_tokens": 500,
                "temperature": 0,
            },
            timeout=20,
        )
        texto = resp.json()["choices"][0]["message"].get("content", "0").strip()
        return float(texto.split()[0])
    except Exception as e:
        logger.warning(f"Error scoring imagen {url}: {e}")
        return _GEMMA_ERROR


MIN_SCORE = 3.0  # fotos con score < 3 en todas → skip Claude

def _seleccionar_top_fotos(urls: list[str], n: int = 3) -> list[str]:
    with ThreadPoolExecutor(max_workers=3) as ex:
        raw_scores = list(ex.map(_score_imagen_facu, urls))

    errores = sum(1 for s in raw_scores if s == _GEMMA_ERROR)
    exitosas = len(raw_scores) - errores

    # Gemma caído (>50% de llamadas fallaron) → fallback a primeras N fotos
    if exitosas == 0 or errores / len(raw_scores) > 0.5:
        logger.warning(f"FOTOS FALLBACK — Gemma falló en {errores}/{len(raw_scores)} fotos → usando primeras {n} sin filtrar")
        return urls[:n]

    # Ignorar errores para el ranking, tratar como score 0
    scores = sorted(zip(raw_scores, urls), key=lambda x: x[0], reverse=True)
    scores_validos = [(s, u) for s, u in scores if s != _GEMMA_ERROR]
    max_score = scores_validos[0][0] if scores_validos else 0.0
    score_str = " | ".join(f"{s:.0f}" if s != _GEMMA_ERROR else "ERR" for s, _ in scores)

    if max_score < MIN_SCORE:
        logger.info(f"FOTOS SKIP — {len(urls)} fotos, scores: [{score_str}] → ninguna relevante, no va a Sonnet")
        return []

    top = [url for _, url in scores_validos[:n]]
    logger.info(f"FOTOS OK — {len(urls)} fotos, scores: [{score_str}] → top {n} → van a Sonnet")
    return top


def _analizar_imagen(url: str) -> dict | None:
    resultado = _url_a_base64(url)
    if not resultado:
        return None

    data, content_type = resultado

    try:
        response = claude.messages.create(
            model="claude-sonnet-4-6",
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

    top_fotos = _seleccionar_top_fotos(fotos_urls, n=3)

    if not top_fotos:
        return {c: False for c in CRITERIOS_VISION} | {"imagenes_analizadas": 0, "descripciones": []}

    resultados = []
    for url in top_fotos:
        r = _analizar_imagen(url)
        if r:
            resultados.append(r)

    if not resultados:
        return {c: False for c in CRITERIOS_VISION} | {"imagenes_analizadas": 0, "descripciones": []}

    combinado = {c: any(r.get(c, False) for r in resultados) for c in CRITERIOS_VISION}
    combinado["imagenes_analizadas"] = len(resultados)
    combinado["descripciones"] = [r.get("descripcion_visual", "") for r in resultados if r.get("descripcion_visual")]

    detectados = [k for k in CRITERIOS_VISION if combinado.get(k)]
    if detectados:
        logger.info(f"SONNET DETECTÓ — {detectados} | {' / '.join(combinado['descripciones'][:1])}")
    else:
        logger.info(f"SONNET — {len(resultados)} fotos analizadas, sin criterios detectados")
    return combinado
