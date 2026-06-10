from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, ForeignKey, UniqueConstraint
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
    manual_override = Column(JSONB, nullable=True)
    duplicate_of = Column(Integer, ForeignKey("properties.id", ondelete="SET NULL"), nullable=True, index=True)
    superficie_m2 = Column(Float, nullable=True)
    ambientes = Column(Integer, nullable=True)


class ScraperLog(Base):
    __tablename__ = "scraper_logs"

    id = Column(Integer, primary_key=True, index=True)
    fuente = Column(String(50), nullable=False, index=True)
    inicio = Column(DateTime(timezone=True), nullable=False)
    fin = Column(DateTime(timezone=True), nullable=True)
    estado = Column(String(20), default="running", nullable=False)  # running | ok | error
    cantidad = Column(Integer, default=0, nullable=False)
    mensaje_error = Column(Text, nullable=True)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    motivo = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)
    estado = Column(String(20), default="pendiente", nullable=False)  # pendiente | resuelto | ignorado
    fecha_creacion = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    notas_admin = Column(Text, nullable=True)
    fecha_resolucion = Column(DateTime(timezone=True), nullable=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    nombre = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    fecha_registro = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ultima_actividad = Column(DateTime(timezone=True), nullable=True)
    reset_token = Column(String, nullable=True, index=True)
    reset_token_expiry = Column(DateTime(timezone=True), nullable=True)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    criterios = Column(JSONB, nullable=True)        # lista de criterios preferidos
    zona = Column(String, nullable=True)
    operacion = Column(String(20), nullable=True)   # alquiler | venta
    precio_min = Column(Float, nullable=True)
    precio_max = Column(Float, nullable=True)


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    fecha_guardado = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Comentario(Base):
    __tablename__ = "comentarios"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    texto = Column(Text, nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    fecha_creacion = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class VotoCriterio(Base):
    __tablename__ = "votos_criterios"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    criterio = Column(String(50), nullable=False)
    valor = Column(Boolean, nullable=False)  # True = "sí tiene" / False = "no tiene"
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (UniqueConstraint('property_id', 'user_id', 'criterio', name='uq_voto_criterio'),)


class SnapshotPropiedades(Base):
    __tablename__ = "snapshots_propiedades"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    fuente = Column(String(50), nullable=False)
    tipo_operacion = Column(String(20), nullable=True)
    cantidad = Column(Integer, default=0, nullable=False)
