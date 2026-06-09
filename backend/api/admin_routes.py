import asyncio
import csv
import io
import logging
import os
import queue
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, desc, case
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import Property, ScraperLog, Report, User, Comentario, SnapshotPropiedades

router = APIRouter(prefix="/admin", tags=["admin"])

logger = logging.getLogger(__name__)

# ── Auth ──────────────────────────────────────────────────────────────────────

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin-changeme")
ADMIN_EMAIL = "emilianomassolin@gmail.com"


def _check_token(token: str):
    if not token or token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token de administrador inválido")


def _check_admin_jwt(authorization: str, db: Session):
    from backend.core.security import decode_token
    if not authorization or not authorization.startswith("Bearer "):
        return False
    payload = decode_token(authorization[7:])
    if not payload:
        return False
    user = db.query(User).filter(User.id == int(payload["sub"]), User.activo == True).first()
    return user is not None and user.email == ADMIN_EMAIL


async def require_admin(
    x_admin_token: str = Header(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    if x_admin_token and x_admin_token == ADMIN_TOKEN:
        return
    if _check_admin_jwt(authorization, db):
        return
    raise HTTPException(status_code=401, detail="No autorizado")


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", dependencies=[Depends(require_admin)])
def get_dashboard(db: Session = Depends(get_db)):
    from backend.scoring.calculator import NIVELES

    # Stats por fuente
    rows = db.query(
        Property.fuente,
        func.count(Property.id).label("total"),
        func.sum(case((Property.analizado == True, 1), else_=0)).label("analizadas"),
        func.avg(Property.score_accesibilidad).label("score_promedio"),
    ).filter(Property.activa == True).group_by(Property.fuente).all()

    stats_por_fuente = [
        {
            "fuente": r.fuente,
            "total": r.total,
            "analizadas": int(r.analizadas or 0),
            "pendientes": r.total - int(r.analizadas or 0),
            "score_promedio": round(float(r.score_promedio), 2) if r.score_promedio else None,
        }
        for r in rows
    ]

    # Distribución de niveles
    scores = db.query(Property.score_accesibilidad).filter(
        Property.activa == True,
        Property.analizado == True,
        Property.score_accesibilidad != None,
    ).all()

    nivel_counts = {nombre: 0 for _, nombre in NIVELES}
    for (score,) in scores:
        if score is not None:
            nivel = next(nombre for umbral, nombre in NIVELES if score >= umbral)
            nivel_counts[nivel] += 1

    distribucion_niveles = [{"nivel": k, "cantidad": v} for k, v in nivel_counts.items()]

    # Totales globales
    total_activas = db.query(Property).filter(Property.activa == True).count()
    total_analizadas = db.query(Property).filter(
        Property.activa == True, Property.analizado == True
    ).count()

    # Última ejecución por scraper
    ultimas_ejecuciones = []
    for fuente in ["mercadolibre", "mendozaprop", "zonaprop", "argenprop"]:
        log = (
            db.query(ScraperLog)
            .filter(ScraperLog.fuente == fuente)
            .order_by(desc(ScraperLog.inicio))
            .first()
        )
        if log:
            ultimas_ejecuciones.append({
                "fuente": fuente,
                "inicio": log.inicio.isoformat() if log.inicio else None,
                "fin": log.fin.isoformat() if log.fin else None,
                "estado": log.estado,
                "cantidad": log.cantidad,
                "mensaje_error": log.mensaje_error,
            })
        else:
            ultimas_ejecuciones.append({"fuente": fuente, "estado": "sin_datos", "cantidad": 0})

    reportes_pendientes = db.query(Report).filter(Report.estado == "pendiente").count()

    return {
        "total_activas": total_activas,
        "total_analizadas": total_analizadas,
        "pendientes_analisis": total_activas - total_analizadas,
        "reportes_pendientes": reportes_pendientes,
        "stats_por_fuente": stats_por_fuente,
        "distribucion_niveles": distribucion_niveles,
        "ultimas_ejecuciones": ultimas_ejecuciones,
    }


# ── Propiedades ───────────────────────────────────────────────────────────────

@router.get("/properties/export", dependencies=[Depends(require_admin)])
def export_properties_csv(
    fuente: Optional[str] = None,
    analizado: Optional[bool] = None,
    activa: Optional[bool] = True,
    db: Session = Depends(get_db),
):
    query = db.query(Property)
    if activa is not None:
        query = query.filter(Property.activa == activa)
    if fuente:
        query = query.filter(Property.fuente == fuente)
    if analizado is not None:
        query = query.filter(Property.analizado == analizado)

    props = query.order_by(desc(Property.fecha_creacion)).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "titulo", "fuente", "tipo_operacion", "ubicacion",
        "precio", "score_accesibilidad", "analizado", "activa",
        "fecha_creacion", "permalink",
    ])
    for p in props:
        writer.writerow([
            p.id, p.titulo, p.fuente, p.tipo_operacion, p.ubicacion,
            p.precio, p.score_accesibilidad, p.analizado, p.activa,
            p.fecha_creacion.isoformat() if p.fecha_creacion else "",
            p.permalink_ml,
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=propiedades.csv"},
    )


@router.get("/properties", dependencies=[Depends(require_admin)])
def admin_list_properties(
    skip: int = 0,
    limit: int = 50,
    fuente: Optional[str] = None,
    analizado: Optional[bool] = None,
    activa: Optional[bool] = None,
    search: Optional[str] = None,
    orden: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Property)
    if activa is not None:
        query = query.filter(Property.activa == activa)
    if fuente:
        query = query.filter(Property.fuente == fuente)
    if analizado is not None:
        query = query.filter(Property.analizado == analizado)
    if search:
        query = query.filter(Property.titulo.ilike(f"%{search}%"))

    total = query.count()

    if orden == "score_desc":
        order = Property.score_accesibilidad.desc().nullslast()
    elif orden == "score_asc":
        order = Property.score_accesibilidad.asc().nullsfirst()
    else:
        order = desc(Property.fecha_creacion)

    props = query.order_by(order).offset(skip).limit(limit).all()

    return {
        "total": total,
        "propiedades": [
            {
                "id": p.id,
                "titulo": p.titulo,
                "fuente": p.fuente,
                "tipo_operacion": p.tipo_operacion,
                "ubicacion": p.ubicacion,
                "precio": p.precio,
                "score_accesibilidad": p.score_accesibilidad,
                "analizado": p.analizado,
                "activa": p.activa,
                "fecha_creacion": p.fecha_creacion.isoformat() if p.fecha_creacion else None,
                "fecha_analisis": p.fecha_analisis.isoformat() if p.fecha_analisis else None,
                "permalink_ml": p.permalink_ml,
                "nlp_resultado": p.nlp_resultado,
                "vision_resultado": p.vision_resultado,
                "manual_override": p.manual_override or {},
            }
            for p in props
        ],
    }


@router.post("/properties/{property_id}/reanalyze", dependencies=[Depends(require_admin)])
def admin_reanalyze(property_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    from backend.nlp.analyzer import analizar_texto
    from backend.vision.image_analyzer import analizar_imagenes
    from backend.scoring.calculator import calcular_score
    from backend.nlp.keyword_filter import tiene_keywords_accesibilidad, RESULTADO_VACIO, VISION_VACIA

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
        "score_accesibilidad": prop.score_accesibilidad,
        "mensaje": "Re-análisis completado",
    }


@router.patch("/properties/{property_id}/status", dependencies=[Depends(require_admin)])
def admin_update_property_status(
    property_id: int,
    activa: bool,
    db: Session = Depends(get_db),
):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    prop.activa = activa
    db.commit()
    return {"id": prop.id, "activa": prop.activa}


class AccessibilityOverrideBody(BaseModel):
    override: dict  # { "rampa": true, "entrada_ancha": true, "ascensor": false, ... }


@router.patch("/properties/{property_id}/accessibility", dependencies=[Depends(require_admin)])
def admin_update_accessibility(
    property_id: int,
    body: AccessibilityOverrideBody,
    db: Session = Depends(get_db),
):
    from backend.scoring.calculator import calcular_score, CRITERIOS

    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    valid_criterios = set(CRITERIOS)
    override = {k: v for k, v in body.override.items() if k in valid_criterios and isinstance(v, bool)}

    prop.manual_override = override
    nlp = prop.nlp_resultado or {}
    vision = prop.vision_resultado or {}
    resultado = calcular_score(nlp, vision, prop.titulo, manual_override=override)

    prop.score_accesibilidad = resultado["score_accesibilidad"]
    prop.justificacion_score = resultado["justificacion"]
    prop.analizado = True
    db.commit()

    return {
        "id": prop.id,
        "score_accesibilidad": prop.score_accesibilidad,
        "manual_override": prop.manual_override,
        "criterios_detectados": resultado["criterios_detectados"],
    }


# ── Reportes ──────────────────────────────────────────────────────────────────

@router.get("/reports", dependencies=[Depends(require_admin)])
def admin_list_reports(
    estado: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(Report)
    if estado:
        query = query.filter(Report.estado == estado)
    total = query.count()
    reports = query.order_by(desc(Report.fecha_creacion)).offset(skip).limit(limit).all()

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

    return {"total": total, "reportes": result}


@router.post("/reports", dependencies=[Depends(require_admin)])
def create_report(
    property_id: int,
    motivo: str,
    descripcion: Optional[str] = None,
    db: Session = Depends(get_db),
):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    report = Report(property_id=property_id, motivo=motivo, descripcion=descripcion)
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "mensaje": "Reporte creado"}


@router.patch("/reports/{report_id}", dependencies=[Depends(require_admin)])
def resolve_report(
    report_id: int,
    accion: str,
    notas: Optional[str] = None,
    db: Session = Depends(get_db),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    if accion == "ignorar":
        report.estado = "ignorado"
    elif accion == "resolver":
        report.estado = "resuelto"
    elif accion == "dar_baja":
        report.estado = "resuelto"
        prop = db.query(Property).filter(Property.id == report.property_id).first()
        if prop:
            prop.activa = False

    report.notas_admin = notas
    report.fecha_resolucion = datetime.now(timezone.utc)
    db.commit()
    return {"id": report.id, "estado": report.estado}


# ── Scrapers ──────────────────────────────────────────────────────────────────

_run_queues: dict[str, queue.Queue] = {}


class _QueueHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q
        self.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    def emit(self, record):
        try:
            self.q.put_nowait(self.format(record))
        except queue.Full:
            pass


def _get_scraper_func(fuente: str):
    if fuente == "mercadolibre":
        from backend.scrapers.mercadolibre_scraper import scrape_mercadolibre
        return scrape_mercadolibre
    if fuente == "mendozaprop":
        from backend.scrapers.mendozaprop_scraper import scrape_mendozaprop
        return scrape_mendozaprop
    if fuente == "zonaprop":
        from backend.scrapers.zonaprop_scraper import scrape_zonaprop
        return scrape_zonaprop
    if fuente == "argenprop":
        from backend.scrapers.argenprop_scraper import scrape_argenprop
        return scrape_argenprop
    raise HTTPException(status_code=400, detail=f"Fuente desconocida: {fuente}")


def _record_snapshot(db, fuente: str):
    """Guarda un snapshot de cuántas propiedades activas hay por fuente y tipo_operacion."""
    from sqlalchemy import func as _func
    rows = (
        db.query(Property.tipo_operacion, _func.count(Property.id))
        .filter(Property.activa == True, Property.fuente == fuente)
        .group_by(Property.tipo_operacion)
        .all()
    )
    now = datetime.now(timezone.utc)
    for tipo_operacion, cantidad in rows:
        snap = SnapshotPropiedades(
            fecha=now,
            fuente=fuente,
            tipo_operacion=tipo_operacion,
            cantidad=cantidad,
        )
        db.add(snap)
    db.commit()


@router.post("/scrapers/{fuente}/run", dependencies=[Depends(require_admin)])
def run_scraper(fuente: str, db: Session = Depends(get_db)):
    scraper_func = _get_scraper_func(fuente)
    run_id = uuid.uuid4().hex[:8]
    q: queue.Queue = queue.Queue(maxsize=1000)
    _run_queues[run_id] = q

    log_entry = ScraperLog(
        fuente=fuente,
        inicio=datetime.now(timezone.utc),
        estado="running",
        cantidad=0,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    log_id = log_entry.id

    def _run():
        from backend.database.connection import SessionLocal
        _db = SessionLocal()
        handler = _QueueHandler(q)
        scraper_loggers = [
            logging.getLogger("backend.scrapers"),
            logging.getLogger(f"backend.scrapers.{fuente}_scraper"),
        ]
        for lg in scraper_loggers:
            lg.addHandler(handler)
        try:
            q.put(f"[INFO] Iniciando scraper: {fuente}")
            count = scraper_func()
            _log = _db.query(ScraperLog).filter(ScraperLog.id == log_id).first()
            if _log:
                _log.fin = datetime.now(timezone.utc)
                _log.estado = "ok"
                _log.cantidad = count or 0
                _db.commit()
            _record_snapshot(_db, fuente)
            q.put(f"__DONE__{count or 0}")
        except Exception as e:
            _log = _db.query(ScraperLog).filter(ScraperLog.id == log_id).first()
            if _log:
                _log.fin = datetime.now(timezone.utc)
                _log.estado = "error"
                _log.mensaje_error = str(e)
                _db.commit()
            q.put(f"__ERROR__{e}")
        finally:
            for lg in scraper_loggers:
                lg.removeHandler(handler)
            _db.close()

    threading.Thread(target=_run, daemon=True).start()
    return {"run_id": run_id, "log_id": log_id, "fuente": fuente}


@router.get("/scrapers/{run_id}/stream")
async def stream_scraper_log(run_id: str, token: str = Query(None), db: Session = Depends(get_db)):
    if token and token == ADMIN_TOKEN:
        pass
    elif _check_admin_jwt(f"Bearer {token}" if token else None, db):
        pass
    else:
        raise HTTPException(status_code=401, detail="No autorizado")

    async def generate():
        q = _run_queues.get(run_id)
        if not q:
            yield "data: ERROR: run_id no encontrado\n\n"
            return
        loop = asyncio.get_event_loop()
        while True:
            try:
                msg = await loop.run_in_executor(None, lambda: q.get(timeout=180))
                if msg.startswith("__DONE__"):
                    yield f"data: ✅ Completado: {msg[8:]} propiedades nuevas\n\n"
                    yield "data: __END__\n\n"
                    _run_queues.pop(run_id, None)
                    break
                elif msg.startswith("__ERROR__"):
                    yield f"data: ❌ Error: {msg[9:]}\n\n"
                    yield "data: __END__\n\n"
                    _run_queues.pop(run_id, None)
                    break
                else:
                    yield f"data: {msg}\n\n"
            except Exception:
                yield "data: [timeout esperando respuesta del scraper]\n\n"
                yield "data: __END__\n\n"
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.delete("/scrapers/logs", dependencies=[Depends(require_admin)])
def clear_scraper_logs(db: Session = Depends(get_db)):
    deleted = db.query(ScraperLog).filter(ScraperLog.estado != "running").delete()
    db.commit()
    return {"deleted": deleted}


@router.get("/scrapers/logs", dependencies=[Depends(require_admin)])
def get_scraper_logs(
    fuente: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(ScraperLog)
    if fuente:
        query = query.filter(ScraperLog.fuente == fuente)
    logs = query.order_by(desc(ScraperLog.inicio)).limit(limit).all()

    return [
        {
            "id": l.id,
            "fuente": l.fuente,
            "inicio": l.inicio.isoformat() if l.inicio else None,
            "fin": l.fin.isoformat() if l.fin else None,
            "estado": l.estado,
            "cantidad": l.cantidad,
            "mensaje_error": l.mensaje_error,
        }
        for l in logs
    ]


# ── Análisis ──────────────────────────────────────────────────────────────────

@router.post("/analysis/start", dependencies=[Depends(require_admin)])
def start_analysis(workers: int = 10):
    run_id = uuid.uuid4().hex[:8]
    q: queue.Queue = queue.Queue(maxsize=5000)
    _run_queues[run_id] = q

    def _run():
        from backend.scripts.analyze_all_fast import main
        try:
            count = main(workers=workers, progress_queue=q)
            q.put(f"__DONE__{count}")
        except Exception as e:
            q.put(f"__ERROR__{e}")

    threading.Thread(target=_run, daemon=True).start()
    return {"run_id": run_id}


@router.get("/analysis/{run_id}/stream")
async def stream_analysis(run_id: str, token: str = Query(None), db: Session = Depends(get_db)):
    if token and token == ADMIN_TOKEN:
        pass
    elif _check_admin_jwt(f"Bearer {token}" if token else None, db):
        pass
    else:
        raise HTTPException(status_code=401, detail="No autorizado")

    async def generate():
        q = _run_queues.get(run_id)
        if not q:
            yield "data: ERROR: run_id no encontrado\n\n"
            return
        loop = asyncio.get_event_loop()
        while True:
            try:
                msg = await loop.run_in_executor(None, lambda: q.get(timeout=300))
                if msg.startswith("__DONE__"):
                    yield f"data: ✅ Completado: {msg[8:]} propiedades analizadas\n\n"
                    yield "data: __END__\n\n"
                    _run_queues.pop(run_id, None)
                    break
                elif msg.startswith("__ERROR__"):
                    yield f"data: ❌ Error: {msg[9:]}\n\n"
                    yield "data: __END__\n\n"
                    _run_queues.pop(run_id, None)
                    break
                else:
                    yield f"data: {msg}\n\n"
            except Exception:
                yield "data: [esperando progreso...]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/analysis/status", dependencies=[Depends(require_admin)])
def analysis_status(db: Session = Depends(get_db)):
    from sqlalchemy import func, case, text
    r = db.query(
        func.count(Property.id).label("total"),
        func.sum(case((Property.analizado == True, 1), else_=0)).label("analizadas"),
    ).filter(Property.activa == True).one()

    vision = db.execute(text(
        "SELECT COUNT(*) FROM properties WHERE activa=true AND analizado=true "
        "AND (vision_resultado->>'imagenes_analizadas')::int > 0"
    )).scalar() or 0

    return {
        "total": int(r.total or 0),
        "analizadas": int(r.analizadas or 0),
        "pendientes": int(r.total or 0) - int(r.analizadas or 0),
        "vision": int(vision),
        "en_curso": bool(_run_queues),
    }


# ── Usuarios ──────────────────────────────────────────────────────────────────

@router.get("/users", dependencies=[Depends(require_admin)])
def admin_list_users(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    total = db.query(User).count()
    users = db.query(User).order_by(desc(User.fecha_registro)).offset(skip).limit(limit).all()

    return {
        "total": total,
        "usuarios": [
            {
                "id": u.id,
                "email": u.email,
                "nombre": u.nombre,
                "activo": u.activo,
                "fecha_registro": u.fecha_registro.isoformat() if u.fecha_registro else None,
                "ultima_actividad": u.ultima_actividad.isoformat() if u.ultima_actividad else None,
                "reportes": db.query(Report).filter(Report.property_id.in_(
                    db.query(Property.id)
                )).count(),
            }
            for u in users
        ],
    }


@router.patch("/users/{user_id}/status", dependencies=[Depends(require_admin)])
def update_user_status(user_id: int, activo: bool, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.activo = activo
    db.commit()
    return {"id": user.id, "activo": user.activo}


# ── Timeline ──────────────────────────────────────────────────────────────────

@router.get("/timeline", dependencies=[Depends(require_admin)])
def get_timeline(
    fuente: Optional[str] = None,
    granularidad: str = "dia",
    db: Session = Depends(get_db),
):
    from sqlalchemy import text as _text, func as _func

    trunc_map = {"dia": "day", "mes": "month", "anio": "year"}
    trunc = trunc_map.get(granularidad, "day")

    filters = "WHERE 1=1"
    params: dict = {}
    if fuente:
        filters += " AND fuente = :fuente"
        params["fuente"] = fuente

    sql = _text(f"""
        SELECT DATE_TRUNC('{trunc}', fecha) AS periodo,
               fuente,
               tipo_operacion,
               ROUND(AVG(cantidad)) AS cantidad
        FROM snapshots_propiedades
        {filters}
        GROUP BY periodo, fuente, tipo_operacion
        ORDER BY periodo ASC
    """)

    rows = db.execute(sql, params).fetchall()
    return [
        {
            "fecha": r.periodo.isoformat(),
            "fuente": r.fuente,
            "tipo_operacion": r.tipo_operacion,
            "cantidad": int(r.cantidad),
        }
        for r in rows
    ]


# ── Comentarios (moderación) ──────────────────────────────────────────────────

@router.get("/comments", dependencies=[Depends(require_admin)])
def admin_list_comments(
    property_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(Comentario, User).join(User, Comentario.user_id == User.id)
    if property_id:
        query = query.filter(Comentario.property_id == property_id)
    total = query.count()
    items = query.order_by(desc(Comentario.fecha_creacion)).offset(skip).limit(limit).all()
    return {
        "total": total,
        "comentarios": [
            {
                "id": c.id,
                "property_id": c.property_id,
                "texto": c.texto,
                "activo": c.activo,
                "fecha_creacion": c.fecha_creacion.isoformat() if c.fecha_creacion else None,
                "user_email": u.email,
                "user_nombre": u.nombre or u.email.split("@")[0],
            }
            for c, u in items
        ],
    }


@router.delete("/comments/{comment_id}", dependencies=[Depends(require_admin)])
def admin_delete_comment(comment_id: int, db: Session = Depends(get_db)):
    comment = db.query(Comentario).filter(Comentario.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
    comment.activo = False
    db.commit()
    return {"ok": True}
