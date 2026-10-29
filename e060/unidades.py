"""
Conversión de unidades.

Convención interna del programa (unidades coherentes para el cálculo):
    longitud .......... cm
    fuerza ............ kgf
    momento ........... kgf·cm
    esfuerzo .......... kgf/cm²
    área de acero ..... cm²

Las entradas y salidas "de usuario" usan:
    longitud .......... m  / cm
    fuerza ............ tonf
    momento ........... tonf·m
    esfuerzo .......... kgf/cm²

ETABS trabaja con los sistemas kgf, tonf, N, kN, lb, kip, y con longitudes
m, cm, mm, in, ft. Todo se normaliza a las unidades internas antes de calcular.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Factores de fuerza -> kgf
# ---------------------------------------------------------------------------
_FUERZA_A_KGF = {
    "kgf": 1.0,
    "kg": 1.0,
    "tonf": 1000.0,
    "tnf": 1000.0,
    "N": 1.0 / 9.80665,
    "kN": 1000.0 / 9.80665,
    "lbf": 0.45359237,
    "lb": 0.45359237,
    "kip": 453.59237,
}

# ---------------------------------------------------------------------------
# Factores de longitud -> cm
# ---------------------------------------------------------------------------
_LONGITUD_A_CM = {
    "m": 100.0,
    "cm": 1.0,
    "mm": 0.1,
    "in": 2.54,
    "ft": 30.48,
}


def _norm(u: str) -> str:
    u = (u or "").strip().replace(" ", "").replace("²", "2").replace("^", "")
    return u


def fuerza_a_kgf(valor: float, unidad: str) -> float:
    """Convierte una fuerza (P, V, T-fuerza) a kgf."""
    u = _norm(unidad)
    for clave, factor in _FUERZA_A_KGF.items():
        if u.lower() == clave.lower():
            return valor * factor
    raise ValueError(f"Unidad de fuerza no reconocida: {unidad!r}")


def longitud_a_cm(valor: float, unidad: str) -> float:
    """Convierte una longitud (L, b, h, recubrimiento) a cm."""
    u = _norm(unidad)
    for clave, factor in _LONGITUD_A_CM.items():
        if u.lower() == clave.lower():
            return valor * factor
    raise ValueError(f"Unidad de longitud no reconocida: {unidad!r}")


def momento_a_kgfcm(valor: float, unidad_fuerza: str, unidad_longitud: str) -> float:
    """Convierte un momento (M, Torsor) a kgf·cm."""
    return fuerza_a_kgf(valor, unidad_fuerza) * longitud_a_cm(1.0, unidad_longitud)


def kgfcm_a_tonfm(valor: float) -> float:
    return valor / 1.0e5


def tonfm_a_kgfcm(valor: float) -> float:
    return valor * 1.0e5


def kgf_a_tonf(valor: float) -> float:
    return valor / 1000.0


def tonf_a_kgf(valor: float) -> float:
    return valor * 1000.0


def cm2_a_m2(valor: float) -> float:
    return valor / 1.0e4


# ---------------------------------------------------------------------------
# Sistemas de unidades presentados por ETABS (menú Options > Display)
# Formato típico: "kN_m_C" (fuerza_longitud_temperatura)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SistemaUnidades:
    nombre: str
    fuerza: str
    longitud: str

    @property
    def etiqueta(self) -> str:
        return f"{self.fuerza}-{self.longitud}"

    def fuerza_a_kgf(self, v: float) -> float:
        return fuerza_a_kgf(v, self.fuerza)

    def longitud_a_cm(self, v: float) -> float:
        return longitud_a_cm(v, self.longitud)

    def momento_a_kgfcm(self, v: float) -> float:
        return fuerza_a_kgf(v, self.fuerza) * longitud_a_cm(1.0, self.longitud)

    def momento_a_tonfm(self, v: float) -> float:
        return kgfcm_a_tonfm(self.momento_a_kgfcm(v))

    def fuerza_a_tonf(self, v: float) -> float:
        return kgf_a_tonf(self.fuerza_a_kgf(v))

    def area_a_cm2(self, v: float) -> float:
        return v * (self.longitud_a_cm(1.0) ** 2)


SISTEMAS_ETABS = {
    "kgf_m_C": SistemaUnidades("kgf_m_C", "kgf", "m"),
    "kgf_cm_C": SistemaUnidades("kgf_cm_C", "kgf", "cm"),
    "kgf_mm_C": SistemaUnidades("kgf_mm_C", "kgf", "mm"),
    "tonf_m_C": SistemaUnidades("tonf_m_C", "tonf", "m"),
    "tonf_cm_C": SistemaUnidades("tonf_cm_C", "tonf", "cm"),
    "tonf_mm_C": SistemaUnidades("tonf_mm_C", "tonf", "mm"),
    "N_m_C": SistemaUnidades("N_m_C", "N", "m"),
    "N_mm_C": SistemaUnidades("N_mm_C", "N", "mm"),
    "kN_m_C": SistemaUnidades("kN_m_C", "kN", "m"),
    "kN_cm_C": SistemaUnidades("kN_cm_C", "kN", "cm"),
    "kN_mm_C": SistemaUnidades("kN_mm_C", "kN", "mm"),
    "lb_ft_F": SistemaUnidades("lb_ft_F", "lb", "ft"),
    "lb_in_F": SistemaUnidades("lb_in_F", "lb", "in"),
    "kip_ft_F": SistemaUnidades("kip_ft_F", "kip", "ft"),
    "kip_in_F": SistemaUnidades("kip_in_F", "kip", "in"),
}


def sistema_unidades(nombre: str) -> SistemaUnidades:
    """
    Devuelve el sistema de unidades pedido. Acepta nombres dados por el API de
    ETABS ('kN_m_C'), versiones cortas ('kN-m', 'kNm', 'tonf-m') y cadenas
    compuestas generadas por las tablas exportadas.
    """
    if not nombre:
        return SISTEMAS_ETABS["tonf_m_C"]
    clave = _norm(nombre)
    if clave in SISTEMAS_ETABS:
        return SISTEMAS_ETABS[clave]
    partes = [p for p in re.split(r"[_/\-]", clave) if p]
    if len(partes) >= 2:
        f, l = partes[0], partes[1]
        for cand in (
            f"{f}_{l}_C",
            f"{f}_{l}_F",
        ):
            if cand in SISTEMAS_ETABS:
                return SISTEMAS_ETABS[cand]
        # combinaciones no tabuladas (p. ej. "kN-m" o "Tonf-cm")
        f_norm = next((k for k in _FUERZA_A_KGF if k.lower() == f.lower()), None)
        l_norm = next((k for k in _LONGITUD_A_CM if k.lower() == l.lower()), None)
        if f_norm and l_norm:
            return SistemaUnidades(f"{f_norm}_{l_norm}", f_norm, l_norm)
    return SISTEMAS_ETABS["tonf_m_C"]


# ---------------------------------------------------------------------------
# Unidades típicas que muestra ETABS al leer diseños de sección
# ---------------------------------------------------------------------------
def normalizar_unidad_tabla(texto: str) -> str:
    """
    Las tablas de ETABS agregan la unidad al encabezado, por ejemplo
    'P (tonf)', 'M3 (tonf-m)'. Esta función extrae solo la unidad.
    """
    if not texto:
        return ""
    t = texto.replace("(", " ").replace(")", " ").replace("[", " ").replace("]", " ")
    partes = t.split()
    for p in reversed(partes):
        p = p.strip(",;")
        if any(p.lower() == k.lower() for k in list(_FUERZA_A_KGF) + list(_LONGITUD_A_CM)):
            return p
        if p.lower() in ("tonf-m", "tonf-cm", "kgf-m", "kgf-cm", "kn-m", "kn-mm", "lbf-ft"):
            return p
    return partes[-1] if partes else ""
