"""
Exportación de tablas desde cualquier fuente ETABS a los CSV que el programa
puede reimportar ("Element Forces - Frames", secciones y materiales).

Se usa para dos casos:

* **Puente local** (`puente_etabs.py`): en el mismo Windows donde corre ETABS
  se leen los elementos por COM/OAPI y se escriben los CSV, que luego se cargan
  en la aplicación web (que puede estar en otra máquina, incluso Linux).
* **Respaldo de resultados**: guardar las solicitaciones usadas en el diseño
  junto con la memoria, para auditoría o revisión por terceros.

Los archivos generados siguen el formato de exportación de ETABS, de modo que
`ETABSTablas.desde_archivos()` los lee sin ninguna conversión previa.
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Sequence

CAB_FUERZAS = ('"Story","Frame","Station","Output Case","Case Type",'
               '"P (tonf)","V2 (tonf)","V3 (tonf)","T (tonf-m)",'
               '"M2 (tonf-m)","M3 (tonf-m)"')


def _num(v: float, decimales: int = 5) -> str:
    """Número en formato ETABS (sin ceros finales innecesarios)."""
    texto = f"{float(v):.{decimales}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto or "0"


def _abreviatura(tipo: str, b: float, h: float) -> str:
    return "COL" if str(tipo).lower().startswith("col") else "VP"


def nombre_seccion(el) -> str:
    """Nombre determinista de sección a partir del tipo y las dimensiones."""
    return f"{_abreviatura(el.tipo, el.b, el.h)} {el.b:.0f}x{el.h:.0f}"


def exportar_tablas(fuente, carpeta: str = ".",
                    solo_seleccionados: bool = False,
                    prefijo: str = "") -> Dict[str, str]:
    """
    Escribe los tres CSV de ETABS a partir de una fuente ya cargada.

    Devuelve las rutas: {'fuerzas': ..., 'secciones': ..., 'materiales': ...}.
    """
    os.makedirs(carpeta, exist_ok=True)
    nombres = fuente.listar_elementos(solo_seleccionados=solo_seleccionados)
    if not nombres:
        raise ValueError("La fuente no devolvió elementos para exportar.")

    filas = ['"TABLE:  Element Forces - Frames"', CAB_FUERZAS]
    secciones: Dict[str, tuple] = {}
    elementos = []
    for nombre in nombres:
        el = fuente.obtener_elemento(nombre)
        elementos.append(el)
        sec = nombre_seccion(el)
        secciones.setdefault(sec, (el.b, el.h, el.fc))
        puntos = sorted(el.puntos, key=lambda p: (p.estacion, p.combo))
        for p in puntos:
            filas.append(",".join([
                f'"{el.story or "Story1"}"', f'"{nombre}"',
                _num(p.estacion / 100.0, 4),
                f'"{p.combo}"', '"Combination"',
                _num(p.P / 1e3), _num(p.V2 / 1e3), _num(p.V3 / 1e3),
                _num(p.T / 1e5), _num(p.M2 / 1e5), _num(p.M3 / 1e5)]))

    ruta_f = os.path.join(carpeta, f"{prefijo}ElementForces_Frames.csv")
    with open(ruta_f, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(filas) + "\n")

    lin = ['"TABLE:  Frame Assignments - Section Properties"',
           '"Story","Line","Frame","DesignSect","AnalysisSect"']
    for el in elementos:
        sec = nombre_seccion(el)
        lin.append(f'"{el.story or "Story1"}","{el.nombre}","{el.nombre}",'
                   f'"{sec}","{sec}"')
    lin += ['', '"TABLE:  Frame Section Properties - Rectangular"',
            '"PropName","Material","t3 (m)","t2 (m)"']
    for sec, (b, h, fc) in secciones.items():
        lin.append(f'"{sec}","{_material(fc)}",{h/100:.4f},{b/100:.4f}')
    ruta_s = os.path.join(carpeta, f"{prefijo}FrameSections_Rectangular.csv")
    with open(ruta_s, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lin) + "\n")

    lin = ['"TABLE:  Material Properties - Concrete Data"',
           '"Material","f\'c (tonf/m2)"']
    for fc in sorted({round(f, 1) for _, _, f in secciones.values()}):
        lin.append(f'"{_material(fc)}",{fc*10:.1f}')
    ruta_m = os.path.join(carpeta, f"{prefijo}MaterialProperties_Concrete.csv")
    with open(ruta_m, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lin) + "\n")

    return {"fuerzas": ruta_f, "secciones": ruta_s, "materiales": ruta_m}


def _material(fc: float) -> str:
    """Nombre de material coherente con el valor de f'c (kgf/cm²)."""
    return f"CONC{fc:.0f}"


def subir_tablas(url: str, rutas: Dict[str, str], timeout: float = 60.0,
                 campos: Optional[Dict[str, str]] = None) -> dict:
    """
    Envía los CSV al servidor del programa (`POST /api/importar`, multipart).

    `url` es la dirección base del servidor, p. ej.
    ``https://<puerto>-<sandbox>.e2b.app`` o ``http://localhost:8000``.
    """
    import json
    import os
    import urllib.request

    limite = "----e060" + os.urandom(8).hex()
    partes = []
    for clave in ("fuerzas", "secciones", "materiales"):
        ruta = rutas.get(clave)
        if not ruta or not os.path.isfile(ruta):
            continue
        with open(ruta, "rb") as fh:
            contenido = fh.read()
        partes.append(
            f"--{limite}\r\n"
            f'Content-Disposition: form-data; name="{clave}"; '
            f'filename="{os.path.basename(ruta)}"\r\n'
            f"Content-Type: text/csv\r\n\r\n".encode("utf-8")
            + contenido + b"\r\n")
    for nombre, valor in (campos or {}).items():
        if valor in (None, ""):
            continue
        partes.append(f"--{limite}\r\n"
                      f'Content-Disposition: form-data; name="{nombre}"\r\n\r\n'
                      f"{valor}\r\n".encode("utf-8"))
    partes.append(f"--{limite}--\r\n".encode("utf-8"))
    cuerpo = b"".join(partes)

    destino = url.rstrip("/") + "/api/importar"
    peticion = urllib.request.Request(
        destino, data=cuerpo, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={limite}",
                 "Content-Length": str(len(cuerpo))})
    with urllib.request.urlopen(peticion, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))
