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
    "acceso ancho",
    # Sin escalones
    "sin escalones", "sin escalón", "sin escalera", "acceso directo",
    "nivel del suelo", "a nivel",
    # Piso plano
    "piso plano", "sin desnivel", "sin desniveles", "superficie plana",
    "piso nivelado",
    # Estacionamiento adaptado
    "cochera adaptada", "estacionamiento adaptado", "lugar para discapacitado",
    "pmd", "estacionamiento pmd", "cochera pmd",
    # Ducha a nivel de piso
    "ducha italiana", "ducha a nivel", "ducha sin bañera", "ducha sin escalon",
    "ducha sin escalón", "ducha nivelada",
    # Pasamanos / barandas
    "pasamanos", "baranda", "barandal", "barandas", "baranda de seguridad",
    # Planta baja
    "planta baja", "piso bajo", "sin escaleras internas",
    # Piso antideslizante
    "piso antideslizante", "antideslizante", "piso de seguridad",
    "superficie antideslizante",
    # Pasillo ancho
    "pasillo ancho", "pasillos anchos", "pasillo amplio", "corredor ancho",
    # Términos generales de accesibilidad
    "accesible", "accesibilidad", "discapacidad", "discapacitado",
    "movilidad reducida", "silla de ruedas", "silla ruedas",
    "adulto mayor", "adultos mayores", "tercera edad",
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
    "ducha_nivel_piso": False,
    "pasamanos": False,
    "planta_baja": False,
    "piso_antideslizante": False,
    "pasillo_ancho": False,
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
    "ducha_nivel_piso": False,
    "pasamanos": False,
    "planta_baja": False,
    "piso_antideslizante": False,
    "pasillo_ancho": False,
    "imagenes_analizadas": 0,
    "descripciones": [],
}
