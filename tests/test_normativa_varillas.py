"""Pruebas de las fórmulas de la E.060 y del catálogo de varillas."""

from __future__ import annotations

import math

import pytest

from vigas_e060.calculo.varillas import (
    VARILLAS_LONGITUDINALES,
    construir_seleccion,
    peso_estribos_kg,
    seleccionar_estribo,
    seleccionar_varillas,
)
from vigas_e060.normativa import e060


# ---------------------------------------------------------------------------
# Materiales y flexión
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("fc", "esperado"),
    [(210, 0.85), (280, 0.85), (350, 0.80), (420, 0.75), (560, 0.65)],
)
def test_beta1(fc, esperado):
    assert e060.beta1(fc) == pytest.approx(esperado, abs=1e-9)


def test_rho_balanceado_valor_conocido():
    # f'c = 210, fy = 4200: ρb ≈ 0.02125
    assert e060.rho_balanceado(210, 4200) == pytest.approx(0.02125, abs=5e-5)


def test_as_minimo():
    esperado = 0.7 * math.sqrt(210) / 4200 * 25 * 44
    assert e060.as_minimo(210, 4200, 25, 44) == pytest.approx(esperado)


def test_limites_acero_gobierna_tension_controlada():
    lim = e060.limites_acero(210, 4200, 25, 44)
    assert lim.As_max_cm2 == pytest.approx(lim.As_tension_controlada_cm2)
    assert lim.criterio.startswith("εt = 0.005")
    assert lim.Mu_max_tm > 0


def test_phi_flexion_interpolacion():
    assert e060.phi_flexion(0.005) == pytest.approx(0.90)
    assert e060.phi_flexion(0.001) == pytest.approx(0.65)
    assert e060.phi_flexion(0.0035) == pytest.approx(0.775)


def test_as_requerido_simple_resuelve_ecuacion():
    Mu, fc, fy, b, d = 15.0, 210, 4200, 25, 44
    As, disc = e060.as_requerido_simple(Mu, fc, fy, b, d)
    assert disc > 0
    a = As * fy / (0.85 * fc * b)
    Mn = As * fy * (d - a / 2) / 100_000
    assert 0.90 * Mn == pytest.approx(Mu, rel=1e-6)


def test_as_requerido_simple_sin_solucion():
    As, disc = e060.as_requerido_simple(500, 210, 4200, 25, 44)
    assert disc < 0
    assert math.isnan(As)


def test_momento_nominal_simple():
    b, d = 25, 44
    As = 3 * 2.85  # 3 Φ 3/4"
    cap = e060.momento_nominal(As, 0, b, d, 0, 210, 4200)
    a = As * 4200 / (0.85 * 210 * b)
    assert cap.a_cm == pytest.approx(a)
    assert cap.Mn_tm == pytest.approx(As * 4200 * (d - a / 2) / 100_000)
    assert cap.phi == pytest.approx(0.90)
    assert 0.002 < cap.eps_t


def test_momento_nominal_con_compresion():
    cap = e060.momento_nominal(12.0, 3.0, 30, 54, 6.0, 280, 4200)
    assert cap.Mn_tm > 0
    assert cap.a_cm > 0
    assert cap.phi >= 0.65


# ---------------------------------------------------------------------------
# Cortante
# ---------------------------------------------------------------------------
def test_resistencias_cortante():
    Vc = e060.vc_concreto(210, 25, 44)
    assert Vc == pytest.approx(0.53 * math.sqrt(210) * 25 * 44)
    Vs = e060.vs_maximo(210, 25, 44)
    assert Vs == pytest.approx(2.1 * math.sqrt(210) * 25 * 44)


def test_av_minimo_por_s():
    esperado = max(0.20 * math.sqrt(210) * 25 / 4200, 3.5 * 25 / 4200)
    assert e060.av_minimo_por_s(210, 25, 4200) == pytest.approx(esperado)


def test_espaciamientos():
    assert e060.s_maximo_general(44) == pytest.approx(22)
    assert e060.s_maximo_general(200) == pytest.approx(60)
    assert e060.s_maximo_confinamiento(44, 1.27, 0.9525) == pytest.approx(10.16)
    assert e060.longitud_confinamiento(50) == pytest.approx(100)


def test_vu_por_capacidad():
    assert e060.vu_por_capacidad(20, 18, 5.4) == pytest.approx(38 / 5.4)


# ---------------------------------------------------------------------------
# Varillas
# ---------------------------------------------------------------------------
def test_construir_seleccion_una_capa():
    varilla = next(v for v in VARILLAS_LONGITUDINALES if v.nombre == '3/4"')
    sel = construir_seleccion(varilla, 3, 25, 50, 4.0, 0.9525)
    assert sel.cabe
    assert sel.area_cm2 == pytest.approx(8.55)
    assert sel.y_cm == pytest.approx(4.0 + 0.9525 + 1.905 / 2)
    assert sel.cantidad == 3
    assert '3 Φ 3/4"' in sel.etiqueta


def test_seleccionar_varillas_no_cabe():
    sel = seleccionar_varillas(80, 20, 40, 4.0, 0.9525, max_capas=1)
    assert sel is None or not sel.cabe or sel.area_cm2 >= 80


def test_peso_estribos():
    from vigas_e060.calculo.varillas import buscar_varilla

    est = buscar_varilla('3/8"', estribo=True)
    peso = peso_estribos_kg(10, 25, 50, 4.0, 0.9525, est)
    assert peso > 0


def test_seleccionar_estribo():
    est, ramas = seleccionar_estribo('3/8"', 1.905, 25, 4.0)
    assert ramas >= 2
    assert est.diametro_cm >= 0.9


def test_momento_nominal_compresion_mayor_que_traccion():
    """Si As' > As, parte del acero superior trabaja en tracción.

    Es el caso de Mpr en la dirección opuesta de una viga con armadura
    superior muy superior a la inferior.  El equilibrio debe resolverse sin
    devolver Mn = 0.
    """
    cap = e060.momento_nominal(5.08, 9.90, 25.0, 44.41, 7.38, 210.0, 4200.0)
    assert cap.Mn_tm > 0.0
    assert cap.Mn_tm == pytest.approx(9.6, abs=0.8)
    assert cap.eps_t > 0.0
    assert cap.fs_prima_kgcm2 < 0.0  # el acero "de compresión" está en tracción
