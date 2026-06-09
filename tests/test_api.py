import pytest
from tests.conftest import BASE, get_any_property_id, get_analyzed_property_id


def test_health(client):
    r = client.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_properties_devuelve_lista(client):
    r = client.get(f"{BASE}/properties")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "propiedades" in data
    assert isinstance(data["propiedades"], list)
    assert data["total"] >= 0


def test_properties_paginacion(client):
    r = client.get(f"{BASE}/properties?limit=5&skip=0")
    assert r.status_code == 200
    assert len(r.json()["propiedades"]) <= 5


def test_properties_paginacion_skip(client):
    r1 = client.get(f"{BASE}/properties?limit=2&skip=0")
    r2 = client.get(f"{BASE}/properties?limit=2&skip=2")
    ids1 = [p["id"] for p in r1.json()["propiedades"]]
    ids2 = [p["id"] for p in r2.json()["propiedades"]]
    assert set(ids1).isdisjoint(set(ids2)), "skip no debería devolver las mismas propiedades"


def test_properties_filtro_fuente(client):
    for fuente in ["zonaprop", "mendozaprop", "argenprop"]:
        r = client.get(f"{BASE}/properties?fuente={fuente}&limit=5")
        assert r.status_code == 200
        for p in r.json()["propiedades"]:
            assert p["fuente"] == fuente


def test_properties_filtro_tipo_operacion(client):
    for tipo in ["alquiler", "venta"]:
        r = client.get(f"{BASE}/properties?tipo_operacion={tipo}&limit=5")
        assert r.status_code == 200
        for p in r.json()["propiedades"]:
            assert p["tipo_operacion"] == tipo


def test_properties_filtro_min_score(client):
    r = client.get(f"{BASE}/properties?min_score=5&limit=10")
    assert r.status_code == 200
    for p in r.json()["propiedades"]:
        assert p["score_accesibilidad"] is not None
        assert p["score_accesibilidad"] >= 5


def test_properties_solo_analizados(client):
    r = client.get(f"{BASE}/properties?solo_analizados=true&limit=10")
    assert r.status_code == 200
    for p in r.json()["propiedades"]:
        assert p["score_accesibilidad"] is not None


def test_property_not_found(client):
    r = client.get(f"{BASE}/properties/999999999")
    assert r.status_code == 404


def test_property_detail_estructura(client):
    prop_id = get_any_property_id(client)
    r = client.get(f"{BASE}/properties/{prop_id}")
    assert r.status_code == 200
    data = r.json()
    for campo in ["id", "titulo", "fuente", "analizado", "permalink_ml"]:
        assert campo in data, f"Falta el campo '{campo}' en el detalle"


def test_property_detail_analizada_tiene_criterios(client):
    prop_id = get_analyzed_property_id(client)
    r = client.get(f"{BASE}/properties/{prop_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["criterios_detectados"] is not None
    criterios = data["criterios_detectados"]
    for k in ["rampa", "ascensor", "bano_adaptado", "entrada_ancha",
              "estacionamiento_adaptado", "ducha_nivel_piso", "pasamanos", "planta_baja"]:
        assert k in criterios, f"Criterio '{k}' ausente en criterios_detectados"
        assert isinstance(criterios[k], bool)


def test_nivel_accesibilidad_en_lista(client):
    r = client.get(f"{BASE}/properties?min_score=0.1&limit=5")
    niveles_validos = {"Muy accesible", "Accesible", "Parcialmente accesible", "Poco accesible"}
    for p in r.json()["propiedades"]:
        if p["score_accesibilidad"] is not None:
            assert p["nivel_accesibilidad"] in niveles_validos


def test_properties_busqueda_texto(client):
    r = client.get(f"{BASE}/properties?q=casa&limit=5")
    assert r.status_code == 200
    assert "propiedades" in r.json()


def test_comments_propiedad_existente(client):
    prop_id = get_any_property_id(client)
    r = client.get(f"{BASE}/properties/{prop_id}/comments")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_votos_criterios_propiedad_existente(client):
    prop_id = get_any_property_id(client)
    r = client.get(f"{BASE}/properties/{prop_id}/votos_criterios")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)
