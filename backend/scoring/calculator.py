CRITERIOS = [
    "rampa",
    "ascensor",
    "bano_adaptado",
    "entrada_ancha",
    "sin_escalones",
    "piso_plano",
    "estacionamiento_adaptado",
]

PESO_TEXTO  = 0.6
PESO_VISION = 0.4
PUNTOS_POR_CRITERIO = 1.5  # 7 × 1.5 = 10.5 → normalizado a 10

NIVELES = [
    (8.5, "Muy accesible"),
    (6.0, "Accesible"),
    (3.5, "Parcialmente accesible"),
    (0.0, "Poco accesible"),
]


def calcular_score(nlp_resultado: dict, vision_resultado: dict) -> dict:
    detectados_texto  = [c for c in CRITERIOS if nlp_resultado.get(c)]
    detectados_vision = [c for c in CRITERIOS if vision_resultado.get(c)]
    detectados_total  = list(set(detectados_texto + detectados_vision))

    puntos_texto  = len(detectados_texto)  * PUNTOS_POR_CRITERIO
    puntos_vision = len(detectados_vision) * PUNTOS_POR_CRITERIO

    score_texto  = min(puntos_texto  / 10, 1.0)
    score_vision = min(puntos_vision / 10, 1.0)
    score_final  = round((score_texto * PESO_TEXTO + score_vision * PESO_VISION) * 10, 2)

    nivel = next(nombre for umbral, nombre in NIVELES if score_final >= umbral)

    justificacion = _generar_justificacion(detectados_texto, detectados_vision, score_final)

    confianza = round(
        nlp_resultado.get("confianza", 0.5) * PESO_TEXTO +
        (0.8 if vision_resultado.get("imagenes_analizadas", 0) > 0 else 0.3) * PESO_VISION,
        2
    )

    return {
        "score_accesibilidad": score_final,
        "nivel": nivel,
        "criterios_detectados": {c: c in detectados_total for c in CRITERIOS},
        "justificacion": justificacion,
        "confianza": confianza,
    }


def _generar_justificacion(detectados_texto: list, detectados_vision: list, score: float) -> str:
    NOMBRES = {
        "rampa":                   "Rampa de acceso",
        "ascensor":                "Ascensor",
        "bano_adaptado":           "Baño adaptado",
        "entrada_ancha":           "Entrada ancha",
        "sin_escalones":           "Sin escalones",
        "piso_plano":              "Piso plano",
        "estacionamiento_adaptado": "Estacionamiento adaptado",
    }

    partes = []
    todos = set(detectados_texto + detectados_vision)

    for criterio in CRITERIOS:
        if criterio not in todos:
            continue
        en_texto  = criterio in detectados_texto
        en_vision = criterio in detectados_vision
        nombre = NOMBRES[criterio]

        if en_texto and en_vision:
            partes.append(f"{nombre} detectado en descripción e imágenes")
        elif en_texto:
            partes.append(f"{nombre} mencionado en descripción")
        else:
            partes.append(f"{nombre} visible en imágenes")

    if not partes:
        return "No se detectaron características de accesibilidad."

    return ". ".join(partes) + f". Score final: {score}/10."
