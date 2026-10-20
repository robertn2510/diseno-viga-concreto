"""
Implementación de las disposiciones de la Norma Técnica E.060 "Concreto
Armado" del Reglamento Nacional de Edificaciones del Perú (D.S. N° 010-2009).

Todas las funciones reciben y devuelven unidades del sistema técnico:

* longitudes ........ cm
* fuerzas ........... kgf
* momentos .......... kgf·cm (salvo los sufijos ``_tm``)
* esfuerzos ......... kgf/cm²

Cada función indica el artículo aplicado.  Las referencias corresponden a la
edición 2009 de la E.060, concordante con el ACI 318-05.  Para los pórticos
especiales resistentes a momentos se usa el capítulo 21, artículos 21.5.x
(vigas de pórticos y sistemas duales tipo II), que es el caso habitual en
edificación peruana.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

# ---------------------------------------------------------------------------
# Constantes de la norma
# ---------------------------------------------------------------------------
ECU: float = 0.003                 # deformación máxima del concreto (10.2.3)
ES_ACERO: float = 2_000_000.0      # kgf/cm² (10.2.4)
PHI_FLEXION: float = 0.90          # 9.3.2.1
PHI_CORTANTE: float = 0.85         # 9.3.2.3
RHO_MAX_SISMICA: float = 0.025     # 21.5.2.2
DEF_TENSION_CONTROLADA: float = 0.005
DEF_MIN_DUCTIL: float = 0.004      # 10.3.5
C_TENSION_CONTROLADA: float = 0.375  # c/d para εt = 0.005 con εcu = 0.003


# ---------------------------------------------------------------------------
# Materiales
# ---------------------------------------------------------------------------
def beta1(fc: float) -> float:
    """
    Factor β1 del bloque rectangular equivalente de esfuerzos.

    E.060 10.2.7.3:
        β1 = 0.85                         si f'c ≤ 280 kgf/cm²
        β1 = 0.85 - 0.05(f'c - 280)/70    si f'c > 280 kgf/cm²
        β1 ≥ 0.65
    """
    if fc <= 280.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc - 280.0) / 70.0)


def rho_balanceado(fc: float, fy: float, es: float = ES_ACERO) -> float:
    """
    Cuantía balanceada de una sección rectangular.

    E.060 10.3.2 / apéndice B:
        ρb = 0.85·β1·(f'c/fy)·(εcu/(εcu + fy/Es))
    """
    if fy <= 0 or es <= 0:
        raise ValueError("fy y Es deben ser positivos.")
    return 0.85 * beta1(fc) * (fc / fy) * (ECU / (ECU + fy / es))


def cuantia_minima(fc: float, fy: float) -> float:
    """
    Cuantía mínima a flexión.

    E.060 10.5.1 (edición 2009, sistema técnico):
        As,min = 0.7·√(f'c)/fy · b·d
    """
    return 0.7 * sqrt(max(fc, 1.0)) / fy


def as_minimo(fc: float, fy: float, b: float, d: float) -> float:
    """Área mínima de acero en tracción (E.060 10.5.1), en cm²."""
    return cuantia_minima(fc, fy) * b * d


# ---------------------------------------------------------------------------
# Límites de acero
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LimitesAcero:
    rho_b: float
    rho_max: float
    As_max_cm2: float
    criterio: str
    As_tension_controlada_cm2: float
    As_rho_b_cm2: float
    As_rho_abs_cm2: float
    a_max_cm: float
    c_max_cm: float
    Mn_max_kgcm: float
    Mu_max_tm: float


def limites_acero(
    fc: float,
    fy: float,
    b: float,
    d: float,
    fraccion_rho_b: float = 0.75,
    rho_max_abs: float = RHO_MAX_SISMICA,
    es: float = ES_ACERO,
) -> LimitesAcero:
    """
    Límites de armadura longitudinal para una viga dúctil.

    Se comparan tres criterios y gobierna el menor:

    1. Fracción de la cuantía balanceada: 0.75ρb (o 0.50ρb), criterio clásico
       de ductilidad y requisito del usuario.
    2. Sección controlada por tracción con εt = 0.005, para que φ = 0.90 sea
       válido según E.060 9.3.2.1.  c = 0.375d, a = β1·c.
    3. Cuantía máxima absoluta ρ ≤ 0.025 (E.060 21.5.2.2, vigas de pórticos
       especiales y duales tipo II).

    El momento máximo se calcula con el bloque rectangular:
        Mn = As·fy·(d - a/2),  a = As·fy/(0.85·f'c·b)
    """
    if not 0.0 < fraccion_rho_b <= 1.0:
        raise ValueError("fraccion_rho_b debe estar entre 0 y 1.")
    b1 = beta1(fc)
    rb = rho_balanceado(fc, fy, es)

    As_rho_b = fraccion_rho_b * rb * b * d
    As_rho_abs = rho_max_abs * b * d

    c_tc = C_TENSION_CONTROLADA * d
    a_tc = b1 * c_tc
    As_tc = 0.85 * fc * b * a_tc / fy

    candidatos = [
        (As_rho_b, f"{fraccion_rho_b:.2f}·ρb"),
        (As_tc, "εt = 0.005 (φ = 0.90)"),
        (As_rho_abs, f"ρ ≤ {rho_max_abs:.3f}"),
    ]
    As_max, criterio = min(candidatos, key=lambda par: par[0])

    a_max = As_max * fy / (0.85 * fc * b)
    c_max = a_max / b1
    Mn_max = As_max * fy * (d - a_max / 2.0)

    return LimitesAcero(
        rho_b=rb,
        rho_max=As_max / (b * d),
        As_max_cm2=As_max,
        criterio=criterio,
        As_tension_controlada_cm2=As_tc,
        As_rho_b_cm2=As_rho_b,
        As_rho_abs_cm2=As_rho_abs,
        a_max_cm=a_max,
        c_max_cm=c_max,
        Mn_max_kgcm=Mn_max,
        Mu_max_tm=PHI_FLEXION * Mn_max / 100_000.0,
    )


# ---------------------------------------------------------------------------
# Flexión
# ---------------------------------------------------------------------------
def phi_flexion(eps_t: float, phi_compresion: float = 0.65) -> float:
    """
    Factor de reducción φ para flexión según la deformación de tracción.

    E.060 9.3.2.2 (elementos con estribos):
        εt ≥ 0.005 ........................ φ = 0.90
        εt ≤ 0.002 ........................ φ = 0.65
        0.002 < εt < 0.005 ................ interpolación lineal

    Para vigas se usa φ = 0.90 cuando la sección es controlada por tracción.
    """
    if eps_t >= DEF_TENSION_CONTROLADA:
        return PHI_FLEXION
    if eps_t <= 0.002:
        return phi_compresion
    return phi_compresion + (PHI_FLEXION - phi_compresion) * (eps_t - 0.002) / 0.003


def as_requerido_simple(Mu_tm: float, fc: float, fy: float, b: float, d: float,
                        phi: float = PHI_FLEXION) -> tuple[float, float]:
    """
    Acero requerido en sección simplemente reforzada resolviendo:

        Mu = φ·As·fy·(d - a/2),   a = As·fy/(0.85·f'c·b)

    Devuelve ``(As, discriminante)`` en cm².  Si el discriminante es negativo
    la sección no puede resistir Mu con armadura simple dentro del rango
    físicamente válido y se requiere doble refuerzo.

    Referencia: E.060 10.2.7 (bloque rectangular) y 10.3.1 (resistencia a
    flexión).
    """
    Mu_kgcm = max(0.0, Mu_tm) * 100_000.0
    if Mu_kgcm <= 0.0:
        return 0.0, 0.0

    K = Mu_kgcm / phi
    C = fy * fy / (2.0 * 0.85 * fc * b)
    B = fy * d
    disc = B * B - 4.0 * C * K
    if disc < 0.0:
        return float("nan"), disc
    As = (B - sqrt(disc)) / (2.0 * C)
    return max(0.0, As), disc


@dataclass(frozen=True)
class MomentoNominal:
    Mn_kgcm: float
    Mn_tm: float
    a_cm: float
    c_cm: float
    eps_t: float
    fs_prima_kgcm2: float
    phi: float
    phiMn_tm: float


def momento_nominal(
    As_t_cm2: float,
    As_c_cm2: float,
    b: float,
    d_t: float,
    d_c: float,
    fc: float,
    fy: float,
    es: float = ES_ACERO,
    b1: float | None = None,
) -> MomentoNominal:
    """
    Momento nominal resistente de una sección rectangular con armadura a
    tracción ``As_t`` y, opcionalmente, armadura a compresión ``As_c``.

    Se resuelve el equilibrio y la compatibilidad de deformaciones:

        T  = As_t·fy
        Cc = 0.85·f'c·b·a
        Cs = As_c·f's,  f's = Es·0.003·(c - d')/c ≤ fy
        T  = Cc + Cs
        Mn = Cc·(d - a/2) + Cs·(d - d')

    ``d_t`` y ``d_c`` se miden desde la fibra extrema comprimida.  Cuando la
    armadura de compresión no fluye se usa su esfuerzo real (hipótesis de
    Bernoulli, E.060 10.2.2).  El factor φ se obtiene de la deformación εt de
    la armadura traccionada (E.060 9.3.2.2).

    Devuelve momentos en kgf·cm y t·m.
    """
    if As_t_cm2 <= 0:
        return MomentoNominal(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, PHI_FLEXION, 0.0)

    b1 = beta1(fc) if b1 is None else b1
    As_c = max(0.0, As_c_cm2)
    d_c = min(max(d_c, 1e-6), d_t - 1e-6)

    # Equilibrio de fuerzas con compatibilidad de deformaciones.
    #
    #   F(c) = Cc(c) + Cs(c) − T(c)
    #
    # donde Cc = 0.85·f'c·b·β1·c, Cs = As'·f's y T = As·fs.  Los esfuerzos del
    # acero se limitan a ±fy.  La función F es monótona creciente en c, por lo
    # que se resuelve por bisección; así se cubre también el caso en que la
    # armadura de compresión no fluye o queda en tracción (c < d'), que ocurre
    # al calcular Mpr en la dirección opuesta de una viga con armadura superior
    # mucho mayor que la inferior.
    def _fs(y: float, c: float) -> float:
        eps = ECU * (c - y) / c
        return max(-fy, min(fy, es * eps))

    def _equilibrio(c: float) -> float:
        cc = 0.85 * fc * b * b1 * c
        cs = As_c * _fs(d_c, c) if As_c > 0 else 0.0
        ft = -As_t_cm2 * _fs(d_t, c)
        return cc + cs - ft

    c_lo, c_hi = 1e-6, d_t
    if _equilibrio(c_hi) <= 0.0:
        c = c_hi
    else:
        for _ in range(80):
            c = 0.5 * (c_lo + c_hi)
            if _equilibrio(c) > 0.0:
                c_hi = c
            else:
                c_lo = c
            if c_hi - c_lo <= 1e-9 * max(d_t, 1.0):
                break
        c = 0.5 * (c_lo + c_hi)

    a = b1 * c
    Cc = 0.85 * fc * b * a
    fs_c = _fs(d_c, c) if As_c > 0 else 0.0
    Cs = As_c * fs_c
    Mn = Cc * (d_t - a / 2.0) + Cs * (d_t - d_c)
    eps_t = ECU * (d_t - c) / c
    phi = phi_flexion(eps_t)
    return MomentoNominal(
        Mn_kgcm=Mn,
        Mn_tm=Mn / 100_000.0,
        a_cm=a,
        c_cm=c,
        eps_t=eps_t,
        fs_prima_kgcm2=fs_c,
        phi=phi,
        phiMn_tm=phi * Mn / 100_000.0,
    )


# ---------------------------------------------------------------------------
# Cortante
# ---------------------------------------------------------------------------
def vc_concreto(fc: float, b: float, d: float) -> float:
    """
    Resistencia nominal del concreto al cortante, en kgf.

    E.060 11.3.1.1 (elementos sin fuerza axial significativa):
        Vc = 0.53·√(f'c)·b·d      [kgf/cm², cm]
    """
    return 0.53 * sqrt(max(fc, 1.0)) * b * d


def vs_maximo(fc: float, b: float, d: float) -> float:
    """
    Resistencia máxima nominal del refuerzo transversal, en kgf.

    E.060 11.5.6.9:
        Vs ≤ 2.1·√(f'c)·b·d      [kgf/cm², cm]
    """
    return 2.1 * sqrt(max(fc, 1.0)) * b * d


def av_minimo_por_s(fc: float, b: float, fy: float) -> float:
    """
    Área mínima de estribos por unidad de longitud, en cm²/cm.

    E.060 11.5.6.3:
        Av,min/s = 0.20·√(f'c)·b/fy   ≥ 3.5·b/fy
    """
    return max(0.20 * sqrt(max(fc, 1.0)) * b / fy, 3.5 * b / fy)


def s_maximo_general(d: float) -> float:
    """
    Espaciamiento máximo general de estribos, en cm.

    E.060 11.5.5.1: s ≤ d/2 ≤ 60 cm.
    """
    return min(d / 2.0, 60.0)


def s_maximo_confinamiento(d: float, db_long_min: float, db_estribo: float) -> float:
    """
    Espaciamiento máximo en zona de confinamiento de vigas de pórticos
    especiales y duales tipo II, en cm.

    E.060 21.5.3.4: el menor de
        a) d/4
        b) 8·db de la barra longitudinal de menor diámetro
        c) 24·db del estribo de confinamiento
        d) 30 cm
    """
    return min(d / 4.0, 8.0 * db_long_min, 24.0 * db_estribo, 30.0)


def longitud_confinamiento(h: float) -> float:
    """
    Longitud de la zona de confinamiento medida desde la cara del apoyo.

    E.060 21.5.3.1: 2h en ambos extremos de la viga.
    """
    return 2.0 * h


def vu_por_capacidad(Mpr_i_tm: float, Mpr_j_tm: float, ln_m: float) -> float:
    """
    Cortante asociado al desarrollo de las resistencias probables en flexión,
    en t, para una viga en doble curvatura.

    E.060 21.5.4.1:
        Ve = (Mpr,i + Mpr,j)/ln
    con Mpr = 1.25·Mn.
    """
    if ln_m <= 0:
        raise ValueError("La luz libre debe ser positiva.")
    return (abs(Mpr_i_tm) + abs(Mpr_j_tm)) / ln_m


# ---------------------------------------------------------------------------
# Requisitos geométricos y de detalle (Capítulo 21)
# ---------------------------------------------------------------------------
def chequeos_geometricos_viga(b: float, h: float, ln_m: float) -> list[tuple[str, str, str, bool, str]]:
    """
    Verifica los requisitos geométricos de vigas de pórticos especiales y
    duales tipo II.

    E.060 21.5.1:
        * ln ≥ 4h
        * bw ≥ 0.25h
        * bw ≥ 250 mm (25 cm)

    Devuelve tuplas ``(nombre, valor, límite, cumple, referencia)``.
    """
    ln_cm = ln_m * 100.0
    return [
        (
            "Luz libre mínima",
            f"ln = {ln_cm:.1f} cm",
            f"ln ≥ 4h = {4 * h:.1f} cm",
            ln_cm >= 4 * h,
            "E.060 21.5.1.1",
        ),
        (
            "Ancho mínimo relativo",
            f"b = {b:.1f} cm",
            f"b ≥ 0.25h = {0.25 * h:.1f} cm",
            b >= 0.25 * h,
            "E.060 21.5.1.3",
        ),
        (
            "Ancho mínimo absoluto",
            f"b = {b:.1f} cm",
            "b ≥ 25.0 cm",
            b >= 25.0,
            "E.060 21.5.1.3",
        ),
    ]


def diametro_minimo_estribo(db_long_max: float) -> float:
    """
    Diámetro mínimo del estribo de confinamiento, en cm.

    E.060 21.5.3.2:
        * 3/8" (0.95 cm) para barras longitudinales ≤ 1"
        * 1/2" (1.27 cm) para barras longitudinales > 1"
    """
    return 1.270 if db_long_max > 2.54 else 0.9525


def espaciamiento_ramas_maximo() -> float:
    """Separación máxima entre ramas verticales de estribos: 30 cm (21.5.3.6)."""
    return 30.0
