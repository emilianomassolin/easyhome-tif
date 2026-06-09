import base64
import hashlib
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

import requests as _req
from dotenv import set_key
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import Property, Comentario, User
from backend.nlp.analyzer import analizar_texto
from backend.vision.image_analyzer import analizar_imagenes
from backend.scoring.calculator import calcular_score
from backend.nlp.keyword_filter import tiene_keywords_accesibilidad, RESULTADO_VACIO, VISION_VACIA

router = APIRouter()

_REDIRECT_URI = os.getenv("ML_REDIRECT_URI", "http://localhost:8000/auth/callback")
_pkce_store: dict[str, str] = {}   # state → code_verifier (in-memory, single process)


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ── Schemas ───────────────────────────────────────────────────────────────────

NIVELES = [
    (8.5, "Muy accesible"),
    (6.0, "Accesible"),
    (3.5, "Parcialmente accesible"),
    (0.0, "Poco accesible"),
]


def _nivel(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    return next(nombre for umbral, nombre in NIVELES if score >= umbral)


class PropertyListItem(BaseModel):
    id: int
    titulo: str
    precio: Optional[float]
    ubicacion: Optional[str]
    permalink_ml: str
    fuente: str
    tipo_operacion: Optional[str] = None
    fotos_urls: Optional[list[str]]
    score_accesibilidad: Optional[float]
    nivel_accesibilidad: Optional[str] = None
    fecha_creacion: datetime

    @classmethod
    def from_orm_with_nivel(cls, obj):
        data = cls.model_validate(obj)
        data.nivel_accesibilidad = _nivel(obj.score_accesibilidad)
        return data

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
    fuente: str
    score_accesibilidad: Optional[float]
    nivel_accesibilidad: Optional[str] = None
    justificacion_score: Optional[str]
    criterios_detectados: Optional[dict] = None
    analizado: bool
    fecha_creacion: datetime

    @classmethod
    def from_orm_with_nivel(cls, obj):
        data = cls.model_validate(obj)
        data.nivel_accesibilidad = _nivel(obj.score_accesibilidad)
        criterios = (obj.nlp_resultado or {})
        vision    = (obj.vision_resultado or {})
        if obj.analizado and (criterios or vision):
            from backend.scoring.calculator import CRITERIOS
            todos = {c for c in CRITERIOS if criterios.get(c) or vision.get(c)}
            data.criterios_detectados = {c: c in todos for c in CRITERIOS}
        return data

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


@router.get("/auth/start", response_class=RedirectResponse)
def ml_auth_start():
    state = secrets.token_urlsafe(16)
    _pkce_store[state] = ""  # placeholder, PKCE not enabled

    app_id = os.getenv("ML_APP_ID", "").strip()
    url = (
        f"https://auth.mercadolibre.com.ar/authorization"
        f"?response_type=code"
        f"&client_id={app_id}"
        f"&redirect_uri={_REDIRECT_URI}"
        f"&state={state}"
        f"&scope=read+write+offline_access"
    )
    return RedirectResponse(url)


@router.get("/auth/callback", response_class=HTMLResponse)
def ml_auth_callback(request: Request, code: str = None, error: str = None, state: str = None):
    if error or not code:
        return HTMLResponse(f"<h2>Error: {error or 'sin código'}</h2>", status_code=400)

    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    verifier = _pkce_store.pop(state, None) if state else None

    payload = {
        "grant_type":    "authorization_code",
        "client_id":     os.getenv("ML_APP_ID", "").strip(),
        "client_secret": os.getenv("ML_CLIENT_SECRET", "").strip(),
        "code":          code,
        "redirect_uri":  _REDIRECT_URI,
    }
    if verifier:
        payload["code_verifier"] = verifier

    resp = _req.post("https://api.mercadolibre.com/oauth/token", data=payload, timeout=10)

    if resp.status_code != 200:
        return HTMLResponse(f"<h2>Error al obtener token: {resp.text}</h2>", status_code=400)

    data = resp.json()
    set_key(env_path, "ML_ACCESS_TOKEN", data["access_token"])
    os.environ["ML_ACCESS_TOKEN"] = data["access_token"]
    if "refresh_token" in data:
        set_key(env_path, "ML_REFRESH_TOKEN", data["refresh_token"])
        os.environ["ML_REFRESH_TOKEN"] = data["refresh_token"]

    return HTMLResponse("<h2>✅ MercadoLibre autorizado correctamente. Podés cerrar esta ventana.</h2>")


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Property).filter(Property.activa == True).count()
    con_accesibilidad = db.query(Property).filter(
        Property.activa == True,
        Property.analizado == True,
        Property.score_accesibilidad > 0,
    ).count()
    return {"total": total, "con_accesibilidad": con_accesibilidad}


@router.get("/properties", response_model=PropertiesResponse)
def list_properties(
    skip: int = 0,
    limit: int = 20,
    fuente: Optional[str] = None,
    min_score: Optional[float] = None,
    tipo_operacion: Optional[str] = None,
    solo_analizados: Optional[bool] = None,
    zona: Optional[str] = None,
    tipo_propiedad: Optional[str] = None,
    criterios: Optional[str] = None,
    orden: Optional[str] = 'desc',
    db: Session = Depends(get_db),
):
    from sqlalchemy import nullslast, nullsfirst, desc, asc, or_
    query = db.query(Property).filter(Property.activa == True)
    if fuente:
        query = query.filter(Property.fuente == fuente)
    if min_score is not None:
        query = query.filter(Property.score_accesibilidad >= min_score)
    if tipo_operacion:
        query = query.filter(Property.tipo_operacion == tipo_operacion)
    if solo_analizados:
        query = query.filter(Property.analizado == True)
    if zona:
        query = query.filter(Property.ubicacion.ilike(f"%{zona}%"))
    if tipo_propiedad:
        query = query.filter(Property.titulo.ilike(f"%{tipo_propiedad}%"))
    if criterios:
        lista = [c.strip() for c in criterios.split(",") if c.strip()]
        for criterio in lista:
            query = query.filter(
                or_(
                    Property.nlp_resultado[criterio].as_boolean() == True,
                    Property.vision_resultado[criterio].as_boolean() == True,
                )
            )
    total = query.count()
    score_order = (
        nullsfirst(asc(Property.score_accesibilidad))
        if orden == 'asc'
        else nullslast(desc(Property.score_accesibilidad))
    )
    propiedades = query.order_by(score_order).offset(skip).limit(limit).all()
    return {"total": total, "propiedades": [PropertyListItem.from_orm_with_nivel(p) for p in propiedades]}


@router.get("/properties/{property_id}", response_model=PropertyDetail)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id, Property.activa == True).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    return PropertyDetail.from_orm_with_nivel(prop)


# ── Endpoints Sprint 2 ────────────────────────────────────────────────────────

@router.post("/analyze/{property_id}", response_model=AnalysisResponse)
def analyze_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id, Property.activa == True).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    if tiene_keywords_accesibilidad(prop.titulo, prop.descripcion):
        nlp = analizar_texto(prop.descripcion)
        nlp_positivo = any(v for k, v in nlp.items() if k != "confianza" and v is True)
        vision = analizar_imagenes(prop.fotos_urls) if nlp_positivo else VISION_VACIA
    else:
        nlp = RESULTADO_VACIO
        vision = VISION_VACIA
    resultado = calcular_score(nlp, vision, prop.titulo)

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


# ── Comentarios ───────────────────────────────────────────────────────────────

class ComentarioIn(BaseModel):
    texto: str


@router.get("/properties/{property_id}/comments")
def get_comments(property_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id, Property.activa == True).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    comments = (
        db.query(Comentario, User)
        .join(User, Comentario.user_id == User.id)
        .filter(Comentario.property_id == property_id, Comentario.activo == True)
        .order_by(Comentario.fecha_creacion.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "texto": c.texto,
            "fecha_creacion": c.fecha_creacion,
            "user_nombre": u.nombre or u.email.split("@")[0],
            "user_id": c.user_id,
        }
        for c, u in comments
    ]


@router.post("/properties/{property_id}/comments")
def add_comment(
    property_id: int,
    body: ComentarioIn,
    db: Session = Depends(get_db),
    request: Request = None,
):
    from backend.core.security import decode_token
    auth = request.headers.get("Authorization", "") if request else ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Se requiere iniciar sesión para comentar")
    payload = decode_token(auth[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    user = db.query(User).filter(User.id == int(payload["sub"]), User.activo == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    prop = db.query(Property).filter(Property.id == property_id, Property.activa == True).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    texto = body.texto.strip()
    if not texto:
        raise HTTPException(status_code=400, detail="El comentario no puede estar vacío")
    if len(texto) > 500:
        raise HTTPException(status_code=400, detail="El comentario no puede superar 500 caracteres")

    comentario = Comentario(property_id=property_id, user_id=user.id, texto=texto)
    db.add(comentario)
    db.commit()
    db.refresh(comentario)
    return {
        "id": comentario.id,
        "texto": comentario.texto,
        "fecha_creacion": comentario.fecha_creacion,
        "user_nombre": user.nombre or user.email.split("@")[0],
        "user_id": user.id,
    }


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db), request: Request = None):
    from backend.core.security import decode_token
    auth = request.headers.get("Authorization", "") if request else ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    payload = decode_token(auth[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")
    user_id = int(payload["sub"])

    comment = db.query(Comentario).filter(Comentario.id == comment_id, Comentario.activo == True).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
    if comment.user_id != user_id:
        raise HTTPException(status_code=403, detail="No podés eliminar comentarios de otros usuarios")
    comment.activo = False
    db.commit()
    return {"ok": True}


@router.post("/scrape/argenprop")
def scrape_argenprop_endpoint(db: Session = Depends(get_db)):
    from backend.scrapers.argenprop_scraper import scrape_argenprop
    saved = scrape_argenprop()
    return {"mensaje": f"Argenprop: {saved} propiedades nuevas/actualizadas.", "guardadas": saved}


@router.post("/analyze-all")
def analyze_all(fuente: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Property).filter(Property.activa == True, Property.analizado == False)
    if fuente:
        query = query.filter(Property.fuente == fuente)
    pendientes = query.all()

    if not pendientes:
        return {"mensaje": "No hay propiedades pendientes de análisis.", "analizadas": 0}

    analizadas = 0
    filtradas = 0
    enviadas_vision = 0
    for i, prop in enumerate(pendientes):
        try:
            if tiene_keywords_accesibilidad(prop.titulo, prop.descripcion):
                nlp = analizar_texto(prop.descripcion)
                nlp_positivo = any(v for k, v in nlp.items() if k != "confianza" and v is True)
                if nlp_positivo:
                    vision = analizar_imagenes(prop.fotos_urls)
                    enviadas_vision += 1
                else:
                    vision = VISION_VACIA
            else:
                nlp = RESULTADO_VACIO
                vision = VISION_VACIA
                filtradas += 1

            resultado = calcular_score(nlp, vision, prop.titulo)
            prop.nlp_resultado = nlp
            prop.vision_resultado = vision
            prop.score_accesibilidad = resultado["score_accesibilidad"]
            prop.justificacion_score = resultado["justificacion"]
            prop.confianza_general = resultado["confianza"]
            prop.analizado = True
            prop.fecha_analisis = datetime.now(timezone.utc)
            analizadas += 1
        except Exception:
            continue

        if (i + 1) % 100 == 0:
            db.commit()

    db.commit()
    enviadas_nlp = analizadas - filtradas
    return {
        "mensaje": f"{analizadas} propiedades procesadas: {filtradas} descartadas por keywords, {enviadas_nlp} enviadas a NLP, {enviadas_vision} enviadas a visión.",
        "analizadas": analizadas,
        "filtradas_sin_keywords": filtradas,
        "enviadas_nlp": enviadas_nlp,
        "enviadas_vision": enviadas_vision,
    }
