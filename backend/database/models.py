from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone

from backend.database.connection import Base


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    ml_id = Column(String, unique=True, nullable=False, index=True)
    titulo = Column(String, nullable=False)
    precio = Column(Float, nullable=True)
    descripcion = Column(Text, nullable=True)
    ubicacion = Column(String, nullable=True)
    permalink_ml = Column(String, nullable=False)
    fotos_urls = Column(JSONB, nullable=True)
    fuente = Column(String, default="mercadolibre", nullable=False)
    tipo_operacion = Column(String(20), nullable=True)
    activa = Column(Boolean, default=True, nullable=False)
    fecha_creacion = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    fecha_actualizacion = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Sprint 2 — análisis de accesibilidad
    nlp_resultado = Column(JSONB, nullable=True)
    vision_resultado = Column(JSONB, nullable=True)
    score_accesibilidad = Column(Float, nullable=True)
    justificacion_score = Column(Text, nullable=True)
    confianza_general = Column(Float, nullable=True)
    analizado = Column(Boolean, default=False, nullable=False)
    fecha_analisis = Column(DateTime(timezone=True), nullable=True)
