"""
Genera las tablas de ejemplo con el mismo formato que exporta ETABS
(Display > Tables, File > Export > Tables > to CSV).

Los tres archivos resultantes permiten probar la importación sin necesidad de
tener ETABS instalado:

    ElementForces_Frames.csv        → "Element Forces - Frames"
    FrameSections_Rectangular.csv   → "Frame Assignments - Section Properties"
                                      + "Frame Section Properties - Rectangular"
    MaterialProperties_Concrete.csv → "Material Properties - Concrete Data"

Ejecución (desde la raíz del proyecto):

    python ejemplos/generar_ejemplos.py
"""

from __future__ import annotations

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from e060.etabs import ETABSDemo  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))


def _fmt(v: float) -> str:
    return f"{v:.5f}".rstrip("0").rstrip(".")


def generar(elementos=("V1-2", "C1-1")):
    fuente = ETABSDemo()
    filas = ['"TABLE:  Element Forces - Frames"',
             '"Story","Frame","Station","Output Case","Case Type",'
             '"P (tonf)","V2 (tonf)","V3 (tonf)","T (tonf-m)","M2 (tonf-m)","M3 (tonf-m)"']
    secciones, dims = [], {}
    for nombre in elementos:
        el = fuente.obtener_elemento(nombre)
        dims[nombre] = (el.b, el.h)
        estaciones = sorted({round(p.estacion, 1) for p in el.puntos})
        for est in estaciones:
            for p in el.puntos:
                if abs(p.estacion - est) > 0.5:
                    continue
                filas.append(",".join([
                    f'"{el.story}"', f'"{nombre}"', _fmt(est / 100.0),
                    f'"{p.combo}"', '"Combination"',
                    _fmt(p.P / 1e3), _fmt(p.V2 / 1e3), _fmt(p.V3 / 1e3),
                    _fmt(p.T / 1e5), _fmt(p.M2 / 1e5), _fmt(p.M3 / 1e5)]))
    with open(os.path.join(AQUI, "ElementForces_Frames.csv"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\n".join(filas) + "\n")

    lineas = ['"TABLE:  Frame Assignments - Section Properties"',
              '"Story","Line","Frame","DesignSect","AnalysisSect"']
    for nombre in elementos:
        b, h = dims[nombre]
        sec = f"{'VP' if h >= b and nombre.startswith('V') else 'COL'} {b:.0f}x{h:.0f}"
        lineas.append(f'"Piso 1","{nombre}","{nombre}","{sec}","{sec}"')
    lineas += ['', '"TABLE:  Frame Section Properties - Rectangular"',
               '"PropName","Material","t3 (m)","t2 (m)"']
    for nombre in elementos:
        b, h = dims[nombre]
        sec = f"{'VP' if h >= b and nombre.startswith('V') else 'COL'} {b:.0f}x{h:.0f}"
        lineas.append(f'"{sec}","CONC",{h/100:.2f},{b/100:.2f}')
    with open(os.path.join(AQUI, "FrameSections_Rectangular.csv"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lineas) + "\n")

    with open(os.path.join(AQUI, "MaterialProperties_Concrete.csv"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write('"TABLE:  Material Properties - Concrete Data"\n'
                '"Material","f\'c (tonf/m2)"\n"CONC",2100\n')

    print("Archivos generados en", AQUI)


if __name__ == "__main__":
    generar()
