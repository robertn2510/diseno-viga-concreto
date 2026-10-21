"""Pruebas de conversión de unidades y del envoltorio de conexión."""

from __future__ import annotations

import pytest
from conftest import hacer_conexion

from vigas_e060.unidades import UNIDADES_ETABS, normalizar_esfuerzo


def test_normalizar_esfuerzo_auto():
    assert normalizar_esfuerzo(2_100_000) == pytest.approx(210)
    assert normalizar_esfuerzo(210) == pytest.approx(210)
    assert normalizar_esfuerzo(21) == pytest.approx(214.14, rel=1e-3)
    with pytest.raises(Exception):
        normalizar_esfuerzo(0)


def test_unidades_kgf_m():
    u = UNIDADES_ETABS[8]
    assert u.nombre == "kgf_m"
    assert u.a_metros(1.0) == pytest.approx(1.0)
    assert u.a_kgf(1_000.0) == pytest.approx(1_000.0)
    assert u.a_tonfm(1_000.0) == pytest.approx(1.0)   # 1000 kgf·m = 1 t·m


def test_conexion_convierte(conexion):
    assert conexion.a_m(3.0) == pytest.approx(3.0)
    assert conexion.a_t(14_000.0) == pytest.approx(14.0)
    assert conexion.a_tm(-18_000.0) == pytest.approx(-18.0)
    assert conexion.a_kgcm2(2_100_000.0) == pytest.approx(210.0)


def test_conexion_cierra(conexion):
    conexion.cerrar()
    assert conexion._unidades_restauradas is True


def test_conexion_simulada_info():
    c = hacer_conexion()
    assert c.info.version == "23.0.0"
    assert c.info.modelo == "demo.edb"
