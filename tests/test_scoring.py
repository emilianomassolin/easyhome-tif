import pytest
from backend.scoring.calculator import calcular_score, CRITERIOS


NLP_VACIO   = {c: False for c in CRITERIOS} | {"confianza": 0.0}
VISION_VACIA = {c: False for c in CRITERIOS} | {"imagenes_analizadas": 0, "descripciones": []}

def _nlp(**kwargs):
    return {**NLP_VACIO, "confianza": 0.9, **kwargs}

def _vision(**kwargs):
    return {**VISION_VACIA, "imagenes_analizadas": 2, **kwargs}


def test_sin_criterios_score_cero():
    resultado = calcular_score(NLP_VACIO, VISION_VACIA)
    assert resultado["score_accesibilidad"] == 0.0
    assert resultado["nivel"] == "Poco accesible"

def test_todos_criterios_score_maximo():
    nlp    = {c: True for c in CRITERIOS} | {"confianza": 1.0}
    vision = {c: True for c in CRITERIOS} | {"imagenes_analizadas": 3, "descripciones": []}
    resultado = calcular_score(nlp, vision)
    assert resultado["score_accesibilidad"] == 10.0
    assert resultado["nivel"] == "Muy accesible"

def test_solo_texto_rampa_y_ascensor():
    nlp = _nlp(rampa=True, ascensor=True)
    resultado = calcular_score(nlp, VISION_VACIA)
    assert resultado["score_accesibilidad"] > 0
    assert resultado["criterios_detectados"]["rampa"] is True
    assert resultado["criterios_detectados"]["ascensor"] is True
    assert resultado["criterios_detectados"]["bano_adaptado"] is False

def test_vision_suma_al_score():
    nlp_con_rampa   = _nlp(rampa=True)
    vision_con_rampa = _vision(rampa=True)
    solo_texto = calcular_score(nlp_con_rampa, VISION_VACIA)
    texto_y_vision = calcular_score(nlp_con_rampa, vision_con_rampa)
    assert texto_y_vision["score_accesibilidad"] > solo_texto["score_accesibilidad"]

def test_niveles_correctos():
    todos = {c: True for c in CRITERIOS}
    # "Muy accesible" requiere texto + visión (el 40% de visión pesa)
    casos = [
        (todos | {"confianza": 1.0}, todos | {"imagenes_analizadas": 3, "descripciones": []}, "Muy accesible"),
        (_nlp(rampa=True, ascensor=True, bano_adaptado=True, entrada_ancha=True,
              sin_escalones=True, piso_plano=True, estacionamiento_adaptado=True), VISION_VACIA, "Accesible"),
        (_nlp(rampa=True, ascensor=True, bano_adaptado=True, entrada_ancha=True), VISION_VACIA, "Parcialmente accesible"),
        (NLP_VACIO, VISION_VACIA, "Poco accesible"),
    ]
    for nlp, vision, nivel_esperado in casos:
        r = calcular_score(nlp, vision)
        assert r["nivel"] == nivel_esperado, f"Esperaba {nivel_esperado}, obtuve {r['nivel']} con score {r['score_accesibilidad']}"

def test_justificacion_menciona_criterios():
    nlp = _nlp(rampa=True, ascensor=True)
    resultado = calcular_score(nlp, VISION_VACIA)
    assert "Rampa" in resultado["justificacion"]
    assert "Ascensor" in resultado["justificacion"]

def test_justificacion_sin_criterios():
    resultado = calcular_score(NLP_VACIO, VISION_VACIA)
    assert "No se detectaron" in resultado["justificacion"]

def test_confianza_rango():
    resultado = calcular_score(_nlp(), _vision())
    assert 0.0 <= resultado["confianza"] <= 1.0
