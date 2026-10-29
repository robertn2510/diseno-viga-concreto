"""
Constantes y reglas de la NTP E.060 "Concreto Armado" (RNE, Perú).

La E.060 peruana es una adaptación del ACI 318; se mantiene la numeración de
artículos del ACI 318-05/08/14 con la denominación E.060. Las referencias
incluidas aquí corresponden a los artículos de la norma peruana vigente.

Todos los valores internos están en kgf y cm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Sequence


# ===========================================================================
# 1. MATERIALES
# ===========================================================================
FC_MIN = 170.0          # kgf/cm² — E.060 5.1.1 (concreto estructural)
FC_MIN_SISMICO = 210.0  # kgf/cm² — E.060 21.1.4.1 (pórticos sismorresistentes)
FY_MIN = 4200.0         # kgf/cm² — acero grado 60, usual en Perú
ES = 2_000_000.0        # kgf/cm² — módulo de elasticidad del acero (E.060 8.5.2)
EC_FACTOR = 15000.0     # Ec = 15000·√f'c  (E.060 8.5.1)

# límites de deformación (E.060 10.3.2 / 10.3.3)
EPS_CU = 0.003          # deformación última del concreto a compresión
EPS_Y = 0.0021          # fy/Es con fy=4200
EPS_T_TRACCION = 0.005  # límite de sección controlada por tracción (φ = 0.90)
                        # E.060 9.3.2 / 10.3.4
EPS_T_DUCTIL = 0.004    # mínimo recomendado E.060 10.3.4 (transición)


def beta1(fc: float) -> float:
    """
    Factor β1 del bloque rectangular equivalente de esfuerzos.
    E.060 10.2.7.3:
        f'c ≤ 280 kgf/cm²  → β1 = 0.85
        por cada 70 kgf/cm² de exceso → se reduce 0.05, mínimo 0.65
    """
    if fc <= 280.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc - 280.0) / 70.0)


def modulo_elasticidad_concreto(fc: float, peso_normal: bool = True) -> float:
    """Ec = 15000·√f'c [kgf/cm²] (E.060 8.5.1, concreto de peso normal)."""
    factor = EC_FACTOR if peso_normal else 10000.0
    return factor * math.sqrt(fc)


# ---------------------------------------------------------------------------
# Factores de reducción φ (E.060 9.3.2)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FactoresPhi:
    flexion: float = 0.90            # 9.3.2.1 tracción controlada
    compresion_estribos: float = 0.65  # 9.3.2.2 (falla por compresión)
    compresion_zunchos: float = 0.75   # 9.3.2.2 (con zunchos/flejes)
    corte: float = 0.85              # 9.3.2.3 corte en concreto de peso normal
    torsion: float = 0.85            # 9.3.2.3 torsión
    aplastamiento: float = 0.65      # 9.3.2.4
    otro: float = 0.90

    # --- E.060 21.2.1 (pórticos sismorresistentes especiales) ------------
    corte_sismico: float = 0.60      # 21.2.4.2 φcorte en zona de rótula
    corte_sismico_confinado: float = 0.85  # 21.2.4.3 si hay confinamiento


PHI = FactoresPhi()


def phi_flexion(eps_t: float) -> float:
    """
    φ para flexión/flexo-compresión según la deformación neta de tracción
    del acero extremo εt (E.060 9.3.2, interpolación en la zona de transición).
    """
    if eps_t <= EPS_Y:
        return 0.65
    if eps_t >= EPS_T_TRACCION:
        return 0.90
    # interpolación lineal entre 0.65 (εt=εy) y 0.90 (εt=0.005)
    return 0.65 + 0.25 * (eps_t - EPS_Y) / (EPS_T_TRACCION - EPS_Y)


# ===========================================================================
# 2. VARILLAS CORRUGADAS COMERCIALES (ASTM A615 Grado 60)
#    Diámetro nominal en pulgadas -> área nominal (cm²)
# ===========================================================================
@dataclass(frozen=True)
class Varilla:
    nombre: str
    diametro_cm: float
    area_cm2: float
    peso_kg_m: float

    @property
    def pulgadas(self) -> float:
        return self.diametro_cm / 2.54

    @property
    def etiqueta(self) -> str:
        """Etiqueta comercial, p. ej. '3/4" (#6)'."""
        pulg = PULGADAS_TEXTO.get(self.nombre, "")
        return f'{pulg} ({self.nombre})' if pulg else self.nombre

    @property
    def descripcion(self) -> str:
        return f'Ø {self.etiqueta} · {self.diametro_cm*10:.1f} mm' 


PULGADAS_TEXTO = {
    "#2": '1/4"', "#3": '3/8"', "#4": '1/2"', "#5": '5/8"', "#6": '3/4"',
    "#7": '7/8"', "#8": '1"', "#9": '1 1/8"', "#10": '1 1/4"', "#11": '1 3/8"',
}

VARILLAS: Dict[str, Varilla] = {
    "#3": Varilla('#3', 0.953, 0.713, 0.560),
    "#4": Varilla('#4', 1.270, 1.267, 0.994),
    "#5": Varilla('#5', 1.588, 1.979, 1.552),
    "#6": Varilla('#6', 1.905, 2.850, 2.235),
    "#7": Varilla('#7', 2.222, 3.871, 3.042),
    "#8": Varilla('#8', 2.540, 5.067, 3.973),
    "#9": Varilla('#9', 2.865, 6.450, 5.060),
    "#10": Varilla('#10', 3.226, 8.190, 6.404),
    "#11": Varilla('#11', 3.581, 10.060, 7.907),
}

# Nombres con diámetro en pulgadas, para compatibilidad con la v3 y con los
# reportes que el usuario pueda tener.
ALIAS_VARILLAS = {
    '3/8"': "#3", '1/2"': "#4", '5/8"': "#5", '3/4"': "#6",
    '7/8"': "#7", '1"': "#8", '1 1/8"': "#9", '1 1/4"': "#10", '1 3/8"': "#11",
}

VARILLAS_VIGA = ["#3", "#4", "#5", "#6", "#7", "#8"]        # longitudinal típico
VARILLAS_COLUMNA = ["#4", "#5", "#6", "#7", "#8", "#9", "#10"]
VARILLAS_ESTRIBO = ["#2", "#3", "#4"]                        # #2 = 6 mm aprox.

VARILLAS["#2"] = Varilla('#2', 0.635, 0.316, 0.250)          # 1/4" (6.35 mm)


def varilla(nombre: str) -> Varilla:
    """Obtiene una varilla por nombre ('#5', '5/8"') o por su área? No: por nombre."""
    if nombre in VARILLAS:
        return VARILLAS[nombre]
    if nombre in ALIAS_VARILLAS:
        return VARILLAS[ALIAS_VARILLAS[nombre]]
    clave = nombre.strip().replace(" ", "")
    if clave.startswith('#'):
        return VARILLAS[clave]
    raise KeyError(f"Varilla desconocida: {nombre!r}. Use, p. ej., '#5' o '5/8\"'.")


def varillas_equivalentes(area_cm2: float, catalogo: List[str] | None = None,
                          n_max: int = 12) -> List[dict]:
    """
    Combinaciones de varillas comerciales que cubren un área requerida.
    Devuelve las mejores opciones ordenadas por exceso de área.
    """
    catalogo = catalogo or VARILLAS_VIGA
    opciones = []
    for nombre in catalogo:
        v = VARILLAS[nombre]
        n = max(2, math.ceil(area_cm2 / v.area_cm2 - 1e-9))
        if n > n_max:
            continue
        opciones.append({
            "varilla": nombre,
            "n": int(n),
            "area": n * v.area_cm2,
            "exceso_pct": 100.0 * (n * v.area_cm2 - area_cm2) / max(area_cm2, 1e-9),
            "diametro_cm": v.diametro_cm,
        })
    opciones.sort(key=lambda o: (o["exceso_pct"], o["n"]))
    return opciones


# ===========================================================================
# 3. RECUBRIMIENTOS (E.060 7.7.1 y 20.6.1.3)
#    Valores libres mínimos para concreto no expuesto a intemperie ni suelo.
# ===========================================================================
@dataclass(frozen=True)
class Recubrimiento:
    viga_libre_cm: float = 4.0        # 7.7.1-1 (estribos #3: 5 cm al eje)
    columna_libre_cm: float = 4.0
    losa_cm: float = 2.0
    cimentacion_cm: float = 7.5


RECUBRIMIENTO = Recubrimiento()


# ===========================================================================
# 4. VIGAS — requisitos de flexión y corte
# ===========================================================================
def acero_minimo_flexion(b: float, d: float, fc: float, fy: float) -> float:
    """
    As mínimo en vigas no preesforzadas (E.060 10.5.1):
        As_min = MAYOR( 0.25·√f'c / fy , 14 / fy ) · b·d
    """
    return max(0.25 * math.sqrt(fc) / fy, 14.0 / fy) * b * d


def cuantia_balanceada(fc: float, fy: float) -> float:
    """ρb (E.060 10.3.2 / Apéndice B)."""
    return (0.85 * beta1(fc) * fc / fy) * (6000.0 / (6000.0 + fy))


def cuantia_maxima(fc: float, fy: float, eps_t_min: float = 0.004) -> float:
    """
    ρ máximo para sección dúctil: aquel en que εt = eps_t_min.
    (E.060 10.3.4 y 21.3.3 imponen εt ≥ 0.004 en pórticos sismorresistentes.)
    """
    b1 = beta1(fc)
    c_d = EPS_CU / (EPS_CU + eps_t_min)          # c/d
    return 0.85 * b1 * fc / fy * c_d


def cortante_concreto_viga(bw: float, d: float, fc: float, nu: float = 0.0,
                           ag: float | None = None) -> float:
    """
    Resistencia al corte del concreto en vigas (E.060 11.3.1.1):
        Vc = 0.53·√f'c·bw·d·(1 + Nu/(14·Ag))
    Nu es la fuerza axial de compresión (kgf, positiva en compresión).
    """
    ag = ag if ag is not None else bw * (d / 0.9)
    factor = 1.0 + (nu / (14.0 * ag) if ag > 0 else 0.0)
    factor = max(factor, 0.0)
    return 0.53 * math.sqrt(fc) * bw * d * factor


def vc_detallado(bw: float, d: float, fc: float, rho_w: float,
                 mu_kgfcm: float, vu_kgf: float, nu: float = 0.0) -> float:
    """
    E.060 11.3.2.1: Vc = (0.50√f'c + 175·ρw·Vu·d/Mu)·bw·d ≤ 0.93√f'c·bw·d
    Requiere Mu ≥ Vu·d (se acota para evitar incoherencias).
    """
    if mu_kgfcm <= 0:
        return 0.53 * math.sqrt(fc) * bw * d
    relacion = min(vu_kgf * d / mu_kgfcm, 1.0)
    vc = (0.50 * math.sqrt(fc) + 175.0 * rho_w * relacion) * bw * d
    vc = min(vc, 0.93 * math.sqrt(fc) * bw * d)
    vc = max(vc, 0.53 * math.sqrt(fc) * bw * d)
    return vc


def cortante_maximo_acero(bw: float, d: float, fc: float) -> float:
    """Vs máximo (E.060 11.4.7.9): Vs ≤ 2.1·√f'c·bw·d  (equivale a Vn ≤ 2.6·√f'c·bw·d)."""
    return 2.1 * math.sqrt(fc) * bw * d


def espaciamiento_max_estribos(d: float, h: float, vu_kgf: float,
                               phi_vc_kgf: float, sismico: bool = False) -> float:
    """
    Espaciamiento máximo de estribos (E.060 11.4.5.1 y 21.4.4.2):
      - VS > 1.1√f'c·bw·d  → s ≤ d/4
      - en caso contrario    → s ≤ d/2
      - pórticos sismorresistentes (21.4.4.2):
            zona de confinamiento (2h desde el apoyo): s ≤ d/4, 8·db_long, 24·db_est, 30 cm
    """
    s = d / 2.0
    if sismico:
        s = min(d / 4.0, 8 * 2.54, 24 * 0.953, 30.0)
    return max(5.0, s)


# ===========================================================================
# 5. COLUMNAS — E.060 10.10 (esbeltez) y 21.4 (sismorresistente)
# ===========================================================================
def radio_giro_aprox(b: float, h: float) -> float:
    """Radio de giro aproximado de sección rectangular (0.30·lado menor)."""
    return 0.30 * min(b, h)


def limite_esbeltez(m1: float, m2: float) -> float:
    """
    E.060 10.10.1.1: k·lu/r ≤ 34 - 12·(M1/M2)  ≤ 40
    M1/M2 positivo si la columna se flecta en curvatura simple.
    """
    if abs(m2) < 1e-9:
        return 40.0
    relacion = m1 / m2
    relacion = max(-1.0, min(1.0, relacion))
    return min(40.0, 34.0 - 12.0 * relacion)


def amplificacion_momentos(nu_kgf: float, ec: float, ig_cm4: float,
                           lu_cm: float, m1: float, m2: float,
                           beta_dns: float = 0.0) -> float:
    """
    Magnificación de momentos para pórticos no arriostrados/sin desplazamiento
    lateral (E.060 10.10.7 / 10.10.6):
        δns = Cm / (1 - Pu/(0.75·Pc))  ≥ 1.0
        Pc  = π²·EI / (k·lu)²
        EI  = 0.4·Ec·Ig / (1 + βdns)
        Cm  = 0.6 + 0.4·(M1/M2) ≥ 0.4
    """
    ei = 0.4 * ec * ig_cm4 / (1.0 + beta_dns)
    pc = math.pi ** 2 * ei / (lu_cm ** 2)          # k = 1 (empotrado-empotrado)
    denom = 1.0 - nu_kgf / (0.75 * pc) if pc > 0 else 0.0
    if denom <= 0.05:
        return float("inf")
    relacion = 0.0 if abs(m2) < 1e-9 else max(-1.0, min(1.0, m1 / m2))
    cm = max(0.4, 0.6 + 0.4 * relacion)
    return max(1.0, cm / denom)


def area_zuncho(b: float, h: float) -> float:
    """Área de la sección confinada por zunchos (E.060 21.4.4.4)."""
    return max(0.0, (b - 2 * 4.0) * (h - 2 * 4.0))


def refuerzo_transversal_columna(ag: float, ach: float, fc: float, fy: float,
                                 db_long: float) -> float:
    """
    Refuerzo transversal en zona de confinamiento de columnas
    (E.060 21.4.4.4):  Ash/s = MAYOR(
        0.3·(Ag/Ach - 1)·f'c/fy ,
        0.09·f'c/fy ) · bc
    Devuelve el área de estribo requerida por cada espaciamiento s (cm²/cm).
    """
    return max(0.3 * (ag / ach - 1.0) * fc / fy,
               0.09 * fc / fy)


def espaciamiento_confinamiento(b: float, h: float, db_long: float,
                                db_est: float) -> float:
    """
    s ≤ MENOR(b/4, 100 mm, 6·db_long, 24·db_est)  (E.060 21.4.4.4);
    en Perú se acepta 100 mm como espaciamiento típico de confinamiento.
    """
    return min(b / 4.0, h / 4.0, 10.0, 6.0 * db_long, 24.0 * db_est)


def phi_corte_columna(confina: bool = True) -> float:
    """φ de corte en columnas: 0.85 (confinada) o 0.60 (E.060 21.2.4)."""
    return PHI.corte_sismico_confinado if confina else PHI.corte_sismico


# ===========================================================================
# 6. COMBINACIONES DE CARGA (E.060 9.2 + NTE E.030)
# ===========================================================================
@dataclass
class Combinacion:
    nombre: str
    factores: Dict[str, float]
    tipo: str = "resistencia"        # 'servicio' | 'resistencia'
    descripcion: str = ""

    def evaluar(self, casos: Dict[str, float]) -> float:
        total = 0.0
        for caso, f in self.factores.items():
            total += f * casos.get(caso, 0.0)
        return total


def combinaciones_e060(incluir_sismo: bool = True,
                       normativa_sismo: str = "E.030-2018",
                       direcciones: Sequence[str] = ("X", "Y")) -> List[Combinacion]:
    """
    Combinaciones de carga según E.060 9.2.1 (y E.030 para sismo).

    Se usa CM = carga muerta, CV = carga viva, CS = sismo en X, CSY = sismo en Y.
    E.030-2018 1.4.2 (art. 16):  1.4CM + 1.7CV
                                 1.25(CM + CV) ± CS
                                 0.9CM ± CS
    """
    combos = [
        Combinacion("1.4CM + 1.7CV", {"CM": 1.4, "CV": 1.7},
                    descripcion="E.060 9.2.1-1"),
        Combinacion("1.2CM + 1.6CV + 0.5CVt",
                    {"CM": 1.2, "CV": 1.6, "CVT": 0.5},
                    descripcion="E.060 9.2.1-2 (CVt = carga viva de techo)"),
        Combinacion("1.2CM + 1.0CV + 1.0CS", {"CM": 1.2, "CV": 1.0},
                    descripcion="E.060 9.2.1-3"),
        Combinacion("1.2CM + 1.6CVT", {"CM": 1.2, "CVT": 1.6},
                    descripcion="E.060 9.2.1-4"),
        Combinacion("0.9CM", {"CM": 0.9}, descripcion="E.060 9.2.1-5"),
        Combinacion("CM + CV", {"CM": 1.0, "CV": 1.0}, tipo="servicio",
                    descripcion="Verificación de deflexiones / servicio"),
    ]
    pares = [(suf, caso) for suf, caso in (("X", "CS"), ("Y", "CSY"))
             if suf in direcciones]
    if incluir_sismo:
        if normativa_sismo == "E.030-2018":
            for sufijo, caso in pares:
                combos += [
                    Combinacion(f"1.4CM + 1.7CV + 1.25CS{sufijo}",
                                {"CM": 1.4, "CV": 1.7, caso: 1.25},
                                descripcion="E.030-2018 art. 1.4.2"),
                    Combinacion(f"1.25(CM+CV) + CS{sufijo}",
                                {"CM": 1.25, "CV": 1.25, caso: 1.0},
                                descripcion="E.030-2018 art. 1.4.2"),
                    Combinacion(f"1.25(CM+CV) - CS{sufijo}",
                                {"CM": 1.25, "CV": 1.25, caso: -1.0},
                                descripcion="E.030-2018 art. 1.4.2"),
                    Combinacion(f"0.9CM + CS{sufijo}",
                                {"CM": 0.9, caso: 1.0},
                                descripcion="E.030-2018 art. 1.4.2"),
                    Combinacion(f"0.9CM - CS{sufijo}",
                                {"CM": 0.9, caso: -1.0},
                                descripcion="E.030-2018 art. 1.4.2"),
                ]
        else:  # E.060 9.2.1 clásico con 1.0CM + 1.0CV ± 1.4CS
            for sufijo, caso in pares:
                combos += [
                    Combinacion(f"1.0CM + 1.0CV + 1.4CS{sufijo}",
                                {"CM": 1.0, "CV": 1.0, caso: 1.4},
                                descripcion="E.060 9.2.1"),
                    Combinacion(f"1.0CM + 1.0CV - 1.4CS{sufijo}",
                                {"CM": 1.0, "CV": 1.0, caso: -1.4},
                                descripcion="E.060 9.2.1"),
                    Combinacion(f"0.9CM + 1.4CS{sufijo}",
                                {"CM": 0.9, caso: 1.4},
                                descripcion="E.060 9.2.1"),
                    Combinacion(f"0.9CM - 1.4CS{sufijo}",
                                {"CM": 0.9, caso: -1.4},
                                descripcion="E.060 9.2.1"),
                ]
    return combos
