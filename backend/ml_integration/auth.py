"""
Gestión del access token de MercadoLibre usando OAuth client_credentials.

Requiere en .env:
    ML_APP_ID      — client_id de tu app en developers.mercadolibre.com
    ML_CLIENT_SECRET — client_secret de tu app

El token se cachea en memoria y se renueva automáticamente al vencer.
"""

import os
import time
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MELI_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

_token: str | None = None
_token_expires_at: float = 0


def get_access_token() -> str | None:
    """Devuelve un access token válido, renovándolo si venció."""
    global _token, _token_expires_at

    if _token and time.time() < _token_expires_at - 60:
        return _token

    app_id = os.getenv("ML_APP_ID", "").strip()
    client_secret = os.getenv("ML_CLIENT_SECRET", "").strip()

    if not app_id or not client_secret:
        logger.warning(
            "ML_APP_ID o ML_CLIENT_SECRET no configurados. "
            "Las llamadas a la API de MercadoLibre pueden fallar."
        )
        return None

    try:
        resp = requests.post(
            MELI_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": app_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _token = data["access_token"]
        _token_expires_at = time.time() + data.get("expires_in", 21600)
        logger.info("Access token de MercadoLibre renovado correctamente.")
        return _token

    except Exception as e:
        logger.error(f"Error al obtener access token de MercadoLibre: {e}")
        return None


def get_auth_headers() -> dict:
    token = get_access_token()
    return {"Authorization": f"Bearer {token}"} if token else {}
