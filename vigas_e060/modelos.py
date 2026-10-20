"""
Modelos de datos del programa.

Todas las magnitudes del núcleo están en kgf, cm, kgf/cm² y t·m.  Los modelos
son deliberadamente simples (dataclasses) para poder serializarlos, probarlos
y reutilizarlos en el generador de memoria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Any, Iterable

from .normativa.e060 import beta1 as _beta1
from .normativa.e060 import rho_balanceado as _rho_balanceado


# ===========================================================================
# Materiales y geometría
# ===========================================================================
@dataclass(frozen=True)
class Materiales:
    """Propiedades de los materiales en kgf/cm²."""

    fc: float = 210.0
    fy: float = 4_200.0
    fyt: float = 4_200.0
    es: float = 2_000_000.0
    gamma_concreto: float = 2.4  # t/m³

    def __post_init__(self) -> None:
        if self.fc < 170:
            raise ValueError("f'c debe ser ≥ 170 kgf/cm² (E.060 4.2.1).")
        if self.fy <= 0 or self.fyt <= 0:
            raise ValueError("fy y fyt deben ser positivos.")
        if self.es <= 0:
            raise ValueError("Es debe ser positivo.")

    @property
    def beta1(self) -> float:
        """Factor β1 del bloque rectangular (E.060 10.2.7.3)."""
        return _beta1(self.fc)

    @property
    def rho_b(self) -> float:
        """Cuantía balanceada (E.060 10.3.2)."""
        return _rho_balanceado(self.fc, self.fy, self.es)

    @property
    def fy_mpa(self) -> float:
        return self.fy * 0.098_066_5


@dataclass(frozen=True)
class GeometriaViga:
    """
    Geometría de una viga rectangular.

    ``L`` es la longitud entre ejes (centro de columna a centro de columna) y
    ``ln`` la luz libre entre caras de apoyo.  ``r`` es el recubrimiento libre
    al estribo, no al centroide de la armadura.
    """

    b: float
    h: float
    L: float
    ln: float
    r: float = 4.0
    diametro_estribo: float = 0.9525      # 3/8"
    diametro_long_estimado: float = 1.905  # 3/4"

    def __post_init__(self) -> None:
        for nombre, valor in (("b", self.b), ("h", self.h), ("L", self.L),
                              ("ln", self.ln), ("r", self.r)):
            if valor <= 0:
                raise ValueError(f"La dimensión {nombre} debe ser positiva.")
        if self.r >= self.h / 2:
            raise ValueError("El recubrimiento es mayor que medio peralte.")
        if self.ln > self.L + 1e-6:
            raise ValueError("La luz libre no puede superar la longitud entre ejes.")

    @property
    def d_estimado(self) -> float:
        """Peralte efectivo supuesto para una capa de acero."""
        return self.h - self.r - self.diametro_estribo - self.diametro_long_estimado / 2

    def d(self, y_cm: float) -> float:
        """Peralte efectivo a partir del centroide de la armadura traccionada."""
        return self.h - y_cm

    @property
    def area_bruta(self) -> float:
        return self.b * self.h


# ===========================================================================
# Varillas
# ===========================================================================
@dataclass(frozen=True)
class Varilla:
    nombre: str
    diametro_cm: float
    area_cm2: float

    @property
    def peso_kg_m(self) -> float:
        # Peso teórico = área (cm²) × densidad (7.85 g/cm³) × 100 cm / 1000
        return self.area_cm2 * 0.785

    def __str__(self) -> str:
        return self.nombre


@dataclass
class CapaVarillas:
    varilla: Varilla
    cantidad: int

    @property
    def area_cm2(self) -> float:
        return self.varilla.area_cm2 * self.cantidad


@dataclass
class SeleccionVarillas:
    """
    Distribución comercial de barras.

    ``y_cm`` es la distancia desde la cara donde se coloca la armadura hasta su
    centroide.  Para acero inferior, ``d = h - y``; para acero superior, el
    peralte efectivo también es ``h - y`` (medido desde la cara superior).
    """

    capas: list[CapaVarillas]
    area_cm2: float
    y_cm: float
    ancho_requerido_cm: float
    separacion_libre_cm: float
    cabe: bool = True
    mensaje: str = ""

    @property
    def cantidad(self) -> int:
        return sum(c.cantidad for c in self.capas)

    @property
    def diametro_max(self) -> float:
        return max((c.varilla.diametro_cm for c in self.capas), default=0.0)

    @property
    def diametro_min(self) -> float:
        return min((c.varilla.diametro_cm for c in self.capas), default=0.0)

    @property
    def etiqueta(self) -> str:
        if not self.capas:
            return "—"
        # Se agrupa por diámetro para informar, p. ej., 3 Φ 3/4"
        grupos: dict[str, int] = {}
        for capa in self.capas:
            grupos[capa.varilla.nombre] = grupos.get(capa.varilla.nombre, 0) + capa.cantidad
        return " + ".join(f"{n} Φ {d}" for d, n in grupos.items())

    @property
    def etiqueta_larga(self) -> None | str:
        if not self.capas:
            return None
        if len(self.capas) == 1:
            return f"{self.capas[0].cantidad} Φ {self.capas[0].varilla.nombre} (1 capa)"
        detalle = " + ".join(
            f"{c.cantidad} Φ {c.varilla.nombre}" for c in self.capas
        )
        return f"{detalle} ({len(self.capas)} capas)"

    def peralte_efectivo(self, h: float) -> float:
        return h - self.y_cm


# ===========================================================================
# Fuerzas extraídas de ETABS
# ===========================================================================
@dataclass
class FuerzaEstacion:
    estacion_m: float
    M3_tm: float
    V2_t: float
    P_t: float
    T_tm: float
    combo: str


@dataclass
class EnvolventeEstacion:
    estacion_m: float
    M3_max_tm: float
    M3_min_tm: float
    V2_max_t: float
    P_min_t: float
    P_max_t: float
    T_max_tm: float
    combo_M3_max: str = ""
    combo_M3_min: str = ""
    combo_V2_max: str = ""
    combo_T_max: str = ""

    @property
    def M_neg_tm(self) -> float:
        """Momento negativo de diseño (valor absoluto)."""
        return max(0.0, -self.M3_min_tm)

    @property
    def M_pos_tm(self) -> float:
        return max(0.0, self.M3_max_tm)


@dataclass
class FuerzasViga:
    combos: list[str] = field(default_factory=list)
    por_combo: dict[str, list[FuerzaEstacion]] = field(default_factory=dict)
    estaciones_clave: dict[str, EnvolventeEstacion] = field(default_factory=dict)
    M_pos_max_tm: float = 0.0
    M_neg_max_tm: float = 0.0
    V_max_t: float = 0.0
    P_compresion_max_t: float = 0.0
    T_max_tm: float = 0.0
    estacion_M_pos_m: float = 0.0
    estacion_M_neg_m: float = 0.0
    estacion_V_max_m: float = 0.0
    combo_M_pos: str = ""
    combo_M_neg: str = ""
    combo_V_max: str = ""
    combo_T_max: str = ""
    V_gravedad_caras: tuple[float, float] = (0.0, 0.0)
    V_gravedad_centro: float = 0.0
    combo_gravedad: str = ""
    advertencias: list[str] = field(default_factory=list)


# ===========================================================================
# Diseño
# ===========================================================================
@dataclass
class Verificacion:
    nombre: str
    valor: str
    limite: str
    cumple: bool
    referencia: str = ""
    observacion: str = ""


@dataclass
class Formula:
    titulo: str
    expresion: str
    sustitucion: str
    resultado: str
    referencia: str = ""


@dataclass
class ResultadoFlexion:
    ubicacion: str
    lado: str                       # "superior" / "inferior"
    Mu_tm: float
    b_cm: float
    h_cm: float
    d_cm: float
    beta1: float
    rho_b: float
    rho_max: float
    As_min_cm2: float
    As_max_cm2: float
    Mu_max_simple_tm: float
    As_req_cm2: float
    As_calculado_cm2: float
    doble: bool
    As_prima_req_cm2: float
    seleccion: SeleccionVarillas | None = None
    seleccion_compresion: SeleccionVarillas | None = None
    d_final_cm: float = 0.0
    a_cm: float = 0.0
    c_cm: float = 0.0
    eps_t: float = 0.0
    phi: float = 0.90
    fs_prima: float = 0.0
    Mn_tm: float = 0.0
    phiMn_tm: float = 0.0
    ratio_As: float = 0.0
    criterio: str = ""
    Mu_original_tm: float = 0.0      # demanda de ETABS cuando se amplió el acero
    motivo_ampliacion: str = ""
    verificaciones: list[Verificacion] = field(default_factory=list)
    formulas: list[Formula] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    @property
    def As_prov_cm2(self) -> float:
        return self.seleccion.area_cm2 if self.seleccion else 0.0

    @property
    def As_prima_prov_cm2(self) -> float:
        return self.seleccion_compresion.area_cm2 if self.seleccion_compresion else 0.0

    @property
    def cumple(self) -> bool:
        return all(v.cumple for v in self.verificaciones)


@dataclass
class ResultadoCortante:
    d_cm: float
    ln_m: float
    Vu_envolvente_t: float
    Mpr_i_tm: float
    Mpr_j_tm: float
    Ve_t: float
    Vg_i_t: float
    Vg_j_t: float
    Vu_i_t: float
    Vu_j_t: float
    Vu_diseno_t: float
    Vc_t: float
    Vc_conf_t: float
    phi: float
    Vs_req_i_t: float
    Vs_req_j_t: float
    s_req_i_cm: float
    s_req_j_cm: float
    s_conf_i_cm: float
    s_conf_j_cm: float
    s_central_cm: float
    s_max_conf_cm: float
    s_max_central_cm: float
    s_av_min_cm: float
    Av_cm2: float
    ramas: int
    estribo: Varilla
    distribucion_i: str = ""
    distribucion_j: str = ""
    distribucion_central: str = ""
    total_estribos: int = 0
    peso_estribos_kg: float = 0.0
    L_conf_m: float = 0.0
    verificaciones: list[Verificacion] = field(default_factory=list)
    formulas: list[Formula] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    @property
    def cumple(self) -> bool:
        return all(v.cumple for v in self.verificaciones)

    @property
    def distribucion_completa(self) -> str:
        """Detalle de estribado de toda la viga en una sola línea."""
        partes = [self.distribucion_i]
        if self.distribucion_central:
            partes.append(f"Resto: {self.distribucion_central}")
        partes.append(self.distribucion_j)
        return " | ".join(p for p in partes if p)


@dataclass
class VigaETABS:
    nombre: str
    etiqueta: str
    piso: str
    eje: str
    seccion: str
    materiales: Materiales
    geometria: GeometriaViga
    punto_i: str = ""
    punto_j: str = ""
    coord_i: tuple[float, float, float] = (0.0, 0.0, 0.0)
    coord_j: tuple[float, float, float] = (0.0, 0.0, 0.0)
    recubrimiento_etabs_cm: float | None = None
    soportes: str = ""
    offset_i_m: float = 0.0
    offset_j_m: float = 0.0
    advertencias: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.etiqueta or self.nombre


@dataclass
class ResultadoViga:
    viga: VigaETABS
    fuerzas: FuerzasViga
    flexion: list[ResultadoFlexion] = field(default_factory=list)
    cortante: ResultadoCortante | None = None
    verificaciones: list[Verificacion] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    def por_ubicacion(self, ubicacion: str, lado: str | None = None) -> ResultadoFlexion | None:
        for r in self.flexion:
            if r.ubicacion == ubicacion and (lado is None or r.lado == lado):
                return r
        return None

    @property
    def cumple(self) -> bool:
        return (
            all(r.cumple for r in self.flexion)
            and (self.cortante is None or self.cortante.cumple)
            and all(v.cumple for v in self.verificaciones)
        )


# ===========================================================================
# Combinaciones
# ===========================================================================
@dataclass(frozen=True)
class ComboRequerida:
    nombre: str
    factores: tuple[tuple[str, float], ...]
    referencia: str

    @property
    def etiqueta(self) -> str:
        partes: list[str] = []
        for caso, factor in self.factores:
            if abs(factor) < 1e-9:
                continue
            signo = "+" if factor >= 0 else "−"
            partes.append(f"{signo} {abs(factor):g}·{caso}")
        texto = " ".join(partes).strip()
        return texto[2:] if texto.startswith("+ ") else texto


@dataclass
class VerificacionCombo:
    requerida: ComboRequerida
    encontrada: str | None
    estado: str              # "coincide", "parcial", "ausente", "no_verificable"
    detalle: str
    factores_encontrados: dict[str, float] = field(default_factory=dict)

    @property
    def cumple(self) -> bool:
        return self.estado == "coincide"


# ===========================================================================
# Metadatos de la memoria
# ===========================================================================
@dataclass
class MetadatosProyecto:
    proyecto: str = "Proyecto estructural"
    ubicacion: str = "Perú"
    ingeniero: str = "Ingeniero estructural"
    cliente: str = ""
    fecha: str = ""
    etabs_version: str = ""
    modelo: str = ""
    ruta_modelo: str = ""
    revision: str = "A"
    observaciones: str = ""

    def como_dict(self) -> dict[str, Any]:
        return {
            "proyecto": self.proyecto,
            "ubicacion": self.ubicacion,
            "ingeniero": self.ingeniero,
            "cliente": self.cliente,
            "fecha": self.fecha,
            "etabs_version": self.etabs_version,
            "modelo": self.modelo,
            "ruta_modelo": self.ruta_modelo,
            "revision": self.revision,
            "observaciones": self.observaciones,
        }


def area_total(selecciones: Iterable[SeleccionVarillas]) -> float:
    return sum(s.area_cm2 for s in selecciones if s)


def cuantia(As_cm2: float, b_cm: float, d_cm: float) -> float:
    if b_cm <= 0 or d_cm <= 0:
        return 0.0
    return As_cm2 / (b_cm * d_cm)


def raiz_fc(fc: float) -> float:
    """Raíz de f'c, usada repetidamente y con protección numérica."""
    return sqrt(max(fc, 1.0))
