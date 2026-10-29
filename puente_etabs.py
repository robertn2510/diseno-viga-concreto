#!/usr/bin/env python3
"""
Puente local con ETABS v20 – v23.

Se ejecuta en el **mismo Windows donde está abierto ETABS** y hace una de dos
cosas, según el caso:

1. **Exportar** las solicitaciones del modelo (o de las barras seleccionadas) a
   los CSV que entiende la aplicación web.
2. **Enviar** esos CSV directamente al servidor del programa (por ejemplo, si
   la interfaz web corre en otro equipo o en un contenedor Linux).

Así se resuelve el caso habitual: ETABS solo existe en Windows, mientras que la
interfaz puede estar en otra máquina. La automatización COM/OAPI no es
necesaria en el servidor.

Instalación (en el Windows con ETABS):

    pip install comtypes

Ejemplos
--------
    # 1) exportar las barras seleccionadas en ETABS a la carpeta "salida"
    python puente_etabs.py --seleccionados --carpeta salida

    # 2) exportar todo el modelo y subirlo a la interfaz web
    python puente_etabs.py --carpeta salida --subir http://localhost:8000

    # 3) subirlo a la vista previa remota
    python puente_etabs.py --subir https://8000-<sandbox>.e2b.app

    # 4) probar el puente sin ETABS (modelo demo)
    python puente_etabs.py --demo --carpeta salida
"""

from __future__ import annotations

import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from e060.etabs.exportar import exportar_tablas, subir_tablas  # noqa: E402


def _fuente(args):
    if args.demo:
        from e060.etabs import ETABSDemo
        return ETABSDemo(), "Modelo demo (sin ETABS)"
    from e060.etabs.com import ConexionETABSError, diagnostico_com
    diag = diagnostico_com()
    if not diag["com_disponible"]:
        print("No es posible conectar con ETABS en este equipo:", file=sys.stderr)
        print(" ", diag["motivo"], file=sys.stderr)
        for i, sugerencia in enumerate(diag["sugerencias"], 1):
            print(f"  {i}. {sugerencia}", file=sys.stderr)
        if not diag["es_windows"]:
            print("\nSugerencia: use --demo para probar el puente, o exporte las "
                  "tablas desde ETABS y cárguelas con «Importar tablas».",
                  file=sys.stderr)
        raise SystemExit(2)
    from e060.etabs import conectar
    try:
        return conectar(adjuntar=True), "ETABS (COM/OAPI)"
    except ConexionETABSError as exc:
        print(f"No se pudo conectar con ETABS: {exc}", file=sys.stderr)
        for i, sugerencia in enumerate(exc.sugerencias, 1):
            print(f"  {i}. {sugerencia}", file=sys.stderr)
        raise SystemExit(2) from exc


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="puente_etabs.py",
        description="Exporta las solicitaciones de ETABS a CSV y, opcionalmente, "
                    "las envía a la aplicación web del diseñador E.060.")
    p.add_argument("--carpeta", default="salida", help="carpeta de salida de los CSV")
    p.add_argument("--seleccionados", action="store_true",
                   help="exporta solo las barras seleccionadas en ETABS")
    p.add_argument("--subir", metavar="URL",
                   help="envía los CSV a la interfaz web (p. ej. http://localhost:8000)")
    p.add_argument("--elemento", action="append", default=[],
                   help="elemento a exportar (puede repetirse); por defecto todos")
    p.add_argument("--demo", action="store_true",
                   help="usa el modelo demo en lugar de ETABS (prueba del puente)")
    args = p.parse_args(argv)

    fuente, etiqueta = _fuente(args)
    try:
        info = fuente.info_modelo()
    except Exception:                                # noqa: BLE001
        info = {}
    print(f"Fuente: {etiqueta}")
    for k in ("versión", "version", "modelo", "elementos"):
        if k in info:
            print(f"  {k}: {info[k]}")

    # filtro opcional de elementos
    if args.elemento:
        nombres = set(args.elemento)
        faltan = nombres - set(fuente.listar_elementos())
        if faltan:
            print(f"ERROR: no están en el modelo: {', '.join(sorted(faltan))}",
                  file=sys.stderr)
            return 2
        original = fuente.listar_elementos

        def listar(solo_seleccionados=False, tipo=None):
            return [n for n in original(solo_seleccionados=solo_seleccionados)
                    if n in nombres]
        fuente.listar_elementos = listar            # type: ignore[attr-defined]

    try:
        rutas = exportar_tablas(fuente, args.carpeta,
                                solo_seleccionados=args.seleccionados)
    except Exception as exc:                          # noqa: BLE001
        from e060.etabs.com import ConexionETABSError
        print(f"ERROR al exportar: {exc}", file=sys.stderr)
        if isinstance(exc, ConexionETABSError):
            for i, sugerencia in enumerate(exc.sugerencias, 1):
                print(f"  {i}. {sugerencia}", file=sys.stderr)
        return 2
    for clave, ruta in rutas.items():
        print(f"  {clave:10s} → {ruta}")

    if args.subir:
        try:
            datos = subir_tablas(args.subir, rutas,
                                 campos={"tipo_defecto": "auto"})
        except Exception as exc:                      # noqa: BLE001
            print(f"ERROR al enviar a {args.subir}: {exc}", file=sys.stderr)
            print("Los CSV quedaron guardados en "
                  f"{os.path.abspath(args.carpeta)}; cárguelos con «Importar tablas».",
                  file=sys.stderr)
            return 3
        if datos.get("ok"):
            print(f"Importado en la interfaz web como fuente '{datos.get('fuente_id')}'."
                  f"\n  {datos.get('info', {})}")
        else:
            print(f"El servidor respondió: {datos}", file=sys.stderr)
            return 3
    else:
        print("\nCargue estos archivos en la interfaz con «Importar tablas de ETABS».")

    # cierre ordenado de la conexión COM
    try:
        fuente.cerrar()                               # type: ignore[attr-defined]
    except Exception:                                 # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
