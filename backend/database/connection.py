import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    pool_size=60,
    max_overflow=20,
    pool_timeout=60,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from backend.database.models import Property, ScraperLog, Report, User, UserPreferences, Favorite, Comentario, SnapshotPropiedades  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _fix_stuck_scrapers()


def _fix_stuck_scrapers():
    """Al arrancar, marca como error los scrapers que quedaron en 'running' por un reinicio."""
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text(
                "UPDATE scraper_logs SET estado='error', fin=NOW(), "
                "mensaje_error='Proceso interrumpido por reinicio del servidor' "
                "WHERE estado='running'"
            ))
            conn.commit()
        except Exception:
            conn.rollback()


def _run_migrations():
    """Agrega columnas nuevas a tablas ya existentes (idempotente)."""
    from sqlalchemy import text
    migrations = [
        ("users", "password_hash",        "VARCHAR"),
        ("users", "reset_token",          "VARCHAR"),
        ("users", "reset_token_expiry",   "TIMESTAMPTZ"),
        ("reports", "user_id",            "INTEGER"),
        ("properties", "manual_override", "JSONB"),
    ]
    with engine.connect() as conn:
        for table, col, col_type in migrations:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"))
                conn.commit()
            except Exception:
                conn.rollback()
