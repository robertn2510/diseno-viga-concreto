"""
Interfaz de línea de comandos.

Ejemplos
--------
    python main.py --demo
    python main.py --listar
    python main.py --seccion VP-25x50 --piso "Piso 2" --salida salidas
    python main.py --vigas V-101,V-102 --formato ambos --proyecto "Edificio A"
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date
from typing import Any

from .calculo.diseno import disenar_viga
from .config import ConfiguracionDiseno
from .demo import ejecutar_demo
from .etabs.api import ETABSError, ETABSSinResultados
from .etabs.combos import (
    combo_gravedad,
    crear_combinaciones,
    detectar_casos_carga,
    generar_combos_requeridas,
    mapas_combo_extraccion,
    verificar_combinaciones,
)
from .etabs.conexion import conectar_etabs
from .etabs.extraccion import (
    extraer_fuerzas,
    extraer_vigas,
    listar_resumen_vigas,
)
from .modelos import MetadatosProyecto, ResultadoViga
from .reporte import generar_reporte


def _parse_lista(valor: str | None) -> tuple[str, ...]:
    if not valor:
        return ()
    return tuple(x.strip() for x in valor.split(",") if x.strip())


def _config_desde_args(args: argparse.Namespace) -> ConfiguracionDiseno:
    formatos = ("md", "docx") if args.formato == "ambos" else (args.formato,)
    cfg = ConfiguracionDiseno(
        fc_default=args.fc if args.fc is not None else 210.0,
        fy_default=args.fy if args.fy is not None else 4200.0,
        fyt_default=args.fy if args.fy is not None else 4200.0,
        recubrimiento_libre_cm=args.recubrimiento,
        usar_recubrimiento_etabs=args.usar_recubrimiento_etabs,
        estribo=args.estribo,
        fraccion_rho_b=args.fraccion_rho_b,
        norma_combinaciones=args.norma_combos,
        caso_muerta=args.caso_muerta or "",
        caso_viva=args.caso_viva or "",
        casos_sismo=_parse_lista(args.caso_sismo),
        usar_vc_cero_sismo=not args.sin_vc_cero,
        p_compresion_negativa=not args.axial_positivo_compresion,
        crear_combos_faltantes=args.crear_combos,
        analizar_si_crea=args.analizar,
        vigas=_parse_lista(args.vigas),
        secciones=_parse_lista(args.seccion),
        pisos=_parse_lista(args.piso),
        max_vigas=args.max_vigas,
        formatos=formatos,
        directorio_salida=args.salida,
        proyecto=args.proyecto,
        ubicacion=args.ubicacion,
        ingeniero=args.ingeniero,
        cliente=args.cliente,
        revision=args.revision,
        forzar_fc=args.fc is not None,
    )
    return cfg


def _imprimir_tabla(filas: list[dict[str, Any]]) -> None:
    if not filas:
        print("  (sin datos)")
        return
    encabezados = list(filas[0].keys())
    anchos = {
        h: max(len(str(h)), *(len(str(f.get(h, ""))) for f in filas))
        for h in encabezados
    }
    linea = "  ".join(str(h).ljust(anchos[h]) for h in encabezados)
    print(linea)
    print("  ".join("-" * anchos[h] for h in encabezados))
    for f in filas:
        print("  ".join(str(f.get(h, "")).ljust(anchos[h]) for h in encabezados))


def _resumen_resultados(resultados: list[ResultadoViga]) -> list[dict[str, Any]]:
    filas = []
    for r in resultados:
        c = r.cortante
        filas.append({
            "Viga": r.viga.id,
            "Piso": r.viga.piso,
            "b×h": f"{r.viga.geometria.b:.0f}×{r.viga.geometria.h:.0f}",
            "M+ (t·m)": f"{r.fuerzas.M_pos_max_tm:.2f}",
            "M− (t·m)": f"{r.fuerzas.M_neg_max_tm:.2f}",
            "V (t)": f"{r.fuerzas.V_max_t:.2f}",
            "Sup. apoyo": (
                r.por_ubicacion("Apoyo izquierdo (cara)", "superior").seleccion.etiqueta
                if r.por_ubicacion("Apoyo izquierdo (cara)", "superior")
                and r.por_ubicacion("Apoyo izquierdo (cara)", "superior").seleccion
                else "—"
            ),
            "Inf. centro": (
                r.por_ubicacion("Centro", "inferior").seleccion.etiqueta
                if r.por_ubicacion("Centro", "inferior")
                and r.por_ubicacion("Centro", "inferior").seleccion
                else "—"
            ),
            "Estribado (izq. | resto | der.)": c.distribucion_completa if c else "—",
            "Estado": "CUMPLE" if r.cumple else "REVISAR",
        })
    return filas


def _crear_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vigas-e060",
        description=(
            "Diseño de vigas de concreto armado según la NTE E.060 del Perú, "
            "con extracción de fuerzas desde ETABS v18–v23."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python main.py --demo\n"
            "  python main.py --listar\n"
            "  python main.py --seccion VP-25x50 --piso 'Piso 2'\n"
            "  python main.py --vigas V-101,V-102 --formato ambos\n"
        ),
    )
    p.add_argument("--demo", action="store_true", help="Ejecuta un caso sintético sin ETABS.")
    p.add_argument("--listar", action="store_true", help="Lista las vigas del modelo y sale.")
    p.add_argument("--crear-instancia", action="store_true", help="Crea una instancia nueva de ETABS.")
    p.add_argument("--ruta-etabs", help="Ruta de ETABS.exe si se crea una instancia.")
    p.add_argument("--pywin32", action="store_true", help="Usa pywin32 en lugar de comtypes.")
    p.add_argument("--modelo", help="Archivo .edb a abrir después de conectar.")
    p.add_argument("--vigas", help="Nombres o etiquetas de vigas separadas por coma.")
    p.add_argument("--seccion", help="Filtro por nombre de sección (coma).")
    p.add_argument("--piso", help="Filtro por piso (coma).")
    p.add_argument("--caso-muerta", help="Nombre del caso de carga muerta (si no se detecta).")
    p.add_argument("--caso-viva", help="Nombre del caso de carga viva.")
    p.add_argument("--caso-sismo", help="Casos sísmicos separados por coma.")
    p.add_argument("--fc", type=float, help="f'c en kgf/cm²; fuerza este valor en todas las vigas.")
    p.add_argument("--fy", type=float, default=4200.0, help="fy en kgf/cm² (por defecto 4200).")
    p.add_argument("--recubrimiento", type=float, default=4.0, help="Recubrimiento libre al estribo (cm).")
    p.add_argument(
        "--usar-recubrimiento-etabs", action="store_true",
        help="Usa el recubrimiento al centroide definido en ETABS para estimar r.",
    )
    p.add_argument("--estribo", default='3/8"', help="Diámetro de estribo (por defecto 3/8\").")
    p.add_argument("--fraccion-rho-b", type=float, default=0.75, help="Fracción de ρb (0.50 o 0.75).")
    p.add_argument(
        "--norma-combos",
        choices=("usuario", "e060-2009"),
        default="usuario",
        help="Variante de combinación sísmica: 1.25S (usuario) o 1.0S (E.060 2009).",
    )
    p.add_argument(
        "--sin-vc-cero", action="store_true",
        help="No reduce Vc a cero en la zona de confinamiento (E.060 21.5.4.2).",
    )
    p.add_argument(
        "--axial-positivo-compresion", action="store_true",
        help="Interpreta P > 0 de ETABS como compresión (por defecto P < 0 es compresión).",
    )
    p.add_argument("--crear-combos", action="store_true", help="Crea en ETABS las combinaciones faltantes.")
    p.add_argument("--analizar", action="store_true", help="Ejecuta el análisis después de crear combos.")
    p.add_argument("--salida", default="salidas", help="Directorio de salida de la memoria.")
    p.add_argument("--formato", choices=("md", "docx", "ambos"), default="ambos", help="Formato de memoria.")
    p.add_argument("--proyecto", default="Proyecto estructural")
    p.add_argument("--ubicacion", default="Perú")
    p.add_argument("--ingeniero", default="Ingeniero estructural")
    p.add_argument("--cliente", default="")
    p.add_argument("--revision", default="A")
    p.add_argument("--max-vigas", type=int, help="Limita el número de vigas procesadas.")
    p.add_argument("--verbose", action="store_true", help="Muestra la traza completa de errores.")
    return p


def _flujo_demo(args: argparse.Namespace, config: ConfiguracionDiseno) -> int:
    print("=" * 78)
    print(" MODO DEMOSTRACIÓN — datos sintéticos (no requiere ETABS)")
    print("=" * 78)
    resultados, salidas = ejecutar_demo(
        salida=args.salida,
        formatos=config.formatos,
        config=config,
    )
    print("\nResumen de diseño:")
    _imprimir_tabla(_resumen_resultados(resultados))
    print("\nArchivos generados:")
    for k, v in salidas.items():
        if k in {"md", "docx"}:
            print(f"  {k.upper()}: {v}")
    for e in salidas.get("errores", []):
        print(f"  ADVERTENCIA: {e}")
    return 0


def _flujo_etabs(args: argparse.Namespace, config: ConfiguracionDiseno) -> int:
    print("=" * 78)
    print(" DISEÑO DE VIGAS E.060 — CONEXIÓN ETABS")
    print("=" * 78)

    conexion = conectar_etabs(
        modo="crear" if args.crear_instancia else "adjuntar",
        ruta_etabs=args.ruta_etabs,
        usar_pywin32=args.pywin32,
        abrir_modelo=args.modelo,
        cerrar_al_salir=args.crear_instancia,
    )
    info = conexion.info
    print(f"ETABS: {info.version}  |  API: {info.api}")
    print(f"Modelo: {info.modelo or '(sin nombre)'}")
    if info.bloqueado:
        print("Aviso: el modelo está bloqueado (analysis locked).")
    for adv in info.advertencias:
        print(f"Advertencia: {adv}")

    try:
        vigas = extraer_vigas(conexion, config)
        if args.listar:
            print("\nVigas detectadas:")
            _imprimir_tabla(listar_resumen_vigas(vigas))
            return 0
        if not vigas:
            print("No se encontraron vigas rectangulares de concreto con los filtros dados.")
            return 2

        print(f"\nVigas a procesar: {len(vigas)}")
        for v in vigas:
            print(f"  - {v.id} ({v.piso}) {v.seccion}  b={v.geometria.b:.0f} h={v.geometria.h:.0f} "
                  f"L={v.geometria.L:.2f} ln={v.geometria.ln:.2f} f'c={v.materiales.fc:.0f}")

        # ------------------------------------------------------------------
        # Casos y combinaciones
        # ------------------------------------------------------------------
        detectados = detectar_casos_carga(conexion.sap_model)
        caso_d = args.caso_muerta or detectados.muerta
        caso_l = args.caso_viva or detectados.viva
        casos_s = list(_parse_lista(args.caso_sismo)) or list(detectados.sismo)
        if not caso_d or not caso_l:
            print(
                "No se pudieron determinar los casos de carga muerta y viva.\n"
                f"Casos disponibles: {', '.join(detectados.todos) or '(ninguno)'}\n"
                "Use --caso-muerta y --caso-viva."
            )
            return 2
        print(f"Casos: D={caso_d!r}  L={caso_l!r}  S={casos_s or '(sin sismo)'}")
        for adv in detectados.advertencias:
            print(f"Advertencia: {adv}")

        requeridas = generar_combos_requeridas(
            caso_d, caso_l, casos_s, config.factor_sismo
        )
        verificaciones = verificar_combinaciones(conexion.sap_model, requeridas)
        print("\nVerificación de combinaciones:")
        for v in verificaciones:
            print(f"  [{v.estado.upper():13}] {v.requerida.nombre:38} {v.detalle}")

        creadas: dict[str, str] = {}
        if any(v.estado != "coincide" for v in verificaciones):
            if config.crear_combos_faltantes:
                print("\nCreando combinaciones faltantes en ETABS...")
                creadas = crear_combinaciones(conexion.sap_model, requeridas, verificaciones)
                for req, real in creadas.items():
                    print(f"  creada: {req} → {real}")
                if creadas:
                    if config.analizar_si_crea or args.analizar:
                        print("Ejecutando análisis...")
                        try:
                            conexion.sap_model.Analyze.RunAnalysis()
                        except Exception as exc:
                            print(f"Advertencia: no se pudo ejecutar el análisis: {exc}")
                    else:
                        print(
                            "Aviso: las combinaciones nuevas requieren análisis. "
                            "Ejecute ETABS o use --analizar."
                        )
                verificaciones = verificar_combinaciones(conexion.sap_model, requeridas)
            else:
                print(
                    "\nAviso: hay combinaciones ausentes o parciales. Use --crear-combos "
                    "para crearlas, o verifique manualmente en ETABS."
                )

        mapa = mapas_combo_extraccion(requeridas, verificaciones, creadas)
        if not mapa:
            print("No hay combinaciones utilizables para extraer fuerzas.")
            return 2
        combos_reales = list(dict.fromkeys(mapa.values()))
        req_grav = combo_gravedad(requeridas)
        combo_grav_real = (
            mapa.get(req_grav.nombre) if req_grav and req_grav.nombre in mapa else None
        )
        faltantes = [c.nombre for c in requeridas if c.nombre not in mapa]
        if faltantes:
            print(
                "\nAVISO: las siguientes combinaciones requeridas no están "
                "disponibles y NO se usaron en el diseño:"
            )
            for c in faltantes:
                print(f"  - {c}")
            print(
                "El diseño puede quedar incompleto. Cree las combinaciones con "
                "--crear-combos y ejecute el análisis, o verifique el modelo."
            )
        print(f"\nCombinaciones para extracción ({len(combos_reales)}):")
        for c in combos_reales:
            print(f"  - {c}")

        for combo in combos_reales:
            try:
                conexion.sap_model.Results.Setup.SetComboSelectedForOutput(combo, True)
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Extracción, diseño y memoria
        # ------------------------------------------------------------------
        resultados: list[ResultadoViga] = []
        for i, v in enumerate(vigas, 1):
            print(f"\n[{i}/{len(vigas)}] Procesando {v.id} — {v.piso}...")
            fuerzas = extraer_fuerzas(
                conexion,
                v,
                combos_reales,
                combo_gravedad=combo_grav_real,
                p_compresion_negativa=config.p_compresion_negativa,
            )
            r = disenar_viga(v, fuerzas, config)
            resultados.append(r)
            print(
                f"  M+={r.fuerzas.M_pos_max_tm:.2f} t·m  "
                f"M−={r.fuerzas.M_neg_max_tm:.2f} t·m  "
                f"V={r.fuerzas.V_max_t:.2f} t  → {'CUMPLE' if r.cumple else 'REVISAR'}"
            )
            for adv in r.advertencias[:5]:
                print(f"    - {adv}")

        metadatos = MetadatosProyecto(
            proyecto=config.proyecto,
            ubicacion=config.ubicacion,
            ingeniero=config.ingeniero,
            cliente=config.cliente,
            fecha=date.today().strftime("%d/%m/%Y"),
            etabs_version=str(info.version),
            modelo=info.modelo,
            ruta_modelo=info.ruta_modelo,
            revision=config.revision,
        )
        combos_diseno = []
        try:
            from .etabs.combos import leer_combos_diseno_concreto

            combos_diseno = leer_combos_diseno_concreto(conexion.sap_model)
        except Exception:
            pass

        salidas = generar_reporte(
            resultados,
            metadatos,
            verificaciones,
            combos_diseno,
            config,
            ruta_salida=args.salida,
            formatos=config.formatos,
        )

        print("\n" + "=" * 78)
        print(" RESUMEN DE DISEÑO")
        print("=" * 78)
        _imprimir_tabla(_resumen_resultados(resultados))
        print("\nArchivos generados:")
        for k, v in salidas.items():
            if k in {"md", "docx"}:
                print(f"  {k.upper()}: {v}")
        for e in salidas.get("errores", []):
            print(f"  ADVERTENCIA: {e}")
        return 0
    finally:
        conexion.cerrar()


def main(argv: list[str] | None = None) -> int:
    parser = _crear_parser()
    args = parser.parse_args(argv)
    try:
        config = _config_desde_args(args)
    except ValueError as exc:
        print(f"Configuración inválida: {exc}")
        return 2

    try:
        if args.demo:
            return _flujo_demo(args, config)
        return _flujo_etabs(args, config)
    except (ETABSError, ETABSSinResultados) as exc:
        print("\nERROR DE ETABS:")
        print(str(exc))
        if args.verbose:
            traceback.print_exc()
        return 1
    except Exception as exc:
        print(f"\nERROR: {exc}")
        if args.verbose:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
