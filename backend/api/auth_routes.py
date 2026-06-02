import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import User
from backend.core.security import hash_password, verify_password, create_access_token, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    nombre: Optional[str] = None


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class ForgotBody(BaseModel):
    email: EmailStr


class ResetBody(BaseModel):
    token: str
    new_password: str


def _user_dict(u: User) -> dict:
    return {"id": u.id, "email": u.email, "nombre": u.nombre, "activo": u.activo}


# ── Dependencia de autenticación ──────────────────────────────────────────────

async def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    payload = decode_token(authorization[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    user = db.query(User).filter(User.id == int(payload["sub"]), User.activo == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register")
def register(body: RegisterBody, db: Session = Depends(get_db)):
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")

    user = User(
        email=body.email,
        nombre=body.nombre,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(user)}


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    if not user.activo:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    user.ultima_actividad = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(user.id, user.email)
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(user)}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return _user_dict(current_user)


@router.post("/forgot-password")
def forgot_password(body: ForgotBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    # Siempre responder igual para no revelar si el email existe
    if user and user.password_hash:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
        db.commit()
        # En producción se enviaría por email; para el TIF se devuelve el token
        return {
            "mensaje": "Si el email existe, recibirás un enlace de recuperación.",
            "_debug_reset_token": token,  # solo para desarrollo/TIF
        }
    return {"mensaje": "Si el email existe, recibirás un enlace de recuperación."}


@router.post("/reset-password")
def reset_password(body: ResetBody, db: Session = Depends(get_db)):
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    user = db.query(User).filter(
        User.reset_token == body.token,
        User.reset_token_expiry > datetime.now(timezone.utc),
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")

    user.password_hash = hash_password(body.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()
    return {"mensaje": "Contraseña actualizada correctamente"}
