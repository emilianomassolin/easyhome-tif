CRITERIOS = [
    "rampa",
    "ascensor",
    "bano_adaptado",
    "entrada_ancha",
    "estacionamiento_adaptado",
    "ducha_nivel_piso",
    "pasamanos",
    "planta_baja",
]

PESO_TEXTO  = 0.6
PESO_VISION = 0.4

NIVELES = [
    (8.5, "Muy accesible"),
    (6.0, "Accesible"),
    (3.5, "Parcialmente accesible"),
    (0.0, "Poco accesible"),
]

# Criterios que NO aplican según el tipo de propiedad
CRITERIOS_EXCLUIDOS = {
    "cochera": {
        "ascensor", "bano_adaptado", "ducha_nivel_piso",
        "pasamanos", "entrada_ancha",
    },
    "terreno": {
        "ascensor", "bano_adaptado", "ducha_nivel_piso",
        "pasamanos", "entrada_ancha",
    },
    "galpon": {
        "ascensor", "bano_adaptado", "ducha_nivel_piso", "pasamanos",
    },
    "local": {
        "bano_adaptado", "ducha_nivel_piso",
    },
}

_TIPOS_KEYWORDS = {
    "cochera": ["cochera", "garage", "garaje", "estacionamiento solo", "box de estacionamiento"],
    "terreno": ["terreno", "lote", "fraccion", "fracción", "campo", "chacra", "finca"],
    "galpon":  ["galpón", "galpon", "deposito", "depósito", "nave industrial", "bodega"],
    "local":   ["local", "comercial", "negocio", "consultorio"],
}


def detectar_tipo(titulo: str | None) -> str:
    if not titulo:
        return "otro"
    t = titulo.lower()
    for tipo, keywords in _TIPOS_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return tipo
    return "otro"


def _criterios_aplicables(tipo: str) -> list[str]:
    excluidos = CRITERIOS_EXCLUIDOS.get(tipo, set())
    return [c for c in CRITERIOS if c not in excluidos]


def calcular_score(nlp_resultado: dict, vision_resultado: dict, titulo: str | None = None) -> dict:
    tipo = detectar_tipo(titulo)
    aplicables = _criterios_aplicables(tipo)

    detectados_texto  = [c for c in aplicables if nlp_resultado.get(c)]
    detectados_vision = [c for c in aplicables if vision_resultado.get(c)]
    detectados_total  = list(set(detectados_texto + detectados_vision))

    score_final = round(len(detectados_total) / len(aplicables) * 10, 2)

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
        "criterios_detectados": {c: c in detectados_total for c in aplicables},
        "justificacion": justificacion,
        "confianza": confianza,
        "tipo_propiedad": tipo,
    }


def _generar_justificacion(detectados_texto: list, detectados_vision: list, score: float) -> str:
    NOMBRES = {
        "rampa":                    "Rampa de acceso",
        "ascensor":                 "Ascensor",
        "bano_adaptado":            "Baño adaptado",
        "entrada_ancha":            "Entrada ancha",
        "sin_escalones":            "Sin escalones en acceso",
        "piso_plano":               "Piso plano",
        "estacionamiento_adaptado": "Estacionamiento adaptado",
        "ducha_nivel_piso":         "Ducha a nivel de piso",
        "pasamanos":                "Pasamanos / barandas",
        "planta_baja":              "Planta baja",
        "pasillo_ancho":            "Pasillo ancho",
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
