import pytest
from tests.conftest import BASE, register_user, get_analyzed_property_id


CRITERIOS_VALIDOS = [
    "rampa", "ascensor", "bano_adaptado", "entrada_ancha",
    "estacionamiento_adaptado", "ducha_nivel_piso", "pasamanos", "planta_baja",
]


# ── GET votos ─────────────────────────────────────────────────────────────────

def test_get_votos_devuelve_dict(client):
    prop_id = get_analyzed_property_id(client)
    r = client.get(f"{BASE}/properties/{prop_id}/votos_criterios")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_get_votos_claves_son_criterios(client):
    prop_id = get_analyzed_property_id(client)
    # Primero votamos para que haya datos
    token, _, _ = register_user(client)
    client.post(
        f"{BASE}/properties/{prop_id}/votar_criterio",
        json={"criterio": "ascensor", "valor": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = client.get(f"{BASE}/properties/{prop_id}/votos_criterios")
    for key in r.json():
        assert key in CRITERIOS_VALIDOS
    # Limpieza
    client.delete(
        f"{BASE}/properties/{prop_id}/votos_criterios/ascensor",
        headers={"Authorization": f"Bearer {token}"},
    )


# ── POST votar_criterio ───────────────────────────────────────────────────────

def test_votar_sin_auth(client):
    prop_id = get_analyzed_property_id(client)
    r = client.post(
        f"{BASE}/properties/{prop_id}/votar_criterio",
        json={"criterio": "ascensor", "valor": False},
    )
    assert r.status_code == 401


def test_votar_criterio_invalido(client):
    prop_id = get_analyzed_property_id(client)
    token, _, _ = register_user(client)
    r = client.post(
        f"{BASE}/properties/{prop_id}/votar_criterio",
        json={"criterio": "criterio_inexistente", "valor": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_votar_propiedad_inexistente(client):
    token, _, _ = register_user(client)
    r = client.post(
        f"{BASE}/properties/999999999/votar_criterio",
        json={"criterio": "ascensor", "valor": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_votar_criterio_valido_false(client):
    prop_id = get_analyzed_property_id(client)
    token, _, _ = register_user(client)
    r = client.post(
        f"{BASE}/properties/{prop_id}/votar_criterio",
        json={"criterio": "pasamanos", "valor": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert isinstance(data["votos"], int)
    assert data["votos"] >= 1
    assert "applied" in data
    assert "score_accesibilidad" in data
    # Limpieza
    client.delete(
        f"{BASE}/properties/{prop_id}/votos_criterios/pasamanos",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_votar_criterio_valido_true(client):
    prop_id = get_analyzed_property_id(client)
    token, _, _ = register_user(client)
    r = client.post(
        f"{BASE}/properties/{prop_id}/votar_criterio",
        json={"criterio": "rampa", "valor": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # Limpieza
    client.delete(
        f"{BASE}/properties/{prop_id}/votos_criterios/rampa",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_voto_duplicado_cuenta_como_uno(client):
    """El mismo usuario votando dos veces el mismo criterio no debe duplicar el conteo."""
    prop_id = get_analyzed_property_id(client)
    token, _, _ = register_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    r1 = client.post(
        f"{BASE}/properties/{prop_id}/votar_criterio",
        json={"criterio": "entrada_ancha", "valor": False},
        headers=headers,
    )
    votos_1 = r1.json()["votos"]
    r2 = client.post(
        f"{BASE}/properties/{prop_id}/votar_criterio",
        json={"criterio": "entrada_ancha", "valor": False},
        headers=headers,
    )
    votos_2 = r2.json()["votos"]
    assert votos_2 == votos_1, "Votar dos veces no debe aumentar el conteo"
    # Limpieza
    client.delete(
        f"{BASE}/properties/{prop_id}/votos_criterios/entrada_ancha",
        headers=headers,
    )


def test_respuesta_incluye_score_cuando_applied(client):
    """Si applied=True, la respuesta debe incluir el nuevo score."""
    # Este test solo verifica la estructura; no forzamos 3 votos porque requeriría 3 usuarios
    prop_id = get_analyzed_property_id(client)
    token, _, _ = register_user(client)
    r = client.post(
        f"{BASE}/properties/{prop_id}/votar_criterio",
        json={"criterio": "bano_adaptado", "valor": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = r.json()
    assert "score_accesibilidad" in data
    if data["applied"]:
        assert data["score_accesibilidad"] is not None
    else:
        assert data["score_accesibilidad"] is None
    # Limpieza
    client.delete(
        f"{BASE}/properties/{prop_id}/votos_criterios/bano_adaptado",
        headers={"Authorization": f"Bearer {token}"},
    )


# ── DELETE voto ───────────────────────────────────────────────────────────────

def test_eliminar_voto_sin_auth(client):
    prop_id = get_analyzed_property_id(client)
    r = client.delete(f"{BASE}/properties/{prop_id}/votos_criterios/ascensor")
    assert r.status_code == 401


def test_eliminar_voto_inexistente(client):
    prop_id = get_analyzed_property_id(client)
    token, _, _ = register_user(client)
    r = client.delete(
        f"{BASE}/properties/{prop_id}/votos_criterios/ascensor",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_eliminar_voto_propio(client):
    prop_id = get_analyzed_property_id(client)
    token, _, _ = register_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        f"{BASE}/properties/{prop_id}/votar_criterio",
        json={"criterio": "planta_baja", "valor": True},
        headers=headers,
    )
    r = client.delete(
        f"{BASE}/properties/{prop_id}/votos_criterios/planta_baja",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_tras_eliminar_voto_ya_no_existe(client):
    prop_id = get_analyzed_property_id(client)
    token, _, _ = register_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        f"{BASE}/properties/{prop_id}/votar_criterio",
        json={"criterio": "ducha_nivel_piso", "valor": True},
        headers=headers,
    )
    client.delete(
        f"{BASE}/properties/{prop_id}/votos_criterios/ducha_nivel_piso",
        headers=headers,
    )
    # Intentar borrar de nuevo → 404
    r = client.delete(
        f"{BASE}/properties/{prop_id}/votos_criterios/ducha_nivel_piso",
        headers=headers,
    )
    assert r.status_code == 404
