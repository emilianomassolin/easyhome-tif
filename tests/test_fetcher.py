import os
import pytest
import requests

from backend.ml_integration.auth import get_auth_headers

MELI_SEARCH_URL = "https://api.mercadolibre.com/sites/MLA/search"
SEARCH_PARAMS = {
    "category": "MLA1459",
    "state": "TUxBUE1FTkE5OWQ4",  # Mendoza
    "limit": 5,
}


def _skip_if_no_credentials():
    resp = requests.get(MELI_SEARCH_URL, params=SEARCH_PARAMS,
                        headers=get_auth_headers(), timeout=10)
    if resp.status_code == 403:
        pytest.skip("Credenciales de MercadoLibre no configuradas (ML_APP_ID / ML_CLIENT_SECRET).")


def test_api_devuelve_resultados():
    """La API responde con propiedades de Mendoza."""
    _skip_if_no_credentials()
    resp = requests.get(MELI_SEARCH_URL, params=SEARCH_PARAMS,
                        headers=get_auth_headers(), timeout=15)
    assert resp.status_code == 200
    assert len(resp.json()["results"]) > 0


def test_propiedad_tiene_campos_requeridos():
    """Cada propiedad incluye id, title y permalink."""
    _skip_if_no_credentials()
    resp = requests.get(MELI_SEARCH_URL, params=SEARCH_PARAMS,
                        headers=get_auth_headers(), timeout=15)
    item = resp.json()["results"][0]
    assert "id" in item
    assert "title" in item
    assert "permalink" in item


def test_paginacion_funciona():
    """El campo paging.total es mayor a cero."""
    _skip_if_no_credentials()
    resp = requests.get(MELI_SEARCH_URL, params=SEARCH_PARAMS,
                        headers=get_auth_headers(), timeout=15)
    assert resp.json().get("paging", {}).get("total", 0) > 0
