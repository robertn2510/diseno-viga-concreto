"""
Modelo demostrativo con análisis matricial de un pórtico plano.

Permite usar el programa sin ETABS instalado: se resuelve un pórtico de
concreto armado de 4 pisos y 3 vanos por el método de rigidez (elementos
frame 2D), se generan las solicitaciones por caso de carga (CM, CV, sismo X)
y luego se evalúan las combinaciones E.060. Las solicitaciones resultantes
son reales (no inventadas) y sirven para validar el motor de diseño.

Advertencia: el modelo es un ejemplo académico de un pórtico plano; no
sustituye el análisis tridimensional del ETABS.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from .. import normas
from ..normas import Combinacion
from .modelo import Elemento, FuenteETABS, PuntoDemanda


# ===========================================================================
# Solver de pórtico plano
# ===========================================================================
class PorticoPlano:
    """
    Pórtico plano resuelto por el método de rigidez.

    Coordenadas: X horizontal [cm], Z vertical [cm].
    Grados de libertad por nudo: u (X), w (Z), θ (giro).
    """

    def __init__(self, fc: float = 210.0):
        self.fc = fc
        self.E = normas.modulo_elasticidad_concreto(fc)
        self.nudos: List[Tuple[float, float]] = []
        self.restricciones: List[Tuple[bool, bool, bool]] = []
        self.elementos: List[dict] = []
        self._index: Dict[Tuple[float, float], int] = {}

    # ------------------------------------------------------------------
    def agregar_nudo(self, x: float, z: float, fijo: bool = False) -> int:
        clave = (round(x, 3), round(z, 3))
        if clave in self._index:
            return self._index[clave]
        idx = len(self.nudos)
        self.nudos.append((x, z))
        self.restricciones.append((fijo, fijo, fijo))
        self._index[clave] = idx
        return idx

    def agregar_elemento(self, i: int, j: int, b: float, h: float,
                         nombre: str = "") -> int:
        x1, z1 = self.nudos[i]
        x2, z2 = self.nudos[j]
        L = math.hypot(x2 - x1, z2 - z1)
        a = b * h
        iz = b * h ** 3 / 12.0
        ux, uz = (x2 - x1) / L, (z2 - z1) / L
        ang = math.atan2(uz, ux)
        self.elementos.append({
            "i": i, "j": j, "L": L, "A": a, "I": iz, "ang": ang,
            "b": b, "h": h, "nombre": nombre or f"E{len(self.elementos)+1}",
            "carga": 0.0,
        })
        return len(self.elementos) - 1

    # ------------------------------------------------------------------
    def _k_local(self, el: dict) -> List[List[float]]:
        E, A, I, L = self.E, el["A"], el["I"], el["L"]
        ea = E * A / L
        ei = E * I
        return [
            [ea, 0, 0, -ea, 0, 0],
            [0, 12 * ei / L ** 3, 6 * ei / L ** 2, 0, -12 * ei / L ** 3, 6 * ei / L ** 2],
            [0, 6 * ei / L ** 2, 4 * ei / L, 0, -6 * ei / L ** 2, 2 * ei / L],
            [-ea, 0, 0, ea, 0, 0],
            [0, -12 * ei / L ** 3, -6 * ei / L ** 2, 0, 12 * ei / L ** 3, -6 * ei / L ** 2],
            [0, 6 * ei / L ** 2, 2 * ei / L, 0, -6 * ei / L ** 2, 4 * ei / L],
        ]

    @staticmethod
    def _T(ang: float) -> List[List[float]]:
        c, s = math.cos(ang), math.sin(ang)
        return [
            [c, s, 0, 0, 0, 0],
            [-s, c, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0],
            [0, 0, 0, c, s, 0],
            [0, 0, 0, -s, c, 0],
            [0, 0, 0, 0, 0, 1],
        ]

    @staticmethod
    def _mtimes(a, b):
        n, m, p = len(a), len(b), len(b[0])
        return [[sum(a[i][k] * b[k][j] for k in range(m)) for j in range(p)]
                for i in range(n)]

    @staticmethod
    def _mv(a, v):
        return [sum(a[i][k] * v[k] for k in range(len(v))) for i in range(len(a))]

    def _k_global(self, el: dict):
        kl = self._k_local(el)
        T = self._T(el["ang"])
        Tt = [[T[j][i] for j in range(6)] for i in range(6)]
        return self._mtimes(self._mtimes(Tt, kl), T)

    # ------------------------------------------------------------------
    def _resolver_sistema(self, K, F):
        """Eliminación gaussiana con pivoteo (matriz densa)."""
        n = len(F)
        M = [row[:] + [F[i]] for i, row in enumerate(K)]
        for col in range(n):
            piv = max(range(col, n), key=lambda r: abs(M[r][col]))
            if abs(M[piv][col]) < 1e-12:
                continue
            M[col], M[piv] = M[piv], M[col]
            pv = M[col][col]
            for r in range(col + 1, n):
                factor = M[r][col] / pv
                if factor == 0.0:
                    continue
                for c in range(col, n + 1):
                    M[r][c] -= factor * M[col][c]
        x = [0.0] * n
        for r in range(n - 1, -1, -1):
            if abs(M[r][r]) < 1e-12:
                x[r] = 0.0
                continue
            s = M[r][n] - sum(M[r][c] * x[c] for c in range(r + 1, n))
            x[r] = s / M[r][r]
        return x

    # ------------------------------------------------------------------
    def resolver(self) -> Dict[str, dict]:
        """
        Resuelve las solicitaciones para los casos de carga definidos en
        cada elemento ('carga' es la carga vertical uniforme en kgf/cm
        actuando hacia abajo) y las fuerzas laterales en nudos.

        Devuelve {nombre_caso: {'fuerzas': [...], 'reacciones': [...]}}.
        """
        n_nudos = len(self.nudos)
        ndof = 3 * n_nudos
        K = [[0.0] * ndof for _ in range(ndof)]
        for el in self.elementos:
            kg = self._k_global(el)
            gdof = [3 * el["i"], 3 * el["i"] + 1, 3 * el["i"] + 2,
                    3 * el["j"], 3 * el["j"] + 1, 3 * el["j"] + 2]
            for a in range(6):
                for b in range(6):
                    K[gdof[a]][gdof[b]] += kg[a][b]

        # vector de cargas por caso
        casos: Dict[str, List[float]] = {}
        for caso in self.casos:
            F = [0.0] * ndof
            for el in self.elementos:
                w = el.get(f"carga_{caso}", el.get("carga", 0.0))
                if abs(w) < 1e-12:
                    continue
                fem_local = [0.0, w * el["L"] / 2, w * el["L"] ** 2 / 12,
                             0.0, w * el["L"] / 2, -w * el["L"] ** 2 / 12]
                T = self._T(el["ang"])
                fem_glob = self._mv([[T[j][i] for j in range(6)] for i in range(6)],
                                    fem_local)
                # la carga actúa hacia abajo (-Z global): se invierte el signo
                gdof = [3 * el["i"], 3 * el["i"] + 1, 3 * el["i"] + 2,
                        3 * el["j"], 3 * el["j"] + 1, 3 * el["j"] + 2]
                for k in range(6):
                    F[gdof[k]] -= fem_glob[k]
            for nodo, (fx, fz) in self.cargas_nodales.get(caso, {}).items():
                F[3 * nodo] += fx
                F[3 * nodo + 1] += fz
            casos[caso] = F

        # reducir sistema (nudos fijos)
        libres = [i for n in range(n_nudos) for i in range(3 * n, 3 * n + 3)
                  if not self.restricciones[n][i - 3 * n]]
        mapa = {g: k for k, g in enumerate(libres)}
        Kred = [[K[g][h] for h in libres] for g in libres]

        resultados: Dict[str, dict] = {}
        for caso, F in casos.items():
            Fred = [F[g] for g in libres]
            u = self._resolver_sistema(Kred, Fred)
            uglob = [0.0] * ndof
            for g, k in mapa.items():
                uglob[g] = u[k]
            fuerzas = []
            for el in self.elementos:
                gdof = [3 * el["i"], 3 * el["i"] + 1, 3 * el["i"] + 2,
                        3 * el["j"], 3 * el["j"] + 1, 3 * el["j"] + 2]
                uloc = self._mv(self._T(el["ang"]), [uglob[g] for g in gdof])
                f = self._mv(self._k_local(el), uloc)   # fuerzas de extremo
                w = el.get(f"carga_{caso}", el.get("carga", 0.0))
                fem = [0.0, w * el["L"] / 2, w * el["L"] ** 2 / 12,
                       0.0, w * el["L"] / 2, -w * el["L"] ** 2 / 12]
                f_int = [f[k] - fem[k] for k in range(6)]
                fuerzas.append({"elemento": el["nombre"], "f": f_int, "w": w,
                                "carga": w})
            resultados[caso] = {"fuerzas": fuerzas, "u": uglob,
                                "reacciones": self._reacciones(K, uglob, F)}
        return resultados

    def _reacciones(self, K, u, F):
        r = self._mv(K, u)
        return [r[i] - F[i] for i in range(len(F))]

    casos: List[str] = []
    cargas_nodales: Dict[str, Dict[int, Tuple[float, float]]] = {}


# ===========================================================================
# Generación del modelo demo
# ===========================================================================
def crear_portico_demo(n_pisos: int = 4, n_vanos: int = 3, luz: float = 600.0,
                       altura: float = 320.0, bc: float = 45.0, hc: float = 45.0,
                       bv: float = 30.0, hv: float = 60.0,
                       fc: float = 210.0, wd: float = 3.2, wl: float = 1.8,
                       zona: float = 0.25, uso: float = 1.0, suelo: float = 1.05,
                       R: float = 6.0):
    """
    Construye un pórtico plano de concreto armado y resuelve los casos
    CM (carga muerta), CV (carga viva) y CSX (sismo en X según E.030).

    Retorna (portico, resultados).
    """
    p = PorticoPlano(fc)
    p.casos = ["CM", "CV", "CSX"]
    p.cargas_nodales = {"CM": {}, "CV": {}, "CSX": {}}

    # nudos
    ids = {}
    for s in range(n_pisos + 1):
        for v in range(n_vanos + 1):
            ids[(s, v)] = p.agregar_nudo(v * luz, s * altura, fijo=(s == 0))

    # elementos
    info_columnas = []
    info_vigas = []
    for s in range(n_pisos):
        for v in range(n_vanos + 1):
            idx = p.agregar_elemento(ids[(s, v)], ids[(s + 1, v)], bc, hc,
                                     nombre=f"C{s+1}-{v+1}")
            info_columnas.append({"idx": idx, "piso": s + 1, "eje": v + 1,
                                  "nombre": f"C{s+1}-{v+1}"})
    for s in range(1, n_pisos + 1):
        for v in range(n_vanos):
            idx = p.agregar_elemento(ids[(s, v)], ids[(s, v + 1)], bv, hv,
                                     nombre=f"V{s}-{v+1}")
            info_vigas.append({"idx": idx, "piso": s, "vano": v + 1,
                               "nombre": f"V{s}-{v+1}"})

    # cargas verticales (kgf/cm) sobre vigas
    for el in p.elementos:
        x1, z1 = p.nudos[el["i"]]
        x2, z2 = p.nudos[el["j"]]
        if abs(z2 - z1) < 1e-6:              # viga horizontal
            el["carga_CM"] = wd * 10.0            # tonf/m → kgf/cm
            el["carga_CV"] = wl * 10.0
            el["carga_CSX"] = 0.0
        else:
            el["carga_CM"] = 0.0
            el["carga_CV"] = 0.0
            el["carga_CSX"] = 0.0

    # peso sísmico y fuerzas laterales (E.030: V = Z·U·C·S/R · P)
    largo_total = n_vanos * luz / 100.0          # m de viga por piso
    peso_piso = [(wd + 0.25 * wl) * largo_total * 1000.0
                 for _ in range(n_pisos)]        # kgf
    peso_total = sum(peso_piso)
    V = zona * uso * 2.5 * suelo / R * peso_total
    numerador = sum((i + 1) * peso_piso[i] for i in range(len(peso_piso)))
    for i, peso in enumerate(peso_piso):
        fi = V * (i + 1) * peso / numerador if numerador > 0 else 0.0
        for v in range(n_vanos + 1):
            p.cargas_nodales["CSX"][ids[(i + 1, v)]] = (fi / (n_vanos + 1), 0.0)

    resultados = p.resolver()
    return p, resultados, info_vigas, info_columnas


# ===========================================================================
# Fuente demo
# ===========================================================================
class ETABSDemo(FuenteETABS):
    """Modelo de ejemplo (pórtico plano analizado por rigidez)."""

    nombre = "Modelo demo (pórtico 4 pisos)"
    descripcion = ("Ejemplo académico: análisis matricial de un pórtico plano "
                   "de 4 pisos y 3 vanos con combinaciones E.060/E.030.")

    def __init__(self, n_pisos: int = 4, n_vanos: int = 3):
        self.n_pisos = n_pisos
        self.n_vanos = n_vanos
        self._elementos: Dict[str, Elemento] = {}
        self._cargar()

    # ------------------------------------------------------------------
    def _cargar(self) -> None:
        portico, res, vigas, columnas = crear_portico_demo(
            n_pisos=self.n_pisos, n_vanos=self.n_vanos)
        combos = normas.combinaciones_e060(incluir_sismo=True, direcciones=("X",))
        casos = portico.casos
        nombres_combos = [c.nombre for c in combos]

        # --- vigas ------------------------------------------------------
        for info in vigas:
            el = portico.elementos[info["idx"]]
            nombre = info["nombre"]
            L = el["L"]
            n_est = 7
            puntos: List[PuntoDemanda] = []
            for k in range(n_est):
                x = L * k / (n_est - 1)
                fuerzas_por_caso = {}
                for caso in casos:
                    fz = res[caso]["fuerzas"][info["idx"]]
                    w = el.get(f"carga_{caso}", 0.0)
                    # momentos y cortantes internos a lo largo del elemento
                    m_i, v_i = fz["f"][2], fz["f"][1]
                    # equilibrio del tramo i–x (carga descendente w > 0)
                    Vx = -v_i - w * x
                    Mx = m_i - v_i * x - w * x * x / 2.0
                    N = 0.5 * (fz["f"][0] - fz["f"][3])   # compresión positiva
                    fuerzas_por_caso[caso] = (Vx, Mx, N)
                for combo in combos:
                    v2 = sum(combo.factores.get(c, 0.0) * fuerzas_por_caso[c][0]
                             for c in casos)
                    m3 = sum(combo.factores.get(c, 0.0) * fuerzas_por_caso[c][1]
                             for c in casos)
                    p_ax = sum(combo.factores.get(c, 0.0) * fuerzas_por_caso[c][2]
                               for c in casos)
                    puntos.append(PuntoDemanda(
                        combo=combo.nombre, estacion=x, P=p_ax, V2=v2,
                        V3=0.0, T=0.0, M2=0.0, M3=m3))
            self._elementos[nombre] = Elemento(
                nombre=nombre, tipo="Viga", seccion=f"{el['b']:.0f}x{el['h']:.0f}",
                story=f"Piso {info['piso']}", material="CONC",
                b=el["b"], h=el["h"], fc=portico.fc, fy=4200.0, L=L,
                puntos=puntos, unidad_fuerza="kgf", unidad_longitud="cm",
                origen="Modelo demo (análisis matricial)")

        # --- columnas ---------------------------------------------------
        for info in columnas:
            el = portico.elementos[info["idx"]]
            nombre = info["nombre"]
            L = el["L"]
            puntos = []
            for k in range(3):
                z = L * k / 2.0
                por_caso = {}
                for caso in casos:
                    f = res[caso]["fuerzas"][info["idx"]]["f"]
                    # axial y momento varían linealmente; se interpola
                    N = 0.5 * (f[0] - f[3])      # compresión positiva
                    M = f[2] - f[1] * z          # momento flector en la estación
                    por_caso[caso] = (N, M, f[1])
                for combo in combos:
                    N = sum(combo.factores.get(c, 0.0) * por_caso[c][0] for c in casos)
                    M = sum(combo.factores.get(c, 0.0) * por_caso[c][1] for c in casos)
                    V = sum(combo.factores.get(c, 0.0) * por_caso[c][2] for c in casos)
                    puntos.append(PuntoDemanda(
                        combo=combo.nombre, estacion=z, P=N, V2=V, V3=0.0,
                        T=0.0, M2=0.0, M3=M))
            self._elementos[nombre] = Elemento(
                nombre=nombre, tipo="Columna", seccion=f"{el['b']:.0f}x{el['h']:.0f}",
                story=f"Piso {info['piso']}", material="CONC",
                b=el["b"], h=el["h"], fc=portico.fc, fy=4200.0, L=L,
                puntos=puntos, unidad_fuerza="kgf", unidad_longitud="cm",
                origen="Modelo demo (análisis matricial)")
        self._combos = nombres_combos

    # ------------------------------------------------------------------
    def listar_elementos(self, solo_seleccionados: bool = False,
                         tipo: Optional[str] = None) -> List[str]:
        nombres = sorted(self._elementos)
        if tipo and tipo != "Todos":
            nombres = [n for n in nombres
                       if self._elementos[n].tipo.lower().startswith(tipo.lower())]
        return nombres

    def obtener_elemento(self, nombre: str) -> Elemento:
        if nombre not in self._elementos:
            raise KeyError(f"Elemento demo {nombre!r} inexistente.")
        return self._elementos[nombre]

    def listar_combos(self) -> List[str]:
        return list(self._combos)

    def info_modelo(self) -> dict:
        return {"fuente": self.nombre, "elementos": len(self._elementos),
                "combos": len(self._combos),
                "descripcion": self.descripcion}
