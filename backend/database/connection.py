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
    from backend.database.models import Property, ScraperLog, Report, User, UserPreferences, Favorite  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _run_migrations()


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
