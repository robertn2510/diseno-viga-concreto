"""Pruebas de generación y verificación de combinaciones E.060."""

from __future__ import annotations

from conftest import COMBOS

from vigas_e060.etabs.combos import (
    combo_gravedad,
    detectar_casos_carga,
    generar_combos_requeridas,
    leer_combos_diseno_concreto,
    leer_combos_existentes,
    mapas_combo_extraccion,
    verificar_combinaciones,
)


def test_generar_combos_usuario():
    combos = generar_combos_requeridas("DEAD", "LIVE", ["SISMO"], 1.25)
    nombres = [c.nombre for c in combos]
    assert nombres[0] == "E060-1.4D+1.7L"
    assert len(combos) == 5
    assert any("1.25" in n and "+1.25SISMO" in n for n in nombres)
    assert any("0.9D" in n for n in nombres)
    # No se duplican firmas de factores
    firmas = {tuple(sorted(c.factores)) for c in combos}
    assert len(firmas) == len(combos)


def test_generar_combos_e060_2009():
    combos = generar_combos_requeridas("DEAD", "LIVE", ["SISMO"], 1.0)
    nombres = [c.nombre for c in combos]
    assert "E060-1.25(D+L)+1SISMO" in nombres
    assert "E060-0.9D-1SISMO" in nombres


def test_combo_gravedad():
    combos = generar_combos_requeridas("DEAD", "LIVE", ["SISMO"], 1.25)
    assert combo_gravedad(combos).nombre == "E060-1.4D+1.7L"
    assert combo_gravedad([]) is None


def test_leer_y_verificar(conexion):
    existentes = leer_combos_existentes(conexion.sap_model)
    assert set(existentes) == set(COMBOS)
    req = generar_combos_requeridas("DEAD", "LIVE", ["SISMO"], 1.25)
    ver = verificar_combinaciones(conexion.sap_model, req)
    assert all(v.estado == "coincide" for v in ver), [v.estado for v in ver]
    mapa = mapas_combo_extraccion(req, ver)
    assert set(mapa) == {c.nombre for c in req}


def test_detectar_casos(conexion):
    casos = detectar_casos_carga(conexion.sap_model)
    assert casos.muerta == "DEAD"
    assert casos.viva == "LIVE"
    assert casos.sismo == ["SISMO"]
    assert casos.advertencias == []


def test_leer_combos_diseno(conexion):
    assert set(leer_combos_diseno_concreto(conexion.sap_model)) == set(COMBOS)


def test_combos_faltantes(conexion):
    req = generar_combos_requeridas("DEAD", "LIVE", ["SISMO X"], 1.25)
    ver = verificar_combinaciones(conexion.sap_model, req)
    estados = {v.requerida.nombre: v.estado for v in ver}
    assert estados["E060-1.4D+1.7L"] == "coincide"
    for nombre, estado in estados.items():
        if "SISMO" in nombre:
            assert estado in {"ausente", "parcial"}
    # Las combinaciones parciales no se usan para extraer fuerzas.
    mapa = mapas_combo_extraccion(req, ver)
    assert set(mapa) == {"E060-1.4D+1.7L"}


def test_factores_distintos(conexion):
    req = generar_combos_requeridas("DEAD", "LIVE", ["SISMO"], 1.0)
    ver = verificar_combinaciones(conexion.sap_model, req)
    # El combo 1.4D+1.7L coincide; los sísmicos con 1.0 no existen como tales.
    estados = {v.requerida.nombre: v.estado for v in ver}
    assert estados["E060-1.4D+1.7L"] == "coincide"
    assert estados["E060-1.25(D+L)+1SISMO"] in {"parcial", "ausente"}
