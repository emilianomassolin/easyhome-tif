import pytest
from backend.nlp.keyword_filter import tiene_keywords_accesibilidad, RESULTADO_VACIO, VISION_VACIA


def test_detecta_rampa():
    assert tiene_keywords_accesibilidad("Casa con rampa de acceso", None) is True

def test_detecta_planta_baja():
    assert tiene_keywords_accesibilidad(None, "Departamento en planta baja, sin escalones") is True

def test_detecta_ascensor():
    assert tiene_keywords_accesibilidad("Edificio con ascensor", "Piso 3") is True

def test_detecta_silla_ruedas():
    assert tiene_keywords_accesibilidad(None, "Adaptado para silla de ruedas") is True

def test_sin_keywords_retorna_false():
    assert tiene_keywords_accesibilidad("Hermosa casa con jardín", "Amplio living, 3 dormitorios") is False

def test_texto_vacio_retorna_false():
    assert tiene_keywords_accesibilidad(None, None) is False
    assert tiene_keywords_accesibilidad("", "") is False

def test_case_insensitive():
    assert tiene_keywords_accesibilidad("RAMPA DE ACCESO", None) is True
    assert tiene_keywords_accesibilidad(None, "PLANTA BAJA") is True

def test_resultado_vacio_estructura():
    criterios = ["rampa", "ascensor", "bano_adaptado", "entrada_ancha",
                 "sin_escalones", "piso_plano", "estacionamiento_adaptado"]
    for c in criterios:
        assert RESULTADO_VACIO[c] is False
    assert RESULTADO_VACIO["confianza"] == 0.0

def test_vision_vacia_estructura():
    assert VISION_VACIA["imagenes_analizadas"] == 0
    assert VISION_VACIA["descripciones"] == []
