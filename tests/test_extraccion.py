"""Pruebas de la extracción de geometría y fuerzas con un SapModel simulado."""

from __future__ import annotations

import pytest
from conftest import COMBOS

from vigas_e060.config import ConfiguracionDiseno
from vigas_e060.etabs.extraccion import (
    extraer_fuerzas,
    extraer_vigas,
    leer_fuerzas_combo,
    listar_resumen_vigas,
)


def test_extraer_vigas_geometria(conexion):
    vigas = extraer_vigas(conexion, ConfiguracionDiseno())
    assert len(vigas) == 1
    v = vigas[0]
    assert v.nombre == "V-101"
    assert v.etiqueta == "V-101"
    assert v.piso == "Piso 2"
    assert v.seccion == "VP-25x50"
    assert v.geometria.b == pytest.approx(25)
    assert v.geometria.h == pytest.approx(50)
    assert v.geometria.L == pytest.approx(6.0)
    assert v.geometria.ln == pytest.approx(5.4)
    assert v.offset_i_m == pytest.approx(0.3)
    assert v.offset_j_m == pytest.approx(0.3)
    assert v.materiales.fc == pytest.approx(210)
    assert v.recubrimiento_etabs_cm == pytest.approx(6.0)
    assert v.soportes == "C-1 / C-2"


def test_filtros_y_resumen(conexion):
    config = ConfiguracionDiseno(vigas=("V-101",), pisos=("Piso 2",))
    vigas = extraer_vigas(conexion, config)
    assert [v.nombre for v in vigas] == ["V-101"]
    filas = listar_resumen_vigas(vigas)
    assert filas and filas[0]["Nombre"] == "V-101"

    none = extraer_vigas(conexion, ConfiguracionDiseno(vigas=("NO-EXISTE",)))
    assert none == []


def test_leer_fuerzas_combo(conexion):
    puntos = leer_fuerzas_combo(conexion, "V-101", "E060-1.4D+1.7L")
    assert len(puntos) == 5
    assert [p.estacion_m for p in puntos] == [0.0, 0.3, 3.0, 5.7, 6.0]
    assert puntos[0].M3_tm == pytest.approx(-12.0)
    assert puntos[2].M3_tm == pytest.approx(8.5)
    assert puntos[0].V2_t == pytest.approx(14.0)
    assert puntos[0].P_t == pytest.approx(-2.0)


def test_extraer_fuerzas(conexion):
    viga = extraer_vigas(conexion, ConfiguracionDiseno())[0]
    combos = list(COMBOS)
    fuerzas = extraer_fuerzas(
        conexion, viga, combos, combo_gravedad="E060-1.4D+1.7L"
    )

    assert set(fuerzas.estaciones_clave) == {
        "I-End", "Cara-I", "Centro", "Cara-J", "J-End",
    }
    assert fuerzas.M_pos_max_tm == pytest.approx(10.0)
    assert fuerzas.estacion_M_pos_m == pytest.approx(3.0)
    assert fuerzas.M_neg_max_tm == pytest.approx(19.0)
    assert fuerzas.estacion_M_neg_m == pytest.approx(6.0)
    assert fuerzas.V_max_t == pytest.approx(20.0)
    assert fuerzas.P_compresion_max_t == pytest.approx(2.8)
    assert fuerzas.V_gravedad_caras == pytest.approx((12.0, 12.0))
    assert fuerzas.V_gravedad_centro == pytest.approx(0.0)

    cara_i = fuerzas.estaciones_clave["Cara-I"]
    assert cara_i.M3_min_tm == pytest.approx(-13.0)
    assert cara_i.M3_max_tm == pytest.approx(-3.0)
    assert cara_i.M_neg_tm == pytest.approx(13.0)
    assert cara_i.M_pos_tm == pytest.approx(0.0)


def test_extraer_fuerzas_sin_combo_gravedad(conexion):
    viga = extraer_vigas(conexion, ConfiguracionDiseno())[0]
    combos = list(COMBOS)[:1]
    fuerzas = extraer_fuerzas(conexion, viga, combos)
    assert fuerzas.V_gravedad_caras == (0.0, 0.0)
    assert any("gravedad" in a for a in fuerzas.advertencias)


def test_sin_resultados(conexion):
    from vigas_e060.etabs.api import ETABSSinResultados

    viga = extraer_vigas(conexion, ConfiguracionDiseno())[0]
    with pytest.raises(ETABSSinResultados):
        extraer_fuerzas(conexion, viga, ["COMBO-INEXISTENTE"])
