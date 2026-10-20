"""Pruebas del diseño a flexión y cortante."""

from __future__ import annotations

import math

import pytest

from vigas_e060.calculo.diseno import disenar_viga
from vigas_e060.calculo.flexion import disenar_flexion
from vigas_e060.config import ConfiguracionDiseno
from vigas_e060.demo import datos_demo
from vigas_e060.modelos import GeometriaViga, Materiales


def _geom(b=25, h=50, L=6.0, ln=5.4):
    return GeometriaViga(b=b, h=h, L=L, ln=ln, r=4.0)


def test_flexion_simple():
    cfg = ConfiguracionDiseno()
    geom = _geom()
    mat = Materiales(fc=210, fy=4200)
    res = disenar_flexion(15.0, geom, mat, "inferior", cfg, "Centro")
    assert not res.doble
    assert res.seleccion is not None
    assert res.As_prov_cm2 >= res.As_req_cm2 - 1e-9
    assert res.As_prov_cm2 >= res.As_min_cm2 - 1e-9
    assert res.phiMn_tm >= res.Mu_tm - 1e-6
    assert res.eps_t >= 0.004
    assert res.cumple
    assert res.d_cm == pytest.approx(geom.h - res.seleccion.y_cm)


def test_flexion_acero_minimo():
    cfg = ConfiguracionDiseno()
    res = disenar_flexion(0.0, _geom(), Materiales(), "superior", cfg, "Centro")
    assert res.As_req_cm2 >= res.As_min_cm2 - 1e-9
    assert res.seleccion is not None
    assert res.cumple


def test_flexion_doble():
    cfg = ConfiguracionDiseno()
    geom = _geom(b=30, h=60, L=7.5, ln=6.9)
    mat = Materiales(fc=280, fy=4200)
    res = disenar_flexion(55.0, geom, mat, "superior", cfg, "Apoyo")
    assert res.doble
    assert res.seleccion_compresion is not None
    assert res.As_prima_prov_cm2 > 0
    assert res.phiMn_tm >= res.Mu_tm - 1e-6
    assert res.As_prov_cm2 / (geom.b * res.d_cm) <= 0.025 + 1e-6


def test_flexion_fc280_beta1():
    res = disenar_flexion(
        20.0, _geom(), Materiales(fc=280, fy=4200), "inferior",
        ConfiguracionDiseno(), "Centro",
    )
    assert res.beta1 == pytest.approx(0.85)
    assert res.cumple


def test_diseno_viga_completo():
    cfg = ConfiguracionDiseno()
    vigas, fuerzas, _ = datos_demo()
    for v in vigas:
        r = disenar_viga(v, fuerzas[v.nombre], cfg)
        assert r.cumple, (v.id, [x.nombre for x in r.verificaciones if not x.cumple])
        assert r.cortante is not None
        c = r.cortante
        assert c.Vu_diseno_t >= c.Ve_t
        assert c.s_conf_i_cm <= c.s_max_conf_cm + 1e-6
        assert c.s_central_cm <= c.s_max_central_cm + 1e-6
        av_min = max(0.20 * (v.materiales.fc ** 0.5) * v.geometria.b / 4200,
                     3.5 * v.geometria.b / 4200)
        assert c.Av_cm2 / c.s_conf_i_cm >= av_min - 1e-9
        assert c.total_estribos > 0
        assert c.peso_estribos_kg > 0


def test_continuidad_21523():
    """Todas las vigas del demo deben cumplir Mn+ ≥ Mn−/2 tras la ampliación."""
    cfg = ConfiguracionDiseno()
    vigas, fuerzas, _ = datos_demo()
    for v in vigas:
        r = disenar_viga(v, fuerzas[v.nombre], cfg)
        for apoyo in ("Apoyo izquierdo (cara)", "Apoyo derecho (cara)"):
            sup = r.por_ubicacion(apoyo, "superior")
            inf = r.por_ubicacion(apoyo, "inferior")
            assert inf.Mn_tm + 1e-6 >= sup.Mn_tm / 2.0


def test_vc_cero_en_confinamiento_por_sismo():
    """E.060 21.5.4.2: Vc = 0 si el sismo domina el cortante y P es baja."""
    cfg = ConfiguracionDiseno()
    vigas, fuerzas, _ = datos_demo()
    v = vigas[0]
    f = fuerzas[v.nombre]
    f.V_gravedad_caras = (0.0, 0.0)
    f.V_gravedad_centro = 0.0
    f.V_max_t = 3.0
    for est in f.estaciones_clave.values():
        est.V2_max_t = 3.0
    r = disenar_viga(v, f, cfg)
    c = r.cortante
    assert c is not None
    assert c.Ve_t / c.Vu_i_t >= 0.5
    assert c.Vc_conf_t == pytest.approx(0.0)
    assert c.Vc_t > 0


def test_vs_requerido_descuenta_vc_en_toneladas():
    """Vs,req = Vu/φ − Vc (ambos en toneladas); no debe restar kgf como t."""
    cfg = ConfiguracionDiseno()
    vigas, fuerzas, _ = datos_demo()
    v = vigas[0]
    c = disenar_viga(v, fuerzas[v.nombre], cfg).cortante
    assert c.Vs_req_i_t == pytest.approx(
        c.Vu_i_t / c.phi - c.Vc_conf_t, abs=1e-6
    )
    assert c.Vs_req_i_t < c.Vu_i_t / c.phi


def test_distribucion_estribos_orientacion():
    cfg = ConfiguracionDiseno()
    vigas, fuerzas, _ = datos_demo()
    c = disenar_viga(vigas[0], fuerzas[vigas[0].nombre], cfg).cortante
    assert c is not None
    assert c.distribucion_i.startswith("1 @ 0.05")
    assert c.distribucion_j.endswith("1 @ 0.05 m")
    assert c.distribucion_completa.count("|") == 2
    assert "Resto:" in c.distribucion_completa


def test_seccion_insuficiente_no_devuelve_nan():
    """Una demanda imposible debe reportarse como NO CUMPLE, sin nan."""
    cfg = ConfiguracionDiseno()
    geom = _geom(b=20, h=30, ln=2.5)
    mat = Materiales(fc=210, fy=4200)
    res = disenar_flexion(150.0, geom, mat, "inferior", cfg, "Centro")
    assert res.seleccion is not None
    assert not res.cumple
    assert math.isfinite(res.As_req_cm2)
    assert math.isfinite(res.ratio_As)
    assert res.phiMn_tm < res.Mu_tm
    assert res.As_prov_cm2 / (geom.b * res.d_cm) <= 0.025 + 1e-6
