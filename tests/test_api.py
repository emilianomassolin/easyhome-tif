import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_properties_devuelve_lista():
    r = client.get("/properties")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "propiedades" in data
    assert isinstance(data["propiedades"], list)
    assert data["total"] >= 0


def test_properties_paginacion():
    r = client.get("/properties?limit=5&skip=0")
    assert r.status_code == 200
    assert len(r.json()["propiedades"]) <= 5


def test_properties_filtro_fuente():
    for fuente in ["mercadolibre", "zonaprop", "mendozaprop"]:
        r = client.get(f"/properties?fuente={fuente}&limit=5")
        assert r.status_code == 200
        for p in r.json()["propiedades"]:
            assert p["fuente"] == fuente


def test_properties_filtro_tipo_operacion():
    for tipo in ["alquiler", "venta"]:
        r = client.get(f"/properties?tipo_operacion={tipo}&limit=5")
        assert r.status_code == 200
        for p in r.json()["propiedades"]:
            assert p["tipo_operacion"] == tipo


def test_properties_filtro_min_score():
    r = client.get("/properties?min_score=5&limit=10")
    assert r.status_code == 200
    for p in r.json()["propiedades"]:
        assert p["score_accesibilidad"] is not None
        assert p["score_accesibilidad"] >= 5


def test_properties_solo_analizados():
    r = client.get("/properties?solo_analizados=true&limit=10")
    assert r.status_code == 200
    for p in r.json()["propiedades"]:
        # Las analizadas tienen score
        assert p["score_accesibilidad"] is not None


def test_property_not_found():
    r = client.get("/properties/999999999")
    assert r.status_code == 404


def test_property_detail_estructura():
    r = client.get("/properties?limit=1")
    propiedades = r.json()["propiedades"]
    if not propiedades:
        pytest.skip("No hay propiedades en la BD")
    prop_id = propiedades[0]["id"]
    r2 = client.get(f"/properties/{prop_id}")
    assert r2.status_code == 200
    data = r2.json()
    for campo in ["id", "titulo", "fuente", "analizado", "permalink_ml"]:
        assert campo in data


def test_nivel_accesibilidad_en_lista():
    r = client.get("/properties?min_score=0.1&limit=5")
    for p in r.json()["propiedades"]:
        if p["score_accesibilidad"] is not None:
            assert p["nivel_accesibilidad"] in [
                "Muy accesible", "Accesible",
                "Parcialmente accesible", "Poco accesible"
            ]
