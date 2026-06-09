import uuid
import pytest
from fastapi.testclient import TestClient
from backend.main import app

BASE = "/api"


@pytest.fixture(scope="session")
def client():
    """TestClient reutilizable para toda la sesión de tests."""
    with TestClient(app) as c:
        yield c


def unique_email():
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


def register_user(client, password="test123", nombre=None):
    email = unique_email()
    r = client.post(f"{BASE}/auth/register", json={"email": email, "password": password, "nombre": nombre})
    assert r.status_code == 200, r.text
    data = r.json()
    return data["access_token"], data["user"]["id"], email


def get_any_property_id(client):
    r = client.get(f"{BASE}/properties?limit=1")
    props = r.json().get("propiedades", [])
    if not props:
        pytest.skip("No hay propiedades en la BD")
    return props[0]["id"]


def get_analyzed_property_id(client):
    r = client.get(f"{BASE}/properties?solo_analizados=true&limit=1")
    props = r.json().get("propiedades", [])
    if not props:
        pytest.skip("No hay propiedades analizadas en la BD")
    return props[0]["id"]
