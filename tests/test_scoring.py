import pytest
from backend.scoring.calculator import calcular_score, CRITERIOS, detectar_tipo, NIVELES


NLP_VACIO   = {c: False for c in CRITERIOS} | {"confianza": 0.0}
VISION_VACIA = {c: False for c in CRITERIOS} | {"imagenes_analizadas": 0, "descripciones": []}


def _nlp(**kwargs):
    return {**NLP_VACIO, "confianza": 0.9, **kwargs}


def _vision(**kwargs):
    return {**VISION_VACIA, "imagenes_analizadas": 2, **kwargs}


# ── Tests de score básico ─────────────────────────────────────────────────────

def test_sin_criterios_score_cero():
    r = calcular_score(NLP_VACIO, VISION_VACIA)
    assert r["score_accesibilidad"] == 0.0
    assert r["nivel"] == "Poco accesible"


def test_todos_criterios_score_maximo():
    nlp    = {c: True for c in CRITERIOS} | {"confianza": 1.0}
    vision = {c: True for c in CRITERIOS} | {"imagenes_analizadas": 3, "descripciones": []}
    r = calcular_score(nlp, vision)
    assert r["score_accesibilidad"] == 10.0
    assert r["nivel"] == "Muy accesible"


def test_score_en_rango_0_10():
    nlp = _nlp(rampa=True, ascensor=True)
    r = calcular_score(nlp, VISION_VACIA)
    assert 0.0 <= r["score_accesibilidad"] <= 10.0


def test_solo_texto_rampa_y_ascensor():
    nlp = _nlp(rampa=True, ascensor=True)
    r = calcular_score(nlp, VISION_VACIA)
    assert r["score_accesibilidad"] > 0
    assert r["criterios_detectados"]["rampa"] is True
    assert r["criterios_detectados"]["ascensor"] is True
    assert r["criterios_detectados"]["bano_adaptado"] is False


def test_vision_agrega_criterio_nuevo():
    """Vision detectando un criterio DIFERENTE al NLP debe aumentar el score."""
    nlp   = _nlp(rampa=True)           # solo rampa
    vision = _vision(ascensor=True)     # solo ascensor (distinto)
    solo_texto    = calcular_score(nlp, VISION_VACIA)
    texto_y_vision = calcular_score(nlp, vision)
    assert texto_y_vision["score_accesibilidad"] > solo_texto["score_accesibilidad"]


def test_vision_criterio_duplicado_no_suma():
    """Si visión y NLP detectan el MISMO criterio, el score no varía."""
    nlp    = _nlp(rampa=True)
    vision = _vision(rampa=True)
    solo_texto    = calcular_score(nlp, VISION_VACIA)
    texto_y_vision = calcular_score(nlp, vision)
    assert texto_y_vision["score_accesibilidad"] == solo_texto["score_accesibilidad"]


# ── Tests de niveles ──────────────────────────────────────────────────────────

def test_niveles_correctos():
    casos = [
        # 8 criterios: 10/10 → Muy accesible
        ({c: True for c in CRITERIOS} | {"confianza": 1.0},
         {c: True for c in CRITERIOS} | {"imagenes_analizadas": 3, "descripciones": []},
         "Muy accesible"),
        # 5 criterios: 5/8*10=6.25 → Accesible
        (_nlp(rampa=True, ascensor=True, bano_adaptado=True, entrada_ancha=True, estacionamiento_adaptado=True),
         VISION_VACIA, "Accesible"),
        # 4 criterios: 4/8*10=5.0 → Parcialmente accesible (< 6.0)
        (_nlp(rampa=True, ascensor=True, bano_adaptado=True, entrada_ancha=True),
         VISION_VACIA, "Parcialmente accesible"),
        # 0 criterios → Poco accesible
        (NLP_VACIO, VISION_VACIA, "Poco accesible"),
    ]
    for nlp, vision, nivel_esperado in casos:
        r = calcular_score(nlp, vision)
        assert r["nivel"] == nivel_esperado, (
            f"Esperaba {nivel_esperado}, obtuve {r['nivel']} con score {r['score_accesibilidad']}"
        )


# ── Tests de manual_override ──────────────────────────────────────────────────

def test_manual_override_agrega_criterio():
    """manual_override True agrega un criterio que el NLP no detectó."""
    r_sin = calcular_score(NLP_VACIO, VISION_VACIA)
    r_con = calcular_score(NLP_VACIO, VISION_VACIA, manual_override={"ascensor": True})
    assert r_con["score_accesibilidad"] > r_sin["score_accesibilidad"]
    assert r_con["criterios_detectados"]["ascensor"] is True


def test_manual_override_quita_criterio():
    """manual_override False elimina un criterio que el NLP sí detectó."""
    nlp = _nlp(rampa=True, ascensor=True)
    r_sin = calcular_score(nlp, VISION_VACIA)
    r_con = calcular_score(nlp, VISION_VACIA, manual_override={"rampa": False})
    assert r_con["score_accesibilidad"] < r_sin["score_accesibilidad"]
    assert r_con["criterios_detectados"]["rampa"] is False
    assert r_con["criterios_detectados"]["ascensor"] is True


def test_manual_override_criterio_invalido_ignorado():
    """Criterio que no está en CRITERIOS es ignorado silenciosamente."""
    r = calcular_score(NLP_VACIO, VISION_VACIA, manual_override={"criterio_fantasma": True})
    assert r["score_accesibilidad"] == 0.0


def test_manual_override_none_no_cambia_nada():
    r1 = calcular_score(NLP_VACIO, VISION_VACIA)
    r2 = calcular_score(NLP_VACIO, VISION_VACIA, manual_override=None)
    assert r1["score_accesibilidad"] == r2["score_accesibilidad"]


# ── Tests de tipo de propiedad ────────────────────────────────────────────────

def test_detectar_tipo_terreno():
    assert detectar_tipo("Vendo lote en Godoy Cruz") == "terreno"
    assert detectar_tipo("Terreno con vista al cerro") == "terreno"
    assert detectar_tipo("Finca en Luján de Cuyo") == "terreno"


def test_detectar_tipo_cochera():
    assert detectar_tipo("Cochera en alquiler") == "cochera"
    assert detectar_tipo("Garage amplio zona centro") == "cochera"


def test_detectar_tipo_galpon():
    assert detectar_tipo("Galpón industrial en venta") == "galpon"
    assert detectar_tipo("Deposito 500m2") == "galpon"


def test_detectar_tipo_otro():
    assert detectar_tipo("Casa 3 dormitorios") == "otro"
    assert detectar_tipo("Departamento luminoso") == "otro"
    assert detectar_tipo(None) == "otro"


def test_terreno_excluye_criterios_no_aplicables():
    """Un terreno no incluye ascensor, baño, etc. en criterios_detectados."""
    nlp = {c: True for c in CRITERIOS} | {"confianza": 1.0}
    r = calcular_score(nlp, VISION_VACIA, titulo="Vendo lote en Godoy Cruz")
    # Criterios excluidos para terreno no deben aparecer en el resultado
    assert "ascensor" not in r["criterios_detectados"]
    assert "bano_adaptado" not in r["criterios_detectados"]
    assert "ducha_nivel_piso" not in r["criterios_detectados"]
    assert "pasamanos" not in r["criterios_detectados"]
    # Criterios aplicables sí deben aparecer
    assert "rampa" in r["criterios_detectados"]
    assert "estacionamiento_adaptado" in r["criterios_detectados"]
    assert r["tipo_propiedad"] == "terreno"


# ── Tests de justificación ────────────────────────────────────────────────────

def test_justificacion_menciona_criterios():
    nlp = _nlp(rampa=True, ascensor=True)
    r = calcular_score(nlp, VISION_VACIA)
    assert "Rampa" in r["justificacion"]
    assert "Ascensor" in r["justificacion"]


def test_justificacion_sin_criterios():
    r = calcular_score(NLP_VACIO, VISION_VACIA)
    assert "No se detectaron" in r["justificacion"]


def test_justificacion_menciona_vision():
    nlp   = _nlp(rampa=True)
    vision = _vision(ascensor=True)
    r = calcular_score(nlp, vision)
    assert "imágenes" in r["justificacion"]


def test_justificacion_menciona_descripcion():
    nlp = _nlp(rampa=True)
    r = calcular_score(nlp, VISION_VACIA)
    assert "descripción" in r["justificacion"]


# ── Tests de confianza ────────────────────────────────────────────────────────

def test_confianza_rango():
    r = calcular_score(_nlp(), _vision())
    assert 0.0 <= r["confianza"] <= 1.0


def test_confianza_mayor_con_imagenes():
    sin_imagenes = calcular_score(_nlp(), VISION_VACIA)
    con_imagenes = calcular_score(_nlp(), _vision())
    assert con_imagenes["confianza"] > sin_imagenes["confianza"]


# ── Test de estructura del resultado ─────────────────────────────────────────

def test_resultado_tiene_todas_las_claves():
    r = calcular_score(NLP_VACIO, VISION_VACIA)
    for k in ["score_accesibilidad", "nivel", "criterios_detectados", "justificacion", "confianza", "tipo_propiedad"]:
        assert k in r, f"Falta la clave '{k}' en el resultado"
