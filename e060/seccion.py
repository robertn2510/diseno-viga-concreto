"""
Análisis de secciones de concreto armado por compatibilidad de deformaciones.

Se implementa el bloque rectangular equivalente de esfuerzos (Whitney) con
geometría arbitraria (polígono convexo) y orientación arbitraria del eje
neutro, lo que permite:

  * Diagramas de interacción P-M uniaxiales (cualquier eje).
  * Superficie de interacción P-Mx-My (flexo-compresión biaxial), resolviendo
    la capacidad exacta en la dirección del momento demandado mediante
    búsqueda bidimensional (ángulo del eje neutro y profundidad c).
  * Diseño de flexión en vigas (As requerido, doble capa, verificación de φMn).

Hipótesis (E.060 10.2):
  - Las secciones planas permanecen planas.
  - Deformación máxima útil del concreto εcu = 0.003.
  - Bloque rectangular equivalente: 0.85·f'c sobre un ancho a = β1·c.
  - El acero cumple εs = Es·ε con plasticidad perfecta a fy (elastoplástico).
  - No se considera la resistencia a tracción del concreto.
  - El acero en compresión descuenta el concreto desplazado (0.85·f'c·As).

Convención de ejes locales:
  x → dimensión b (ancho de la sección)
  y → dimensión h (peralte de la sección)
  θ = 0°   → eje neutro paralelo a "b", flexión "sobre b" → Mx (peralte h).
  θ = 90°  → eje neutro paralelo a "h", flexión "sobre h" → My (peralte b).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Tuple

from . import normas
from .normas import EPS_CU, ES, PHI, beta1, phi_flexion


Punto = Tuple[float, float]


# ===========================================================================
# Geometría: polígonos, recorte por semiplano, área y centroide
# ===========================================================================
def area_centroide(poly: Sequence[Punto]) -> Tuple[float, float, float]:
    """Área y centroide de un polígono simple (shoelace)."""
    n = len(poly)
    if n < 3:
        return 0.0, 0.0, 0.0
    a2 = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cruz = x1 * y2 - x2 * y1
        a2 += cruz
        cx += (x1 + x2) * cruz
        cy += (y1 + y2) * cruz
    a = a2 / 2.0
    if abs(a) < 1e-12:
        return 0.0, 0.0, 0.0
    return abs(a), cx / (6.0 * a), cy / (6.0 * a)


def recortar_semiplano(poly: Sequence[Punto], ux: float, uy: float,
                       t: float) -> List[Punto]:
    """Recorta el polígono conservando la región con ux·x + uy·y ≥ t."""
    salida: List[Punto] = []
    n = len(poly)
    if n == 0:
        return salida
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        q1 = ux * p1[0] + uy * p1[1] - t
        q2 = ux * p2[0] + uy * p2[1] - t
        dentro1 = q1 >= -1e-12
        dentro2 = q2 >= -1e-12
        if dentro1:
            salida.append(p1)
        if dentro1 != dentro2:
            denom = (q1 - q2)
            if abs(denom) > 1e-15:
                f = q1 / denom
                salida.append((p1[0] + f * (p2[0] - p1[0]),
                               p1[1] + f * (p2[1] - p1[1])))
    return salida


def rectangulo(b: float, h: float) -> List[Punto]:
    """Rectángulo centrado en el origen: ancho b (x), peralte h (y)."""
    return [(-b / 2.0, -h / 2.0), (b / 2.0, -h / 2.0),
            (b / 2.0, h / 2.0), (-b / 2.0, h / 2.0)]


# ===========================================================================
# Barras
# ===========================================================================
@dataclass
class Barra:
    x: float
    y: float
    db: float
    nombre: str = ""
    _area: float | None = None

    @property
    def area(self) -> float:
        if self._area is not None:
            return self._area
        return math.pi * self.db ** 2 / 4.0


@dataclass
class LayoutBarras:
    """Distribución de barras para columnas rectangulares."""
    n_cara_x: int          # barras por cara paralela a x (caras superior e inferior)
    n_cara_y: int          # barras por cara paralela a y
    db: float              # diámetro longitudinal [cm]
    db_estribo: float = 0.953
    recubrimiento_libre: float = 4.0

    def posiciones(self, b: float, h: float) -> List[Barra]:
        """
        Genera barras simétricas. n_cara_x = barras en las caras de arriba y
        abajo (incluyendo esquinas); n_cara_y = barras en las caras laterales.
        """
        nx = max(2, int(self.n_cara_x))
        ny = max(2, int(self.n_cara_y))
        d_centro = self.recubrimiento_libre + self.db_estribo + self.db / 2.0
        x_max = b / 2.0 - d_centro
        y_max = h / 2.0 - d_centro
        barras: List[Barra] = []
        # caras horizontales (y = ±y_max)
        xs = [(-x_max + 2 * x_max * i / (nx - 1)) for i in range(nx)] if nx > 1 else [0.0]
        for y in (-y_max, y_max):
            for i, x in enumerate(xs):
                if (y == -y_max and i == 0) or (y == y_max and i == 0) or True:
                    barras.append(Barra(x, y, self.db))
        # caras verticales intermedias (x = ±x_max), excluyendo esquinas
        ys = [(-y_max + 2 * y_max * j / (ny - 1)) for j in range(ny)]
        for x in (-x_max, x_max):
            for j, y in enumerate(ys):
                if j == 0 or j == ny - 1:
                    continue          # esquinas ya contadas
                barras.append(Barra(x, y, self.db))
        return barras

    def descripcion(self) -> str:
        return f"{self.n_cara_x} barras por cara horizontal + {self.n_cara_y} por cara vertical · #{round(self.db*10/2.54*10)/10:.0f}"


def diametro_a_etiqueta(db: float) -> str:
    """Devuelve la etiqueta '#n' o 'd mm' más cercana a un diámetro en cm."""
    for nombre, v in normas.VARILLAS.items():
        if abs(v.diametro_cm - db) < 0.06:
            return nombre
    return f"Ø{db*10:.0f} mm"


# ===========================================================================
# Resultado del análisis de una fibra
# ===========================================================================
@dataclass
class Fibra:
    c: float
    theta: float
    P: float                  # fuerza axial [kgf] (+ compresión)
    Mx: float                 # momento alrededor de x [kgf·cm]
    My: float                 # momento alrededor de y [kgf·cm]
    eps_t: float              # deformación máxima de tracción en el acero
    eps_c_max: float
    Cc: float                 # compresión del concreto [kgf]
    Fs: List[float] = field(default_factory=list)
    eps_s: List[float] = field(default_factory=list)
    bloque_area: float = 0.0
    phi: float = 0.65

    @property
    def phiP(self) -> float:
        return self.phi * self.P

    @property
    def phiMn(self) -> float:
        return self.phi * math.hypot(self.Mx, self.My)


# ===========================================================================
# Sección
# ===========================================================================
class Seccion:
    """
    Sección de concreto armado definida por un polígono (centrado en el
    centroide geométrico) y un conjunto de barras.
    """

    def __init__(self, b: float, h: float, barras: Iterable[Barra],
                 fc: float, fy: float, nombre: str = "",
                 recubrimiento: float = 4.0, db_estribo: float = 0.953,
                 poligono: Sequence[Punto] | None = None,
                 zunchada: bool = False):
        self.b = float(b)
        self.h = float(h)
        self.fc = float(fc)
        self.fy = float(fy)
        self.nombre = nombre or f"{b:.0f}x{h:.0f}"
        self.recubrimiento = recubrimiento
        self.db_estribo = db_estribo
        self.zunchada = zunchada
        self.poligono: List[Punto] = list(poligono) if poligono else rectangulo(b, h)
        # normaliza al centroide geométrico
        a, cx, cy = area_centroide(self.poligono)
        self.Ag = a
        self.centro = (cx, cy)
        self.poligono = [(x - cx, y - cy) for x, y in self.poligono]
        self.barras: List[Barra] = [Barra(br.x - cx, br.y - cy, br.db)
                                    for br in barras]
        self._iy, self._ix = self._inercias()
        # cotas de la sección original respecto al centroide
        self.y_min = min(p[1] for p in self.poligono)
        self.y_max = max(p[1] for p in self.poligono)
        self.x_min = min(p[0] for p in self.poligono)
        self.x_max = max(p[0] for p in self.poligono)

    # ------------------------------------------------------------------
    def _inercias(self) -> Tuple[float, float]:
        """Momentos de inercia respecto a los ejes centroidales."""
        poly = self.poligono
        ix = 0.0
        iy = 0.0
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            cruz = x1 * y2 - x2 * y1
            ix += (y1 * y1 + y1 * y2 + y2 * y2) * cruz
            iy += (x1 * x1 + x1 * x2 + x2 * x2) * cruz
        return abs(iy / 12.0), abs(ix / 12.0)

    @property
    def Ix(self) -> float:
        return self._ix

    @property
    def Iy(self) -> float:
        return self._iy

    @property
    def As_total(self) -> float:
        return sum(br.area for br in self.barras)

    @property
    def cuantia(self) -> float:
        return self.As_total / self.Ag

    @property
    def recubrimiento_eje(self) -> float:
        return self.recubrimiento + self.db_estribo

    # ------------------------------------------------------------------
    # 1. Análisis de una fibra
    # ------------------------------------------------------------------
    def fibra(self, c: float, theta_deg: float = 0.0) -> Fibra:
        """
        Calcula P, Mx, My para una profundidad de eje neutro c y orientación
        theta (grados) del vector normal al eje neutro. La compresión extrema
        se ubica en el borde de proyección mínima.
        """
        th = math.radians(theta_deg)
        ux, uy = math.cos(th), math.sin(th)
        proj = [ux * p[0] + uy * p[1] for p in self.poligono]
        q_min = min(proj)
        c = max(1e-4, min(c, 4.0 * max(self.b, self.h)))
        a = beta1(self.fc) * c                       # profundidad del bloque
        a = min(a, (max(proj) - q_min) + 1e-6)

        # --- Concreto: bloque entre q_min y q_min + a -------------------
        t_bloque = q_min + a
        arriba = recortar_semiplano(self.poligono, ux, uy, t_bloque)
        a_sup, cx_sup, cy_sup = area_centroide(arriba)
        a_tot, cx_tot, cy_tot = area_centroide(self.poligono)
        area_bloque = a_tot - a_sup
        if area_bloque > 1e-9:
            cx_bloque = (a_tot * cx_tot - a_sup * cx_sup) / area_bloque
            cy_bloque = (a_tot * cy_tot - a_sup * cy_sup) / area_bloque
        else:
            cx_bloque = cy_bloque = 0.0
        Cc = 0.85 * self.fc * max(area_bloque, 0.0)

        P = Cc
        Mx = -Cc * cy_bloque       # momento alrededor de x (compresión en y<0)
        My = -Cc * cx_bloque

        # --- Acero ------------------------------------------------------
        eps_s: List[float] = []
        Fs: List[float] = []
        eps_t = 0.0
        eps_c_max = 0.0
        for br in self.barras:
            q = ux * br.x + uy * br.y
            dist = q - q_min                    # distancia desde fibra comprimida
            if c <= 1e-9:
                eps = 0.0
            else:
                eps = EPS_CU * (c - dist) / c    # + compresión
            eps_s.append(eps)
            eps_c_max = max(eps_c_max, eps)
            if eps < 0:
                eps_t = max(eps_t, -eps)
            if eps >= 0:
                fs = min(self.fy, ES * eps)
            else:
                fs = max(-self.fy, ES * eps)
            F = fs * br.area
            if eps > 0:   # descuenta concreto desplazado
                F -= 0.85 * self.fc * br.area
            Fs.append(F)
            P += F
            Mx += -F * br.y
            My += -F * br.x

        phi = phi_flexion(eps_t)
        if self.zunchada:
            phi = min(0.75, max(phi, 0.70)) if eps_t <= normas.EPS_Y else phi
        return Fibra(c=c, theta=theta_deg, P=P, Mx=Mx, My=My, eps_t=eps_t,
                     eps_c_max=eps_c_max, Cc=Cc, Fs=Fs, eps_s=eps_s,
                     bloque_area=area_bloque, phi=phi)

    # ------------------------------------------------------------------
    # 2. Propiedades básicas de capacidad axial
    # ------------------------------------------------------------------
    @property
    def P0(self) -> float:
        """Carga axial pura: P0 = 0.85·f'c·(Ag - As) + fy·As (E.060 10.3.6)."""
        return 0.85 * self.fc * (self.Ag - self.As_total) + self.fy * self.As_total

    @property
    def phiP0(self) -> float:
        return PHI.compresion_zunchos * 0.85 * self.P0 if self.zunchada else \
            PHI.compresion_estribos * 0.80 * self.P0

    @property
    def fy_As(self) -> float:
        return self.fy * self.As_total

    def cuantia_geometrica(self) -> float:
        return self.As_total / self.Ag

    # ------------------------------------------------------------------
    # 3. Diagramas de interacción uniaxiales
    # ------------------------------------------------------------------
    def diagrama(self, theta_deg: float = 0.0, n: int = 60,
                 incluir_traccion: bool = True) -> List[Fibra]:
        """
        Puntos del diagrama de interacción (P, M) para un eje dado.

        Se barre la profundidad del eje neutro c desde valores muy pequeños
        (tracción) hasta que la sección queda totalmente comprimida; el barrido
        se detiene cuando P supera 0.97·P0 para no dibujar la rama de retorno.
        """
        hmax = max(self.b, self.h)
        c_min, c_max = 0.004 * hmax, 2.0 * hmax
        puntos: List[Fibra] = []
        for i in range(n):
            f = i / (n - 1)
            c = c_min * (c_max / c_min) ** f
            fb = self.fibra(c, theta_deg)
            if puntos and fb.P > 0.97 * self.P0:
                break
            puntos.append(fb)
        if incluir_traccion and (not puntos or puntos[0].P > 0):
            puntos.insert(0, self.fibra(0.001 * hmax, theta_deg))
        return puntos

    def phiPn_max(self) -> float:
        """φPn máximo permitido (E.060 10.3.6): 0.80·φ·P0 (estribos) / 0.85 (zunchos)."""
        factor = 0.85 if self.zunchada else 0.80
        phi = PHI.compresion_zunchos if self.zunchada else PHI.compresion_estribos
        return phi * factor * self.P0

    def capacidad_uniaxial(self, theta_deg: float, Pu: float) -> Tuple[float, Fibra]:
        """
        Momento resistente de diseño φMn en un eje dado para una carga axial Pu.

        Se busca el punto del diagrama de diseño (φPn, φMn) con φPn = Pu, es
        decir se resuelve φ(c)·P(c) = Pu; el factor φ se evalúa con la
        deformación εt de cada punto (E.060 10.3.2).
        Si Pu supera φPn,max se devuelve (0.0, fibra límite).
        """
        hmax = max(self.b, self.h)
        if Pu >= self.phiPn_max():
            return 0.0, self.fibra(4.0 * hmax, theta_deg)
        c_lo, c_hi = 0.02 * hmax, 4.0 * hmax
        f_lo = self.fibra(c_lo, theta_deg)
        f_hi = self.fibra(c_hi, theta_deg)
        if Pu <= f_lo.phi * f_lo.P:
            return f_lo.phi * math.hypot(f_lo.Mx, f_lo.My), f_lo
        if Pu >= f_hi.phi * f_hi.P:
            return 0.0, f_hi
        for _ in range(70):
            c_mid = 0.5 * (c_lo + c_hi)
            fb = self.fibra(c_mid, theta_deg)
            if abs(fb.phi * fb.P - Pu) < max(20.0, 1e-6 * abs(Pu)):
                break
            if fb.phi * fb.P > Pu:
                c_hi = c_mid
            else:
                c_lo = c_mid
        fb = self.fibra(0.5 * (c_lo + c_hi), theta_deg)
        return fb.phi * math.hypot(fb.Mx, fb.My), fb

    # ------------------------------------------------------------------
    # 4. Capacidad biaxial exacta (superficie de interacción) (superficie de interacción)
    # ------------------------------------------------------------------
    def capacidad_biaxial(self, Pu: float, alfa_deg: float,
                          tol_theta: float = 0.05) -> Tuple[float, Fibra]:
        """
        Momento de diseño φM capaz en la dirección del momento resultante
        alfa = atan2(Muy, Mux), para la carga axial Pu.

        Se resuelve (θ, c) tal que P(θ, c) = Pu y la dirección del momento
        coincida con alfa.  θ = orientación de la normal al eje neutro,
        c = profundidad del eje neutro.

        El ángulo del momento resultante decrece monótonamente desde 90°
        (θ = 0°, flexión sobre b) hasta 0° (θ = 90°, flexión sobre h), lo que
        permite resolver por bisección anidada: para cada θ se halla c con
        P = Pu y se ajusta θ hasta que el ángulo del momento coincida.
        """
        hmax = max(self.b, self.h)
        alfa = abs(alfa_deg) % 180.0
        if alfa > 90.0:
            alfa = 180.0 - alfa
        if Pu >= self.phiPn_max():
            return 0.0, self.fibra(4.0 * hmax, 0.0)

        def resolver_c(theta: float):
            """Para un θ dado, resuelve φ(c)·P(c) = Pu. Devuelve (φM, ángulo, fibra)."""
            c_lo, c_hi = 0.02 * hmax, 4.0 * hmax
            f_lo = self.fibra(c_lo, theta)
            f_hi = self.fibra(c_hi, theta)
            if not (f_lo.phi * f_lo.P < Pu < f_hi.phi * f_hi.P):
                return None
            for _ in range(60):
                c_mid = 0.5 * (c_lo + c_hi)
                if self.fibra(c_mid, theta).phi * self.fibra(c_mid, theta).P > Pu:
                    c_hi = c_mid
                else:
                    c_lo = c_mid
            fb = self.fibra(0.5 * (c_lo + c_hi), theta)
            m = math.hypot(fb.Mx, fb.My)
            ang = math.degrees(math.atan2(fb.My, fb.Mx)) if m > 1e-9 else 0.0
            return fb.phi * m, ang % 180.0, fb

        r_lo = resolver_c(0.0)          # ángulo ≈ 90°
        r_hi = resolver_c(90.0)         # ángulo ≈ 0°
        if r_lo is None and r_hi is None:
            m, fb = self.capacidad_uniaxial(90.0, Pu)
            return m, fb
        if r_lo is None:
            return r_hi[0], r_hi[2]
        if r_hi is None:
            return r_lo[0], r_lo[2]

        th_lo, th_hi = 0.0, 90.0
        mejor = min((r_lo, r_hi), key=lambda r: abs(r[1] - alfa))
        if abs(mejor[1] - alfa) <= tol_theta:
            return mejor[0], mejor[2]

        for _ in range(45):
            th = 0.5 * (th_lo + th_hi)
            r = resolver_c(th)
            if r is None:
                break
            if abs(r[1] - alfa) < abs(mejor[1] - alfa):
                mejor = r
            if abs(r[1] - alfa) <= tol_theta:
                return r[0], r[2]
            # el ángulo decrece al aumentar θ
            if r[1] > alfa:
                th_lo = th
            else:
                th_hi = th
            if th_hi - th_lo < 1e-4:
                break
        return mejor[0], mejor[2]

    # ------------------------------------------------------------------
    # 4b. Contorno de capacidad biaxial a P constante (para gráficos)
    # ------------------------------------------------------------------
    def contorno_biaxial(self, Pu: float, n: int = 13) -> List[Tuple[float, float]]:
        """
        Contorno (Mux, Muy) de capacidad a carga axial constante, para el
        primer cuadrante.  Devuelve [(Mux, Muy), ...] en kgf·cm y φ aplicado.
        """
        hmax = max(self.b, self.h)
        puntos: List[Tuple[float, float]] = []
        for k in range(n):
            alfa = 90.0 * k / (n - 1)
            m, fb = self.capacidad_biaxial(Pu, alfa)
            a = math.radians(alfa)
            puntos.append((m * math.cos(a), m * math.sin(a)))
        return puntos

    # ------------------------------------------------------------------
    # 5. Información geométrica para reportes
    # ------------------------------------------------------------------
    def resumen_geometria(self) -> dict:
        return {
            "b": self.b, "h": self.h, "Ag": self.Ag,
            "Ix": self.Ix, "Iy": self.Iy,
            "As": self.As_total, "rho": self.cuantia,
            "n_barras": len(self.barras),
            "P0": self.P0, "phiP0": self.phiP0,
        }


# ===========================================================================
# Funciones auxiliares de diseño en flexión (vigas)
# ===========================================================================
def momento_nominal_rectangular(As: float, d: float, fc: float, fy: float,
                                b: float) -> Tuple[float, float]:
    """
    Mn de una sección rectangular simplemente armada:
        a = As·fy/(0.85·f'c·b)
        Mn = As·fy·(d - a/2)
    Devuelve (Mn [kgf·cm], a [cm]).  No aplica φ.
    """
    a = As * fy / (0.85 * fc * b)
    return As * fy * (d - a / 2.0), a


def area_acero_requerida(Mu_kgfcm: float, b: float, d: float, fc: float,
                         fy: float) -> float:
    """
    As requerido para Mu (sin φ) en sección rectangular simplemente armada.
    Resuelve Mu/φ = 0.85·f'c·b·a·(d - a/2) en la incógnita a.
    """
    mu = Mu_kgfcm / PHI.flexion
    disc = 1.0 - 2.0 * mu / (0.85 * fc * b * d * d)
    if disc < 0:
        raise ValueError("La sección es insuficiente para el momento último "
                         "(se requiere refuerzo en compresión o mayor peralte).")
    a = d * (1.0 - math.sqrt(disc))
    return 0.85 * fc * b * a / fy


def momento_ultimo_solicitado(M: float) -> float:
    """Momento de diseño: los momentos de ETABS ya vienen amplificados."""
    return M


def verificar_cuantias(As: float, b: float, d: float, fc: float,
                       fy: float, sismico: bool = True) -> dict:
    as_min = normas.acero_minimo_flexion(b, d, fc, fy)
    rho_max = normas.cuantia_maxima(fc, fy, 0.004 if sismico else 0.005)
    as_max = rho_max * b * d
    return {
        "As_min": as_min,
        "As_max": as_max,
        "rho_min": as_min / (b * d),
        "rho_max": rho_max,
        "cumple_min": As >= as_min * 0.999,
        "cumple_max": As <= as_max,
    }
