from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import Property
from backend.nlp.analyzer import analizar_texto
from backend.vision.image_analyzer import analizar_imagenes
from backend.scoring.calculator import calcular_score

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class PropertyListItem(BaseModel):
    id: int
    titulo: str
    precio: Optional[float]
    ubicacion: Optional[str]
    permalink_ml: str
    score_accesibilidad: Optional[float]
    fecha_creacion: datetime

    class Config:
        from_attributes = True


class PropertyDetail(BaseModel):
    id: int
    titulo: str
    precio: Optional[float]
    descripcion: Optional[str]
    ubicacion: Optional[str]
    fotos_urls: Optional[list[str]]
    permalink_ml: str
    score_accesibilidad: Optional[float]
    justificacion_score: Optional[str]
    analizado: bool
    fecha_creacion: datetime

    class Config:
        from_attributes = True


class PropertiesResponse(BaseModel):
    total: int
    propiedades: list[PropertyListItem]


class AnalysisResponse(BaseModel):
    id: int
    titulo: str
    score_accesibilidad: float
    nivel: str
    criterios_detectados: dict
    justificacion: str
    confianza: float


# ── Endpoints Sprint 1 ────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/properties", response_model=PropertiesResponse)
def list_properties(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    query = db.query(Property).filter(Property.activa == True)
    total = query.count()
    propiedades = query.offset(skip).limit(limit).all()
    return {"total": total, "propiedades": propiedades}


@router.get("/properties/{property_id}", response_model=PropertyDetail)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id, Property.activa == True).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    return prop


# ── Endpoints Sprint 2 ────────────────────────────────────────────────────────

@router.post("/analyze/{property_id}", response_model=AnalysisResponse)
def analyze_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id, Property.activa == True).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    nlp = analizar_texto(prop.descripcion)
    vision = analizar_imagenes(prop.fotos_urls)
    resultado = calcular_score(nlp, vision)

    prop.nlp_resultado = nlp
    prop.vision_resultado = vision
    prop.score_accesibilidad = resultado["score_accesibilidad"]
    prop.justificacion_score = resultado["justificacion"]
    prop.confianza_general = resultado["confianza"]
    prop.analizado = True
    prop.fecha_analisis = datetime.now(timezone.utc)
    db.commit()

    return {
        "id": prop.id,
        "titulo": prop.titulo,
        **resultado,
    }


@router.post("/analyze-all")
def analyze_all(db: Session = Depends(get_db)):
    pendientes = db.query(Property).filter(
        Property.activa == True,
        Property.analizado == False,
    ).all()

    if not pendientes:
        return {"mensaje": "No hay propiedades pendientes de análisis.", "analizadas": 0}

    analizadas = 0
    for prop in pendientes:
        try:
            nlp = analizar_texto(prop.descripcion)
            vision = analizar_imagenes(prop.fotos_urls)
            resultado = calcular_score(nlp, vision)

            prop.nlp_resultado = nlp
            prop.vision_resultado = vision
            prop.score_accesibilidad = resultado["score_accesibilidad"]
            prop.justificacion_score = resultado["justificacion"]
            prop.confianza_general = resultado["confianza"]
            prop.analizado = True
            prop.fecha_analisis = datetime.now(timezone.utc)
            analizadas += 1
        except Exception as e:
            continue

    db.commit()
    return {"mensaje": f"{analizadas} propiedades analizadas correctamente.", "analizadas": analizadas}
