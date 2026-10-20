"""
Conversión y normalización de unidades.

El núcleo de cálculo trabaja SIEMPRE en el sistema técnico peruano:

* fuerza .............. kilogramo-fuerza (kgf)  -> se reporta en toneladas-fuerza (t)
* longitud ............ centímetros (cm)
* momento ............. kgf·cm                   -> se reporta en t·m
* esfuerzo ............ kgf/cm²
* área de acero ....... cm²

ETABS se configura a ``kgf_m`` (eUnits = 8) para leer geometría en metros y
fuerzas en kgf.  Aun así se incluye ``normalizar_esfuerzo`` porque algunas
versiones devuelven las propiedades del material en kgf/m² cuando la unidad
presente es kgf_m.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

# ---------------------------------------------------------------------------
# Factores exactos
# ---------------------------------------------------------------------------
KG_POR_TONF: float = 1_000.0
TONF_POR_KG: float = 1.0 / KG_POR_TONF
KGCM_POR_TONFM: float = 100_000.0      # 1 t·m = 1000 kgf × 100 cm
TONFM_POR_KGCM: float = 1.0 / KGCM_POR_TONFM
CM_POR_M: float = 100.0
M_POR_CM: float = 0.01

MPA_POR_KGCM2: float = 0.098_066_5
KGCM2_POR_MPA: float = 1.0 / MPA_POR_KGCM2  # 10.197162...


class ErrorUnidades(ValueError):
    """Conversión o unidad no reconocida."""


# ---------------------------------------------------------------------------
# Conversión de resultados ETABS -> núcleo
# ---------------------------------------------------------------------------
def de_kgf_a_tonf(valor: float) -> float:
    """Convierte kilogramo-fuerza a tonelada-fuerza."""
    return float(valor) / KG_POR_TONF


def de_kgfm_a_tonfm(valor: float) -> float:
    """Convierte kgf·m a t·m."""
    return float(valor) / KG_POR_TONF


def de_kgfcm_a_tonfm(valor: float) -> float:
    """Convierte kgf·cm a t·m."""
    return float(valor) / KGCM_POR_TONFM


def de_tonfm_a_kgfcm(valor: float) -> float:
    """Convierte t·m a kgf·cm (unidad de trabajo de las fórmulas)."""
    return float(valor) * KGCM_POR_TONFM


def de_m_a_cm(valor: float) -> float:
    return float(valor) * CM_POR_M


def de_cm_a_m(valor: float) -> float:
    return float(valor) * M_POR_CM


# ---------------------------------------------------------------------------
# Esfuerzos
# ---------------------------------------------------------------------------
def normalizar_esfuerzo(valor: float, unidad: str = "auto") -> float:
    """
    Devuelve un esfuerzo en kgf/cm².

    Parámetros
    ----------
    valor:
        Número leído de ETABS o del usuario.
    unidad:
        ``"kgf_cm2"``, ``"mpa"``, ``"kgf_m2"`` o ``"auto"``.  El modo automático
        usa órdenes de magnitud: un hormigón estructural tiene entre 15 y
        80 MPa, es decir 150 a 800 kgf/cm².  Para f'c = 210 kgf/cm² ETABS en
        kgf_m devuelve 2 100 000 kgf/m².
    """
    if valor is None:
        raise ErrorUnidades("Esfuerzo vacío.")
    v = float(valor)
    if not isfinite(v) or v <= 0:
        raise ErrorUnidades(f"Esfuerzo inválido: {valor!r}")

    if unidad == "auto":
        if v > 20_000:          # kgf/m² -> kgf/cm²
            return v / 10_000.0
        if v > 60:              # ya está en kgf/cm²
            return v
        if v > 8:               # MPa -> kgf/cm²
            return v * KGCM2_POR_MPA
        raise ErrorUnidades(
            f"No se pudo inferir la unidad del esfuerzo {v!r}. "
            "Indique unidad='kgf_cm2', 'mpa' o 'kgf_m2'."
        )

    if unidad in {"kgf_cm2", "kg/cm2", "kg_cm2"}:
        return v
    if unidad in {"mpa", "MPa"}:
        return v * KGCM2_POR_MPA
    if unidad in {"kgf_m2", "kg/m2", "kg_m2"}:
        return v / 10_000.0
    raise ErrorUnidades(f"Unidad de esfuerzo no soportada: {unidad!r}")


def de_kgcm2_a_mpa(valor: float) -> float:
    return float(valor) * MPA_POR_KGCM2


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------
def fmt(valor: float | int | None, decimales: int = 2, vacio: str = "—") -> str:
    """Formatea un número con separador de miles simple y punto decimal."""
    if valor is None:
        return vacio
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if not isfinite(v):
        return vacio
    texto = f"{v:,.{decimales}f}"
    return texto.replace(",", " ")


def fmt_con_unidad(valor: float, unidad: str, decimales: int = 2) -> str:
    return f"{fmt(valor, decimales)} {unidad}".strip()


@dataclass(frozen=True)
class UnidadesETABS:
    """
    Códigos de ``eUnits`` usados por ETABS.

    Sólo se documentan los habituales; el programa fija ``kgf_m``.  Si el
    usuario tiene una versión que no permite cambiar unidades, la extracción
    aborta con un mensaje explícito antes de entregar resultados erróneos.
    """

    codigo: int
    nombre: str
    longitud_m: float
    fuerza_kgf: float

    def a_metros(self, valor: float) -> float:
        return float(valor) * self.longitud_m

    def a_kgf(self, valor: float) -> float:
        return float(valor) * self.fuerza_kgf

    def a_tonfm(self, valor: float) -> float:
        return self.a_kgf(valor) * self.a_metros(1.0) / KG_POR_TONF


UNIDADES_ETABS: dict[int, UnidadesETABS] = {
    1: UnidadesETABS(1, "lb_in", 0.0254, 0.453_592_37),
    2: UnidadesETABS(2, "lb_ft", 0.3048, 0.453_592_37),
    3: UnidadesETABS(3, "kip_in", 0.0254, 453.592_37),
    4: UnidadesETABS(4, "kip_ft", 0.3048, 453.592_37),
    5: UnidadesETABS(5, "kN_mm", 0.001, 101.971_621),
    6: UnidadesETABS(6, "kN_m", 1.0, 101.971_621),
    7: UnidadesETABS(7, "kgf_mm", 0.001, 1.0),
    8: UnidadesETABS(8, "kgf_m", 1.0, 1.0),
    9: UnidadesETABS(9, "N_mm", 0.001, 0.101_971_621),
    10: UnidadesETABS(10, "N_m", 1.0, 0.101_971_621),
    11: UnidadesETABS(11, "tonf_mm", 0.001, 1_000.0),
    12: UnidadesETABS(12, "tonf_m", 1.0, 1_000.0),
}
