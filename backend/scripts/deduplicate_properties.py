"""
Detecta y marca propiedades duplicadas entre fuentes distintas.

Criterios para considerar duplicado:
  - Misma ubicacion (similitud pg_trgm >= 0.80)
  - Precio dentro del ±10%
  - Mismo tipo_operacion
  - Fuente distinta

Canónica = la que tiene más fotos; en empate, la de menor id (más antigua).
El duplicado queda con duplicate_of = id_canónica.

Uso:
    python -m backend.scripts.deduplicate_properties
    python -m backend.scripts.deduplicate_properties --db postgresql://... --dry-run
"""

import argparse
import logging
import os
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.80
PRICE_TOLERANCE = 0.10  # ±10%

FIND_PAIRS_SQL = text("""
    SELECT
        a.id  AS id_a,
        b.id  AS id_b,
        -- Canónica = más fotos, si empate la más antigua (menor id)
        CASE
            WHEN COALESCE(jsonb_array_length(a.fotos_urls), 0) >=
                 COALESCE(jsonb_array_length(b.fotos_urls), 0)
            THEN a.id ELSE b.id
        END AS canonical_id,
        CASE
            WHEN COALESCE(jsonb_array_length(a.fotos_urls), 0) >=
                 COALESCE(jsonb_array_length(b.fotos_urls), 0)
            THEN b.id ELSE a.id
        END AS duplicate_id,
        round(similarity(a.ubicacion, b.ubicacion)::numeric, 3) AS sim,
        a.ubicacion AS ubic_a,
        b.ubicacion AS ubic_b,
        a.precio AS precio_a,
        b.precio  AS precio_b,
        a.fuente  AS fuente_a,
        b.fuente  AS fuente_b,
        a.tipo_operacion
    FROM properties a
    JOIN properties b ON a.id < b.id
    WHERE a.fuente          != b.fuente
      AND a.activa          = true
      AND b.activa          = true
      AND a.duplicate_of    IS NULL
      AND b.duplicate_of    IS NULL
      AND a.ubicacion       IS NOT NULL
      AND b.ubicacion       IS NOT NULL
      AND length(a.ubicacion) > 15
      AND length(b.ubicacion) > 15
      AND a.precio          IS NOT NULL
      AND b.precio          IS NOT NULL
      AND a.tipo_operacion  IS NOT NULL
      AND a.tipo_operacion  = b.tipo_operacion
      AND similarity(a.ubicacion, b.ubicacion) >= :sim_threshold
      AND abs(a.precio - b.precio)
          / NULLIF(greatest(a.precio, b.precio), 0) < :price_tol
    ORDER BY sim DESC, canonical_id
""")

MARK_DUPLICATE_SQL = text("""
    UPDATE properties
    SET duplicate_of = :canonical_id,
        fecha_actualizacion = now()
    WHERE id = :duplicate_id
      AND duplicate_of IS NULL
""")


def run(db_url: str, dry_run: bool):
    engine = create_engine(db_url)
    with engine.connect() as conn:
        log.info("Buscando pares duplicados...")
        rows = conn.execute(
            FIND_PAIRS_SQL,
            {"sim_threshold": SIMILARITY_THRESHOLD, "price_tol": PRICE_TOLERANCE},
        ).fetchall()
        log.info(f"Pares encontrados: {len(rows)}")

        # Un id solo puede ser duplicado de uno (el primero que se encuentre)
        already_marked: set[int] = set()
        to_mark: list[tuple[int, int]] = []

        for r in rows:
            dup_id = r.duplicate_id
            can_id = r.canonical_id
            if dup_id in already_marked or can_id in already_marked:
                continue
            already_marked.add(dup_id)
            to_mark.append((can_id, dup_id))
            log.info(
                f"  DUP {dup_id} → CANON {can_id} "
                f"[{r.fuente_a}↔{r.fuente_b}] "
                f"sim={r.sim} "
                f"'{r.ubic_a[:40]}' ≈ '{r.ubic_b[:40]}' "
                f"${r.precio_a:.0f}≈${r.precio_b:.0f}"
            )

        if dry_run:
            log.info(f"[DRY-RUN] Se marcarían {len(to_mark)} duplicados. Nada escrito.")
            return

        marked = 0
        for canonical_id, duplicate_id in to_mark:
            result = conn.execute(
                MARK_DUPLICATE_SQL,
                {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )
            marked += result.rowcount
        conn.commit()
        log.info(f"Duplicados marcados: {marked}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL", "postgresql://easyhome_user:1234@localhost/easyhome"),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo muestra qué se marcaría, sin escribir en la DB",
    )
    args = parser.parse_args()
    run(args.db, args.dry_run)


if __name__ == "__main__":
    main()
