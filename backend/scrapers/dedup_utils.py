"""
Utilidad de deduplicación para scrapers.
Antes de insertar una propiedad nueva, chequea si ya existe una similar
en otra fuente y, de ser así, marca la nueva como duplicado.
"""

from sqlalchemy.orm import Session
from sqlalchemy import text


SIMILARITY_THRESHOLD = 0.80
PRICE_TOLERANCE = 0.10


def find_canonical(db: Session, ubicacion: str, precio: float, tipo_operacion: str, fuente: str) -> int | None:
    """
    Devuelve el id de una propiedad canónica existente si esta nueva es duplicado.
    Retorna None si no hay duplicado.
    """
    if not ubicacion or len(ubicacion) < 15 or not precio or not tipo_operacion:
        return None

    row = db.execute(
        text("""
            SELECT id FROM properties
            WHERE fuente != :fuente
              AND activa = true
              AND duplicate_of IS NULL
              AND ubicacion IS NOT NULL
              AND length(ubicacion) > 15
              AND precio IS NOT NULL
              AND tipo_operacion = :tipo_op
              AND similarity(ubicacion, :ubic) >= :sim_thr
              AND abs(precio - :precio) / NULLIF(greatest(precio, :precio), 0) < :price_tol
            ORDER BY similarity(ubicacion, :ubic) DESC, id ASC
            LIMIT 1
        """),
        {
            "fuente": fuente,
            "ubic": ubicacion,
            "precio": precio,
            "tipo_op": tipo_operacion,
            "sim_thr": SIMILARITY_THRESHOLD,
            "price_tol": PRICE_TOLERANCE,
        },
    ).first()

    return row[0] if row else None
