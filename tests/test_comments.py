import uuid
import pytest
from tests.conftest import BASE, register_user, get_any_property_id


# ── GET comments ──────────────────────────────────────────────────────────────

def test_get_comments_devuelve_lista(client):
    prop_id = get_any_property_id(client)
    r = client.get(f"{BASE}/properties/{prop_id}/comments")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_comments_propiedad_inexistente(client):
    r = client.get(f"{BASE}/properties/999999999/comments")
    assert r.status_code == 404


# ── POST comments ─────────────────────────────────────────────────────────────

def test_add_comment_sin_auth(client):
    prop_id = get_any_property_id(client)
    r = client.post(f"{BASE}/properties/{prop_id}/comments", json={"texto": "Hola"})
    assert r.status_code == 401


def test_add_comment_con_auth(client):
    prop_id = get_any_property_id(client)
    token, _, _ = register_user(client)
    r = client.post(
        f"{BASE}/properties/{prop_id}/comments",
        json={"texto": "Comentario de test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["texto"] == "Comentario de test"
    assert "id" in data
    assert "user_nombre" in data
    # Limpieza
    client.delete(f"{BASE}/comments/{data['id']}", headers={"Authorization": f"Bearer {token}"})


def test_add_comment_texto_vacio(client):
    prop_id = get_any_property_id(client)
    token, _, _ = register_user(client)
    r = client.post(
        f"{BASE}/properties/{prop_id}/comments",
        json={"texto": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_add_comment_muy_largo(client):
    prop_id = get_any_property_id(client)
    token, _, _ = register_user(client)
    r = client.post(
        f"{BASE}/properties/{prop_id}/comments",
        json={"texto": "x" * 501},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_add_comment_token_invalido(client):
    prop_id = get_any_property_id(client)
    r = client.post(
        f"{BASE}/properties/{prop_id}/comments",
        json={"texto": "Hola"},
        headers={"Authorization": "Bearer tokeninvalido"},
    )
    assert r.status_code == 401


# ── DELETE comments ───────────────────────────────────────────────────────────

def test_delete_comment_propio(client):
    prop_id = get_any_property_id(client)
    token, _, _ = register_user(client)
    add = client.post(
        f"{BASE}/properties/{prop_id}/comments",
        json={"texto": "A borrar"},
        headers={"Authorization": f"Bearer {token}"},
    )
    comment_id = add.json()["id"]
    r = client.delete(f"{BASE}/comments/{comment_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_delete_comment_de_otro_usuario(client):
    prop_id = get_any_property_id(client)
    token1, _, _ = register_user(client)
    token2, _, _ = register_user(client)
    add = client.post(
        f"{BASE}/properties/{prop_id}/comments",
        json={"texto": "Del usuario 1"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    comment_id = add.json()["id"]
    r = client.delete(f"{BASE}/comments/{comment_id}", headers={"Authorization": f"Bearer {token2}"})
    assert r.status_code == 403
    # Limpieza
    client.delete(f"{BASE}/comments/{comment_id}", headers={"Authorization": f"Bearer {token1}"})


def test_delete_comment_sin_auth(client):
    prop_id = get_any_property_id(client)
    token, _, _ = register_user(client)
    add = client.post(
        f"{BASE}/properties/{prop_id}/comments",
        json={"texto": "Sin auth"},
        headers={"Authorization": f"Bearer {token}"},
    )
    comment_id = add.json()["id"]
    r = client.delete(f"{BASE}/comments/{comment_id}")
    assert r.status_code == 401
    # Limpieza
    client.delete(f"{BASE}/comments/{comment_id}", headers={"Authorization": f"Bearer {token}"})


def test_delete_comment_inexistente(client):
    token, _, _ = register_user(client)
    r = client.delete(f"{BASE}/comments/999999999", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


# ── Flujo completo ─────────────────────────────────────────────────────────────

def test_comment_aparece_en_lista_tras_agregar(client):
    prop_id = get_any_property_id(client)
    token, _, _ = register_user(client)
    texto = f"Test_{uuid.uuid4().hex[:6]}"
    add = client.post(
        f"{BASE}/properties/{prop_id}/comments",
        json={"texto": texto},
        headers={"Authorization": f"Bearer {token}"},
    )
    comment_id = add.json()["id"]
    r = client.get(f"{BASE}/properties/{prop_id}/comments")
    textos = [c["texto"] for c in r.json()]
    assert texto in textos
    # Limpieza
    client.delete(f"{BASE}/comments/{comment_id}", headers={"Authorization": f"Bearer {token}"})


def test_comment_desaparece_tras_borrar(client):
    prop_id = get_any_property_id(client)
    token, _, _ = register_user(client)
    texto = f"Borrar_{uuid.uuid4().hex[:6]}"
    add = client.post(
        f"{BASE}/properties/{prop_id}/comments",
        json={"texto": texto},
        headers={"Authorization": f"Bearer {token}"},
    )
    comment_id = add.json()["id"]
    client.delete(f"{BASE}/comments/{comment_id}", headers={"Authorization": f"Bearer {token}"})
    r = client.get(f"{BASE}/properties/{prop_id}/comments")
    textos = [c["texto"] for c in r.json()]
    assert texto not in textos
