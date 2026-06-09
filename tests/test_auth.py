import pytest
from tests.conftest import BASE, unique_email, register_user


# ── Registro ───────────────────────────────────────────────────────────────────

def test_register_nuevo_usuario(client):
    email = unique_email()
    r = client.post(f"{BASE}/auth/register", json={"email": email, "password": "test123", "nombre": "Test User"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["user"]["email"] == email
    assert data["user"]["nombre"] == "Test User"


def test_register_sin_nombre(client):
    r = client.post(f"{BASE}/auth/register", json={"email": unique_email(), "password": "test123"})
    assert r.status_code == 200


def test_register_email_duplicado(client):
    email = unique_email()
    client.post(f"{BASE}/auth/register", json={"email": email, "password": "test123"})
    r = client.post(f"{BASE}/auth/register", json={"email": email, "password": "otraclave"})
    assert r.status_code == 409
    assert "existe" in r.json()["detail"].lower()


def test_register_password_corta(client):
    r = client.post(f"{BASE}/auth/register", json={"email": unique_email(), "password": "abc"})
    assert r.status_code == 400


def test_register_email_invalido(client):
    r = client.post(f"{BASE}/auth/register", json={"email": "noesunemail", "password": "test123"})
    assert r.status_code == 422


# ── Login ──────────────────────────────────────────────────────────────────────

def test_login_correcto(client):
    token, _, email = register_user(client)
    r = client.post(f"{BASE}/auth/login", json={"email": email, "password": "test123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["user"]["email"] == email


def test_login_password_incorrecta(client):
    token, _, email = register_user(client)
    r = client.post(f"{BASE}/auth/login", json={"email": email, "password": "clavemala"})
    assert r.status_code == 401


def test_login_email_inexistente(client):
    r = client.post(f"{BASE}/auth/login", json={"email": "nadie@x.com", "password": "test123"})
    assert r.status_code == 401


def test_login_devuelve_token_valido(client):
    token, _, email = register_user(client)
    r = client.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


# ── /me ────────────────────────────────────────────────────────────────────────

def test_me_con_token_valido(client):
    token, _, email = register_user(client)
    r = client.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email


def test_me_sin_token(client):
    r = client.get(f"{BASE}/auth/me")
    assert r.status_code == 401


def test_me_token_invalido(client):
    r = client.get(f"{BASE}/auth/me", headers={"Authorization": "Bearer tokeninvalido.fake.123"})
    assert r.status_code == 401


def test_me_no_es_admin_por_defecto(client):
    token, _, _ = register_user(client)
    r = client.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["is_admin"] is False


# ── Forgot / Reset password ────────────────────────────────────────────────────

def test_forgot_password_email_existente(client):
    token, _, email = register_user(client)
    r = client.post(f"{BASE}/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    assert "mensaje" in r.json()


def test_forgot_password_email_inexistente_mismo_status(client):
    """No revelar si el email existe o no."""
    r = client.post(f"{BASE}/auth/forgot-password", json={"email": "noexiste@nowhere.com"})
    assert r.status_code == 200


def test_reset_password_token_invalido(client):
    r = client.post(f"{BASE}/auth/reset-password", json={"token": "tokenfalso123", "new_password": "nueva123"})
    assert r.status_code == 400


def test_reset_password_nueva_corta(client):
    r = client.post(f"{BASE}/auth/reset-password", json={"token": "cualquier", "new_password": "abc"})
    assert r.status_code == 400


def test_reset_password_flujo_completo(client):
    """Obtiene token de forgot, lo usa en reset, puede loguearse con la nueva clave."""
    token_reg, _, email = register_user(client)
    # Pedir reset
    forgot = client.post(f"{BASE}/auth/forgot-password", json={"email": email})
    reset_token = forgot.json().get("_debug_reset_token")
    if not reset_token:
        pytest.skip("No se devolvió _debug_reset_token (puede que el usuario no tenga password_hash aún)")
    # Resetear
    r = client.post(f"{BASE}/auth/reset-password", json={"token": reset_token, "new_password": "nuevaclave123"})
    assert r.status_code == 200
    # Login con la nueva clave
    login = client.post(f"{BASE}/auth/login", json={"email": email, "password": "nuevaclave123"})
    assert login.status_code == 200
    # La vieja clave ya no sirve
    old = client.post(f"{BASE}/auth/login", json={"email": email, "password": "test123"})
    assert old.status_code == 401
