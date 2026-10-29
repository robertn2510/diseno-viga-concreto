"""
Interfaz de línea de comandos del motor de diseño E.060.

Permite diseñar un elemento de ETABS (o del modelo demo) sin abrir la
interfaz gráfica, y es útil para generar memorias en lote.

Ejemplos
--------
    # lista los elementos del modelo demo
    python -m e060.cli --demo --listar

    # diseña una viga del demo y genera HTML + PDF
    python -m e060.cli --demo --elemento V1-2 --pdf salidas/V1-2.pdf

    # diseña un elemento importado de tablas de ETABS
    python -m e060.cli --fuerzas ejemplos/ElementForces_Frames.csv \
        --secciones ejemplos/FrameSections_Rectangular.csv \
        --materiales ejemplos/MaterialProperties_Concrete.csv \
        --elemento C1-1 --html salidas/C1-1.html

    # diseña todos los elementos y guarda una memoria HTML por elemento
    python -m e060.cli --demo --todos --carpeta salidas/memorias
"""

from __future__ import annotations

import argparse
import os
import sys

from . import memoria, servicio
from .etabs import ETABSDemo, ETABSTablas


def _fuente(args):
    if args.fuerzas:
        fuente = ETABSTablas.desde_archivos(args.fuerzas, args.secciones, args.materiales)
    elif args.etabs:
        from .etabs import conectar
        fuente = conectar(adjuntar=True)
    else:
        fuente = ETABSDemo()
    return fuente


def _opciones(args) -> servicio.OpcionesDiseno:
    return servicio.OpcionesDiseno(
        sismico=not args.no_sismico,
        recubrimiento=args.recubrimiento,
        n_estaciones=args.estaciones,
        amplificar_esbeltez=args.esbeltez,
        proyecto=args.proyecto,
        autor=args.autor,
        b=args.b, h=args.h, fc=args.fc, fy=args.fy,
        tipo=args.tipo,
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m e060.cli",
        description="Diseño de vigas y columnas de concreto armado según la NTP E.060 "
                    "(RNE, Perú) a partir de ETABS v20–v23.")
    p.add_argument("--demo", action="store_true", help="usa el modelo demo (sin ETABS)")
    p.add_argument("--etabs", action="store_true", help="conecta con ETABS abierto (COM, Windows)")
    p.add_argument("--fuerzas", help="CSV de 'Element Forces - Frames' exportado de ETABS")
    p.add_argument("--secciones", help="CSV de secciones (opcional)")
    p.add_argument("--materiales", help="CSV de materiales (opcional)")
    p.add_argument("--elemento", help="nombre del elemento a diseñar (p. ej. V1-2)")
    p.add_argument("--todos", action="store_true", help="diseña todos los elementos")
    p.add_argument("--listar", action="store_true", help="lista los elementos disponibles")
    p.add_argument("--carpeta", help="carpeta donde guardar las memorias (HTML)")
    p.add_argument("--html", help="archivo HTML de salida")
    p.add_argument("--pdf", help="archivo PDF de salida")
    p.add_argument("--md", dest="markdown", help="archivo Markdown de salida")
    p.add_argument("--proyecto", default="Proyecto")
    p.add_argument("--autor", default="Ing. Estructural")
    p.add_argument("--tipo", default="auto", choices=["auto", "Viga", "Columna"])
    p.add_argument("--recubrimiento", type=float, default=4.0, help="recubrimiento libre [cm]")
    p.add_argument("--estaciones", type=int, default=5, help="estaciones de diseño por elemento")
    p.add_argument("--esbeltez", action="store_true", help="amplificar momentos por esbeltez (10.10.7)")
    p.add_argument("--no-sismico", action="store_true", help="omite los requisitos del capítulo 21")
    p.add_argument("--b", type=float, help="ancho [cm] (sobrescribe el del modelo)")
    p.add_argument("--h", type=float, help="peralte [cm] (sobrescribe el del modelo)")
    p.add_argument("--fc", type=float, help="f'c [kgf/cm²]")
    p.add_argument("--fy", type=float, help="fy [kgf/cm²]")
    args = p.parse_args(argv)

    try:
        fuente = _fuente(args)
    except Exception as exc:                        # noqa: BLE001
        print(f"ERROR al abrir la fuente: {exc}", file=sys.stderr)
        return 2

    nombres = fuente.listar_elementos()
    if args.listar or (not args.elemento and not args.todos):
        info = fuente.info_modelo() if hasattr(fuente, "info_modelo") else {}
        print(f"Fuente: {info.get('fuente', type(fuente).__name__)}")
        for k, v in info.items():
            if k != "fuente":
                print(f"  {k}: {v}")
        print(f"\nElementos ({len(nombres)}):")
        for n in nombres:
            try:
                el = fuente.obtener_elemento(n)
                print(f"  {n:10s} {el.tipo:10s} {el.b:.0f}x{el.h:.0f} cm  "
                      f"L={el.L:.0f} cm  f'c={el.fc:.0f}  {len(el.combos)} combinaciones")
            except Exception:                        # noqa: BLE001
                print(f"  {n}")
        if not args.listar:
            print("\nIndique --elemento NOMBRE o --todos para diseñar.")
        return 0

    if args.elemento:
        if args.elemento not in nombres:
            print(f"ERROR: '{args.elemento}' no está en la fuente. Use --listar.",
                  file=sys.stderr)
            return 2
        objetivo = [args.elemento]
    else:
        objetivo = nombres

    os.makedirs(args.carpeta or ".", exist_ok=True)
    fallos = 0
    for nombre in objetivo:
        out = servicio.disenar_elemento(fuente.obtener_elemento(nombre), _opciones(args))
        doc = memoria.construir_memoria(out)
        res = out["resumen"]
        ok = servicio.aprobado(out)
        fallos += 0 if ok else 1
        if out["tipo"] == "Viga":
            detalle = (f"{res['filas'][0]['ref_neg']} / {res['filas'][0]['ref_pos']} · "
                       f"estribos {res['corte_gobernante']['estribo']} "
                       f"@{res['corte_gobernante']['s_conf']:g}/{res['corte_gobernante']['s_resto']:g} cm")
        else:
            detalle = f"{res['refuerzo']} · ρ={res['rho']*100:.2f}% · D/C={res['dcr']:.3f}"
        print(f"{'OK ' if ok else 'REV'} {nombre:8s} {out['tipo']:8s} {detalle}")
        if args.html:
            memoria.guardar_html(out, args.html if len(objetivo) == 1
                                 else os.path.join(args.carpeta or ".", f"{nombre}.html"))
        if args.markdown:
            memoria.guardar_markdown(out, args.markdown if len(objetivo) == 1
                                     else os.path.join(args.carpeta or ".", f"{nombre}.md"))
        if args.pdf:
            ruta = args.pdf if len(objetivo) == 1 else os.path.join(
                args.carpeta or ".", f"{nombre}.pdf")
            if not memoria.guardar_pdf(out, ruta):
                print("  (PDF no generado: instale 'reportlab')", file=sys.stderr)
        if args.carpeta and not (args.html or args.pdf or args.markdown):
            memoria.guardar_html(out, os.path.join(args.carpeta, f"{nombre}.html"))
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
