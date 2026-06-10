"""
Extrae datos estructurados (superficie, ambientes) de texto libre.
Usado en scrapers y en el script de backfill.
"""

import re


_SUPERFICIE_PATTERNS = [
    # "211 m² Cub." / "211 m2 cub" → prioridad: cubierta
    re.compile(r'(\d+(?:[.,]\d+)?)\s*m[²2]\s*[Cc]ub', re.IGNORECASE),
    # "50 m² Tot." / "50 M2"
    re.compile(r'(\d+(?:[.,]\d+)?)\s*[Mm][²2](?:\s*[Tt]ot)?', re.IGNORECASE),
    # "68 mts2" / "68mts"
    re.compile(r'(\d+(?:[.,]\d+)?)\s*mts?2?', re.IGNORECASE),
    # "500 metros cuadrados"
    re.compile(r'(\d+(?:[.,]\d+)?)\s*metros?\s*cuadrados?', re.IGNORECASE),
]

_AMBIENTES_PATTERNS = [
    # "3 dormitorios" / "2 Dorm."
    re.compile(r'(\d+)\s*(?:dormitorios?|habitaciones?|dorm\.?)', re.IGNORECASE),
    # "3 ambientes"
    re.compile(r'(\d+)\s*ambientes?', re.IGNORECASE),
]


def extraer_superficie(texto: str) -> float | None:
    """Retorna m² cubiertos (o totales si no hay cubiertos). None si no encuentra."""
    if not texto:
        return None
    for pat in _SUPERFICIE_PATTERNS:
        m = pat.search(texto)
        if m:
            val = float(m.group(1).replace(",", "."))
            # Filtrar valores absurdos (< 5 m² o > 50.000 m²)
            if 5 <= val <= 50_000:
                return val
    return None


def extraer_ambientes(texto: str) -> int | None:
    """Retorna número de dormitorios/ambientes. None si no encuentra."""
    if not texto:
        return None
    for pat in _AMBIENTES_PATTERNS:
        m = pat.search(texto)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 20:
                return val
    return None
