"""
Gestión del access token de MercadoLibre usando OAuth Authorization Code.

Requiere en .env:
    ML_APP_ID         — client_id de tu app en developers.mercadolibre.com
    ML_CLIENT_SECRET  — client_secret de tu app
    ML_ACCESS_TOKEN   — token obtenido con ml_oauth_setup.py
    ML_REFRESH_TOKEN  — refresh token para renovar automáticamente
"""

import os
import time
import logging
import requests
from dotenv import load_dotenv, set_key

load_dotenv()

logger = logging.getLogger(__name__)

MELI_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", "..", ".env")

_token: str | None = None
_token_expires_at: float = 0


def _refresh_token() -> str | None:
    """Renueva el access token usando el refresh token guardado en .env."""
    app_id = os.getenv("ML_APP_ID", "").strip()
    client_secret = os.getenv("ML_CLIENT_SECRET", "").strip()
    refresh = os.getenv("ML_REFRESH_TOKEN", "").strip()

    if not all([app_id, client_secret, refresh]):
        return None

    try:
        resp = requests.post(
            MELI_TOKEN_URL,
            data={
                "grant_type":    "refresh_token",
                "client_id":     app_id,
                "client_secret": client_secret,
                "refresh_token": refresh,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        env_path = os.path.abspath(ENV_FILE)
        set_key(env_path, "ML_ACCESS_TOKEN",  data["access_token"])
        set_key(env_path, "ML_REFRESH_TOKEN", data["refresh_token"])
        os.environ["ML_ACCESS_TOKEN"]  = data["access_token"]
        os.environ["ML_REFRESH_TOKEN"] = data["refresh_token"]

        logger.info("Access token de MercadoLibre renovado con refresh_token.")
        return data["access_token"], data.get("expires_in", 21600)

    except Exception as e:
        logger.error(f"Error al renovar token de MercadoLibre: {e}")
        return None


def get_access_token() -> str | None:
    global _token, _token_expires_at

    if _token and time.time() < _token_expires_at - 60:
        return _token

    stored = os.getenv("ML_ACCESS_TOKEN", "").strip()
    if stored:
        result = _refresh_token()
        if result:
            _token, expires_in = result
            _token_expires_at = time.time() + expires_in
            return _token
        # Si el refresh falla, usar el token almacenado tal cual
        _token = stored
        _token_expires_at = time.time() + 3600
        return _token

    logger.warning(
        "ML_ACCESS_TOKEN no configurado. Ejecutá: python -m backend.ml_integration.ml_oauth_setup"
    )
    return None


def get_auth_headers() -> dict:
    token = get_access_token()
    return {"Authorization": f"Bearer {token}"} if token else {}
