"""
Modelo de datos común para elementos importados de ETABS.

Cualquier fuente (COM/OAPI, tablas exportadas o el modelo demo) produce
objetos Elemento con solicitaciones ya convertidas a las unidades internas
del motor (kgf, cm, kgf·cm).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


# ===========================================================================
# Solicitaciones
# ===========================================================================
@dataclass
class PuntoDemanda:
    """Solicitación en una estación de un elemento."""
    combo: str
    estacion: float = 0.0        # [cm] medida desde el extremo i
    P: float = 0.0               # [kgf] (+ compresión)
    V2: float = 0.0              # [kgf]
    V3: float = 0.0              # [kgf]
    T: float = 0.0               # [kgf·cm]
    M2: float = 0.0              # [kgf·cm]
    M3: float = 0.0              # [kgf·cm]

    def clave(self) -> Tuple[int]:
        return (round(self.estacion, 1), self.combo)

    @property
    def M_max(self) -> float:
        return max(abs(self.M2), abs(self.M3))


@dataclass
class Elemento:
    """Viga o columna importada de ETABS."""
    nombre: str
    tipo: str                     # 'Viga' | 'Columna' | 'Desconocido'
    seccion: str = ""
    story: str = ""
    material: str = ""
    b: float = 0.0                # [cm]
    h: float = 0.0                # [cm]
    fc: float = 210.0             # [kgf/cm²]
    fy: float = 4200.0            # [kgf/cm²]
    L: float = 0.0                # [cm] longitud del elemento
    puntos: List[PuntoDemanda] = field(default_factory=list)
    unidad_fuerza: str = "tonf"
    unidad_longitud: str = "m"
    origen: str = ""
    extras: Dict[str, object] = field(default_factory=dict)

    # ------------------------------------------------------------------
    @property
    def estaciones(self) -> List[float]:
        return sorted({round(p.estacion, 1) for p in self.puntos})

    @property
    def combos(self) -> List[str]:
        vistos = []
        for p in self.puntos:
            if p.combo not in vistos:
                vistos.append(p.combo)
        return vistos

    @property
    def dimensiones_validas(self) -> bool:
        return self.b > 5 and self.h > 5

    def puntos_en(self, estacion: float, tol: float = 2.0) -> List[PuntoDemanda]:
        return [p for p in self.puntos if abs(p.estacion - estacion) <= tol]

    def estaciones_clave(self, n_max: int = 5) -> List[float]:
        ests = self.estaciones
        if not ests:
            return [0.0]
        if len(ests) <= n_max:
            return ests
        # toma extremos, centro y puntos intermedios equiespaciados
        objetivo = [ests[0], ests[-1], ests[len(ests) // 2]]
        for e in ests:
            if len(objetivo) >= n_max:
                break
            if all(abs(e - o) > 1.0 for o in objetivo):
                objetivo.append(e)
        return sorted(objetivo)

    # ------------------------------------------------------------------
    def envolventes(self) -> List[dict]:
        """
        Envolvente por estación: momentos positivos y negativos máximos,
        cortante máximo y torsor máximo, con la combinación que los produce.
        """
        resultado = []
        for est in self.estaciones:
            pts = self.puntos_en(est)
            if not pts:
                continue
            pos = max(pts, key=lambda p: p.M3 if self.tipo == "Viga" else p.M3)
            neg = min(pts, key=lambda p: p.M3 if self.tipo == "Viga" else p.M3)
            m_pos = max(0.0, pos.M3)
            m_neg = abs(min(0.0, neg.M3))
            corte = max(pts, key=lambda p: abs(p.V2))
            torsor = max(pts, key=lambda p: abs(p.T))
            axial = max(pts, key=lambda p: abs(p.P))
            resultado.append({
                "estacion": est,
                "Mu_pos": m_pos, "combo_pos": pos.combo if m_pos > 0 else "",
                "Mu_neg": m_neg, "combo_neg": neg.combo if m_neg > 0 else "",
                "Vu": abs(corte.V2), "combo_Vu": corte.combo,
                "Tu": abs(torsor.T), "combo_Tu": torsor.combo,
                "Pu": axial.P, "combo_Pu": axial.combo,
                "M2_pos": max((p.M2 for p in pts), default=0.0),
                "M2_neg": min((p.M2 for p in pts), default=0.0),
            })
        return resultado

    def diagrama_m3(self) -> Tuple[List[float], List[float]]:
        """Envolvente de M3 a lo largo del elemento (para gráficos)."""
        xs, ys = [], []
        for env in self.envolventes():
            xs.append(env["estacion"] / 100.0)
            ys.extend([env["Mu_pos"] / 1e5, -env["Mu_neg"] / 1e5])
        # se reconstruye como dos curvas
        return xs, ys

    def resumen(self) -> dict:
        envs = self.envolventes()
        return {
            "nombre": self.nombre, "tipo": self.tipo, "seccion": self.seccion,
            "story": self.story, "b": self.b, "h": self.h,
            "fc": self.fc, "fy": self.fy, "L": self.L,
            "n_combos": len(self.combos), "combos": self.combos,
            "n_estaciones": len(envs),
            "Mu_pos_max": max((e["Mu_pos"] for e in envs), default=0.0),
            "Mu_neg_max": max((e["Mu_neg"] for e in envs), default=0.0),
            "Vu_max": max((e["Vu"] for e in envs), default=0.0),
            "Tu_max": max((e["Tu"] for e in envs), default=0.0),
            "Pu_max": max((e["Pu"] for e in envs), default=0.0, key=abs),
            "Pu_min": min((e["Pu"] for e in envs), default=0.0),
        }

    def validar(self) -> List[str]:
        errores = []
        if not self.dimensiones_validas:
            errores.append(f"Dimensiones no válidas: b={self.b:.1f} cm, h={self.h:.1f} cm")
        if not self.puntos:
            errores.append("El elemento no tiene solicitaciones importadas.")
        if self.fc < 170:
            errores.append(f"f'c = {self.fc:.0f} kgf/cm² es menor que el mínimo de 170 kgf/cm² (E.060 5.1.1).")
        if self.fy < 2100:
            errores.append(f"fy = {self.fy:.0f} kgf/cm² parece incorrecto.")
        return errores


# ===========================================================================
# Fuente de datos (interfaz común)
# ===========================================================================
class FuenteETABS:
    """Interfaz que implementan los conectores."""
    nombre = "ETABS"
    descripcion = ""

    def listar_elementos(self, solo_seleccionados: bool = False,
                         tipo: Optional[str] = None) -> List[str]:
        raise NotImplementedError

    def obtener_elemento(self, nombre: str) -> Elemento:
        raise NotImplementedError

    def listar_combos(self) -> List[str]:
        raise NotImplementedError

    def info_modelo(self) -> dict:
        return {"fuente": self.nombre, "descripcion": self.descripcion}

    def cerrar(self) -> None:
        pass


# ===========================================================================
# Utilidades de filtrado y clasificación
# ===========================================================================
def clasificar_elemento(nombre: str, b: float, h: float) -> str:
    """
    Heurística para clasificar una barra como viga o columna cuando ETABS no
    informa la orientación de diseño. Se puede corregir desde la interfaz.
    """
    return "Desconocido"


def filtrar(elementos: Sequence[Elemento], tipo: Optional[str] = None,
            texto: Optional[str] = None) -> List[Elemento]:
    salida = list(elementos)
    if tipo and tipo != "Todos":
        salida = [e for e in salida if e.tipo.lower().startswith(tipo.lower())]
    if texto:
        t = texto.lower()
        salida = [e for e in salida if t in e.nombre.lower() or t in e.seccion.lower()
                  or t in e.story.lower()]
    return salida
