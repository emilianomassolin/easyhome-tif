import pytest

# MercadoLibre fue descartado del proyecto por restricciones anti-bot y
# OAuth que vence cada 6h. Estos tests se saltean permanentemente para no
# romper la suite de CI.
pytestmark = pytest.mark.skip(reason="MercadoLibre OAuth vencido; fuente descartada del proyecto")


def test_api_devuelve_resultados():
    pass


def test_propiedad_tiene_campos_requeridos():
    pass


def test_paginacion_funciona():
    pass
