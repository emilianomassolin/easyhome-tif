"""
Utilidad de deduplicación para scrapers.
Antes de insertar una propiedad nueva chequea si ya existe una similar
en otra fuente y, de ser así, marca la nueva como duplicado.

Criterios combinados:
  - Dirección similar (pg_trgm) — umbral base 0.80
  - Precio ±10%
  - Mismo tipo_operacion
  - Fuente distinta
  - Bonus: si m² y/o ambientes coinciden se baja el umbral de dirección a 0.65
"""

from sqlalchemy.orm import Session
from sqlalchemy import text


_BASE_SIM   = 0.80   # umbral dirección sin datos estructurales
_BONUS_SIM  = 0.65   # umbral cuando m² y/o ambientes también coinciden
_PRICE_TOL  = 0.10   # ±10% precio
_SUP_TOL    = 0.15   # ±15% superficie


def find_canonical(
    db: Session,
    ubicacion: str,
    precio: float,
    tipo_operacion: str,
    fuente: str,
    superficie_m2: float | None = None,
    ambientes: int | None = None,
) -> int | None:
    """
    Devuelve el id de una propiedad canónica si esta nueva es duplicado.
    Retorna None si no hay duplicado.
    """
    if not ubicacion or len(ubicacion) < 15 or not precio or not tipo_operacion:
        return None

    # Si tenemos datos estructurales podemos usar umbral más bajo
    tiene_extras = superficie_m2 is not None or ambientes is not None
    sim_threshold = _BONUS_SIM if tiene_extras else _BASE_SIM

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
              AND (
                -- Sin datos estructurales: solo dirección+precio
                (:sup IS NULL AND :amb IS NULL)
                OR
                -- Con superficie: debe coincidir ±15%
                (:sup IS NOT NULL AND superficie_m2 IS NOT NULL
                 AND abs(superficie_m2 - :sup) / NULLIF(greatest(superficie_m2, :sup), 0) < :sup_tol)
                OR
                -- Con ambientes: debe coincidir exacto
                (:amb IS NOT NULL AND ambientes IS NOT NULL AND ambientes = :amb)
              )
            ORDER BY similarity(ubicacion, :ubic) DESC, id ASC
            LIMIT 1
        """),
        {
            "fuente":     fuente,
            "ubic":       ubicacion,
            "precio":     precio,
            "tipo_op":    tipo_operacion,
            "sim_thr":    sim_threshold,
            "price_tol":  _PRICE_TOL,
            "sup":        superficie_m2,
            "amb":        ambientes,
            "sup_tol":    _SUP_TOL,
        },
    ).first()

    return row[0] if row else None
