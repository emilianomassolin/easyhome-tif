from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import Favorite, Property, Report, User, UserPreferences
from backend.api.auth_routes import get_current_user

router = APIRouter(prefix="/users/me", tags=["usuarios"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class PreferencesBody(BaseModel):
    criterios: Optional[list[str]] = None
    zona: Optional[str] = None
    operacion: Optional[str] = None
    precio_min: Optional[float] = None
    precio_max: Optional[float] = None


class ReportBody(BaseModel):
    property_id: int
    motivo: str
    descripcion: Optional[str] = None


# ── Preferencias ──────────────────────────────────────────────────────────────

@router.get("/preferences")
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == current_user.id).first()
    if not prefs:
        return {"criterios": [], "zona": None, "operacion": None, "precio_min": None, "precio_max": None}
    return {
        "criterios": prefs.criterios or [],
        "zona": prefs.zona,
        "operacion": prefs.operacion,
        "precio_min": prefs.precio_min,
        "precio_max": prefs.precio_max,
    }


@router.put("/preferences")
def save_preferences(
    body: PreferencesBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == current_user.id).first()
    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)

    prefs.criterios = body.criterios
    prefs.zona = body.zona
    prefs.operacion = body.operacion
    prefs.precio_min = body.precio_min
    prefs.precio_max = body.precio_max
    db.commit()
    return {"mensaje": "Preferencias guardadas"}


# ── Favoritas ─────────────────────────────────────────────────────────────────

def _prop_dict(p: Property) -> dict:
    return {
        "id": p.id,
        "titulo": p.titulo,
        "ubicacion": p.ubicacion,
        "precio": p.precio,
        "fuente": p.fuente,
        "tipo_operacion": p.tipo_operacion,
        "fotos_urls": p.fotos_urls,
        "score_accesibilidad": p.score_accesibilidad,
        "activa": p.activa,
        "permalink_ml": p.permalink_ml,
    }


@router.get("/favorites")
def get_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favs = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id)
        .order_by(desc(Favorite.fecha_guardado))
        .all()
    )
    result = []
    for fav in favs:
        prop = db.query(Property).filter(Property.id == fav.property_id).first()
        if prop:
            result.append({**_prop_dict(prop), "fecha_guardado": fav.fecha_guardado.isoformat()})
    return {"total": len(result), "favoritas": result}


@router.get("/favorites/ids")
def get_favorite_ids(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favs = db.query(Favorite.property_id).filter(Favorite.user_id == current_user.id).all()
    return [f.property_id for f in favs]


@router.post("/favorites/{property_id}")
def add_favorite(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not db.query(Property).filter(Property.id == property_id).first():
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    existing = db.query(Favorite).filter(
        Favorite.user_id == current_user.id, Favorite.property_id == property_id
    ).first()
    if existing:
        return {"mensaje": "Ya está en favoritas"}
    db.add(Favorite(user_id=current_user.id, property_id=property_id))
    db.commit()
    return {"mensaje": "Agregada a favoritas"}


@router.delete("/favorites/{property_id}")
def remove_favorite(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fav = db.query(Favorite).filter(
        Favorite.user_id == current_user.id, Favorite.property_id == property_id
    ).first()
    if fav:
        db.delete(fav)
        db.commit()
    return {"mensaje": "Eliminada de favoritas"}


# ── Reportes ──────────────────────────────────────────────────────────────────

@router.post("/reports")
def create_report(
    body: ReportBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not db.query(Property).filter(Property.id == body.property_id).first():
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    report = Report(
        property_id=body.property_id,
        user_id=current_user.id,
        motivo=body.motivo,
        descripcion=body.descripcion,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "mensaje": "Reporte enviado. Te notificaremos cuando sea revisado."}


@router.get("/reports")
def get_my_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports = (
        db.query(Report)
        .filter(Report.user_id == current_user.id)
        .order_by(desc(Report.fecha_creacion))
        .all()
    )
    result = []
    for r in reports:
        prop = db.query(Property).filter(Property.id == r.property_id).first()
        result.append({
            "id": r.id,
            "property_id": r.property_id,
            "titulo_propiedad": prop.titulo if prop else "—",
            "motivo": r.motivo,
            "descripcion": r.descripcion,
            "estado": r.estado,
            "fecha_creacion": r.fecha_creacion.isoformat() if r.fecha_creacion else None,
            "notas_admin": r.notas_admin,
            "fecha_resolucion": r.fecha_resolucion.isoformat() if r.fecha_resolucion else None,
        })
    return {"total": len(result), "reportes": result}
