"""
Extrae superficie_m2 y ambientes de descripciones existentes y los guarda en la DB.

Uso:
    python -m backend.scripts.backfill_superficie
    python -m backend.scripts.backfill_superficie --db postgresql://...
"""

import argparse
import logging
import os
from sqlalchemy import create_engine, text

from backend.scrapers.extract_utils import extraer_superficie, extraer_ambientes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BATCH = 500


def run(db_url: str):
    engine = create_engine(db_url)
    with engine.connect() as conn:
        total = conn.execute(text(
            "SELECT count(*) FROM properties WHERE descripcion IS NOT NULL"
            " AND superficie_m2 IS NULL"
        )).scalar()
        log.info(f"Propiedades con descripción sin superficie: {total}")

        offset = 0
        actualizadas = 0

        while True:
            rows = conn.execute(text(
                "SELECT id, descripcion FROM properties"
                " WHERE descripcion IS NOT NULL AND superficie_m2 IS NULL"
                " ORDER BY id LIMIT :lim OFFSET :off"
            ), {"lim": BATCH, "off": offset}).fetchall()

            if not rows:
                break

            params = []
            for row in rows:
                sup = extraer_superficie(row.descripcion)
                amb = extraer_ambientes(row.descripcion)
                if sup is not None or amb is not None:
                    params.append({"id": row.id, "sup": sup, "amb": amb})

            if params:
                conn.execute(text("""
                    UPDATE properties
                    SET superficie_m2 = :sup,
                        ambientes     = :amb
                    WHERE id = :id
                """), params)
                conn.commit()
                actualizadas += len(params)

            offset += BATCH
            if offset % 5000 == 0:
                log.info(f"Procesadas {offset}/{total} — {actualizadas} actualizadas")

        log.info(f"Completado: {actualizadas} propiedades actualizadas")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL", "postgresql://easyhome_user:1234@localhost/easyhome"),
    )
    args = parser.parse_args()
    run(args.db)


if __name__ == "__main__":
    main()
