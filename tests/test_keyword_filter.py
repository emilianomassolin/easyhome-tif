import pytest
from backend.nlp.keyword_filter import tiene_keywords_accesibilidad, RESULTADO_VACIO, VISION_VACIA
from backend.scoring.calculator import CRITERIOS


# ── Detección de keywords ──────────────────────────────────────────────────────

def test_detecta_rampa():
    assert tiene_keywords_accesibilidad("Casa con rampa de acceso", None) is True


def test_detecta_planta_baja():
    assert tiene_keywords_accesibilidad(None, "Departamento en planta baja, sin escalones") is True


def test_detecta_ascensor():
    assert tiene_keywords_accesibilidad("Edificio con ascensor", "Piso 3") is True


def test_detecta_silla_ruedas():
    assert tiene_keywords_accesibilidad(None, "Adaptado para silla de ruedas") is True


def test_detecta_ducha_italiana():
    assert tiene_keywords_accesibilidad(None, "Baño con ducha italiana a nivel de piso") is True


def test_detecta_pasamanos():
    assert tiene_keywords_accesibilidad(None, "Escalera con pasamanos en ambos lados") is True


def test_detecta_baranda():
    assert tiene_keywords_accesibilidad(None, "Balcón con baranda de seguridad") is True


def test_detecta_pmd():
    assert tiene_keywords_accesibilidad(None, "Cochera pmd incluida") is True


def test_detecta_accesible_general():
    assert tiene_keywords_accesibilidad("Propiedad accesible para adultos mayores", None) is True


def test_detecta_barrales():
    assert tiene_keywords_accesibilidad(None, "Baño con barrales de apoyo") is True


def test_sin_keywords_retorna_false():
    assert tiene_keywords_accesibilidad("Hermosa casa con jardín", "Amplio living, 3 dormitorios") is False


def test_texto_vacio_retorna_false():
    assert tiene_keywords_accesibilidad(None, None) is False
    assert tiene_keywords_accesibilidad("", "") is False


def test_solo_titulo_vacio_retorna_false():
    assert tiene_keywords_accesibilidad(None, "Tres dormitorios con vista al jardín") is False


def test_case_insensitive():
    assert tiene_keywords_accesibilidad("RAMPA DE ACCESO", None) is True
    assert tiene_keywords_accesibilidad(None, "PLANTA BAJA") is True
    assert tiene_keywords_accesibilidad(None, "ASCENSOR") is True


def test_keyword_en_titulo_basta():
    assert tiene_keywords_accesibilidad("Apto para discapacitado", "Sin descripción especial") is True


def test_keyword_en_descripcion_basta():
    assert tiene_keywords_accesibilidad("Casa linda", "Tiene rampa de acceso") is True


# ── Estructura de RESULTADO_VACIO ──────────────────────────────────────────────

def test_resultado_vacio_tiene_todos_los_criterios():
    """RESULTADO_VACIO debe tener exactamente los criterios de CRITERIOS más 'confianza'."""
    for c in CRITERIOS:
        assert c in RESULTADO_VACIO, f"Criterio '{c}' ausente en RESULTADO_VACIO"
        assert RESULTADO_VACIO[c] is False
    assert "confianza" in RESULTADO_VACIO
    assert RESULTADO_VACIO["confianza"] == 0.0


def test_resultado_vacio_no_tiene_criterios_viejos():
    """Criterios obsoletos no deben estar en RESULTADO_VACIO."""
    for obsoleto in ["sin_escalones", "piso_plano", "pasillo_ancho"]:
        assert obsoleto not in RESULTADO_VACIO, f"'{obsoleto}' no debería existir en RESULTADO_VACIO"


# ── Estructura de VISION_VACIA ─────────────────────────────────────────────────

def test_vision_vacia_estructura():
    assert VISION_VACIA["imagenes_analizadas"] == 0
    assert VISION_VACIA["descripciones"] == []
    for c in CRITERIOS:
        if c != "planta_baja":  # planta_baja es NLP-only, puede no estar en vision
            assert c in VISION_VACIA, f"Criterio '{c}' ausente en VISION_VACIA"


def test_vision_vacia_valores_false():
    for c in CRITERIOS:
        if c in VISION_VACIA:
            assert VISION_VACIA[c] is False
