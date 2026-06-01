"""
Pre-filtro de palabras clave de accesibilidad.

Antes de llamar a Claude, verifica si la propiedad menciona alguna
característica de accesibilidad. Si no hay ninguna coincidencia,
devuelve resultado vacío sin gastar tokens de API.
"""

KEYWORDS = [
    # Rampa
    "rampa", "rampas", "rampa de acceso", "acceso rampeado",
    # Ascensor
    "ascensor", "ascensores", "elevador", "elevadores",
    "plataforma elevadora", "silla salvaescaleras", "salvaescaleras", "lift",
    # Baño adaptado
    "baño adaptado", "bano adaptado", "baño para discapacitado",
    "baño accesible", "bano accesible", "baño especial",
    "barras de apoyo", "barra de apoyo", "barra de seguridad", "barrales", "barral",
    "ducha accesible", "ducha adaptada", "asiento de ducha", "silla de baño",
    "inodoro adaptado", "inodoro elevado",
    # Entrada ancha
    "puerta ancha", "puertas anchas", "entrada ancha", "acceso amplio",
    "acceso ancho", "portón ancho", "puerta doble", "portón amplio",
    "entrada accesible", "acceso vehicular amplio",
    # Piso plano
    "piso plano", "sin desnivel", "sin desniveles", "superficie plana",
    "piso nivelado", "piso liso", "sin irregularidades", "piso uniforme",
    # Estacionamiento adaptado
    "cochera adaptada", "estacionamiento adaptado", "lugar para discapacitado",
    "pmd", "estacionamiento pmd", "cochera pmd", "garaje adaptado",
    "lugar pcd", "espacio discapacitado", "parking adaptado",
    # Ducha a nivel de piso
    "ducha italiana", "ducha a nivel", "ducha sin bañera", "ducha sin escalon",
    "ducha sin escalón", "ducha nivelada", "ducha de piso", "ducha rasante",
    "walk-in shower", "ducha a ras",
    # Pasamanos / barandas
    "pasamanos", "baranda", "barandal", "barandas", "baranda de seguridad",
    "baranda de apoyo", "balaustrada", "apoyo en escalera", "baranda lateral",
    # Planta baja
    "planta baja", "piso bajo", "sin escaleras internas", "pb ",
    "departamento en pb", "casa en pb", "al frente planta baja",
    # Pasillo ancho
    "pasillo ancho", "pasillos anchos", "pasillo amplio", "corredor ancho",
    "corredor amplio", "hall amplio", "circulación amplia",
    # Términos generales de accesibilidad
    "accesible", "accesibilidad", "discapacidad", "discapacitado",
    "movilidad reducida", "silla de ruedas", "silla ruedas",
    "adulto mayor", "adultos mayores", "tercera edad",
    "persona con discapacidad", "pcd", "pmr",
    "diseño universal", "arquitectura accesible", "sin barreras arquitectónicas",
    "apto discapacitado", "apto para discapacitado", "adaptado para",
    # Movilidad / equipamiento
    "andador", "bastón", "muletas", "silla ortopédica",
    # Cuidado y salud
    "convalecencia", "rehabilitación", "postoperatorio", "cuidador",
    "adulto independiente",
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
    "estacionamiento_adaptado": False,
    "ducha_nivel_piso": False,
    "pasamanos": False,
    "planta_baja": False,
    "confianza": 0.0,
}

VISION_VACIA = {
    "rampa": False,
    "ascensor": False,
    "bano_adaptado": False,
    "entrada_ancha": False,
    "estacionamiento_adaptado": False,
    "ducha_nivel_piso": False,
    "pasamanos": False,
    "imagenes_analizadas": 0,
    "descripciones": [],
}
