"""
Combinaciones de carga y envolventes (E.060 9.2 / E.030).

ETABS entrega las solicitaciones por combinación; este módulo permite además
construir combinaciones propias a partir de casos simples (CM, CV, CSX, CSY)
y calcular envolventes con la combinación que gobierna cada estado.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence

from .normas import Combinacion, combinaciones_e060  # re-export


def evaluar(combos: Sequence[Combinacion], casos: Dict[str, float]) -> Dict[str, float]:
    """Evalúa una lista de combinaciones para un conjunto de casos de carga."""
    return {c.nombre: c.evaluar(casos) for c in combos}


def envolvente(registros: Sequence[dict], campos: Sequence[str]) -> Dict[str, dict]:
    """
    Envolvente de una lista de registros.

    Cada registro es un dict con una clave 'combo' y los campos numéricos.
    Devuelve, por campo, el máximo absoluto con signo y la combinación que lo
    produce: {'campo': {'max': v, 'min': v, 'combo_max': s, 'combo_min': s}}.
    """
    salida: Dict[str, dict] = {}
    for campo in campos:
        mejor_max = None
        mejor_min = None
        for reg in registros:
            v = reg.get(campo)
            if v is None:
                continue
            if mejor_max is None or v > mejor_max[0]:
                mejor_max = (v, reg.get("combo", ""))
            if mejor_min is None or v < mejor_min[0]:
                mejor_min = (v, reg.get("combo", ""))
        if mejor_max is None:
            continue
        salida[campo] = {
            "max": mejor_max[0], "min": mejor_min[0],
            "combo_max": mejor_max[1], "combo_min": mejor_min[1],
            "abs": max(abs(mejor_max[0]), abs(mejor_min[0])),
        }
    return salida


def escalar_por_combinacion(valores: Dict[str, float],
                            combo: Combinacion) -> float:
    """Aplica los factores de una combinación a valores por caso de carga."""
    return combo.evaluar(valores)


def es_combinacion_sismica(nombre: str) -> bool:
    """Heurística para reconocer combinaciones con sismo en el nombre."""
    n = nombre.lower()
    return any(k in n for k in ("sismo", "csx", "csy", "eqx", "eqy", "spec",
                                "sísm", "sis", "quake", "0.9cm"))


def factor_de_caso(nombre_combo: str, caso: str) -> Optional[float]:
    """Extrae el factor de un caso dentro del nombre de una combinación de ETABS."""
    import re
    nombre = nombre_combo.replace(" ", "").upper()
    patron = rf"([0-9]*\.?[0-9]+)\*?{re.escape(caso.upper())}"
    m = re.search(patron, nombre)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


__all__ = ["Combinacion", "combinaciones_e060", "evaluar", "envolvente",
           "escalar_por_combinacion", "es_combinacion_sismica", "factor_de_caso"]
