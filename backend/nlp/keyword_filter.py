"""
Pre-filtro de palabras clave de accesibilidad.

Antes de llamar a Claude, verifica si la propiedad menciona alguna
característica de accesibilidad. Si no hay ninguna coincidencia,
devuelve resultado vacío sin gastar tokens de API.
"""

KEYWORDS = [
    # Rampa
    "rampa", "rampas",
    # Ascensor
    "ascensor", "ascensores", "elevador", "elevadores",
    # Baño adaptado
    "baño adaptado", "bano adaptado", "baño para discapacitado",
    "barras de apoyo", "barra de apoyo", "ducha accesible",
    # Entrada ancha
    "puerta ancha", "puertas anchas", "entrada ancha", "acceso amplio",
    "acceso ancho", "pasillo ancho", "pasillos anchos",
    # Sin escalones
    "planta baja", "sin escalones", "sin escalón", "sin escalera",
    "acceso directo", "nivel del suelo", "a nivel",
    # Piso plano
    "piso plano", "sin desnivel", "sin desniveles", "superficie plana",
    "piso nivelado",
    # Estacionamiento adaptado
    "cochera adaptada", "estacionamiento adaptado", "lugar para discapacitado",
    "pmd", "estacionamiento pmd", "cochera pmd",
    # Términos generales de accesibilidad
    "accesible", "accesibilidad", "discapacidad", "discapacitado",
    "movilidad reducida", "silla de ruedas", "silla ruedas",
    "adulto mayor", "adultos mayores",
]


def tiene_keywords_accesibilidad(titulo: str | None, descripcion: str | None) -> bool:
    texto = " ".join(filter(None, [titulo, descripcion])).lower()
    if not texto:
        return False
    return any(kw in texto for kw in KEYWORDS)


RESULTADO_VACIO = {
    "rampa": False,
    "ascensor": False,
    "bano_adaptado": False,
    "entrada_ancha": False,
    "sin_escalones": False,
    "piso_plano": False,
    "estacionamiento_adaptado": False,
    "confianza": 0.0,
}

VISION_VACIA = {
    "rampa": False,
    "ascensor": False,
    "bano_adaptado": False,
    "entrada_ancha": False,
    "sin_escalones": False,
    "piso_plano": False,
    "estacionamiento_adaptado": False,
    "imagenes_analizadas": 0,
    "descripciones": [],
}
