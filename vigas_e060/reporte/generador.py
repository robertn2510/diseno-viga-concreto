"""
Construcción de la memoria de cálculo.

El contenido es independiente del formato: se arma un :class:`Documento` con
bloques y luego se renderiza a Markdown o DOCX.  Esto garantiza que ambas
salidas tengan exactamente la misma información técnica.
"""

from __future__ import annotations

from datetime import date

from ..calculo.diseno import resumen_armado
from ..config import ConfiguracionDiseno
from ..modelos import (
    MetadatosProyecto,
    ResultadoFlexion,
    ResultadoViga,
    Verificacion,
    VerificacionCombo,
)
from .documento import Documento


def _hoy() -> str:
    return date.today().strftime("%d/%m/%Y")


def _estado(cumple: bool, advertencias: list[str]) -> str:
    if cumple and not advertencias:
        return "CUMPLE"
    if cumple:
        return "CUMPLE CON OBSERVACIONES"
    return "REVISAR"


def _tabla_verificaciones(doc: Documento, verificaciones: list[Verificacion]) -> None:
    filas = [
        [
            v.nombre,
            v.valor,
            v.limite,
            "CUMPLE" if v.cumple else "NO CUMPLE",
            v.referencia,
            v.observacion,
        ]
        for v in verificaciones
    ]
    doc.tabla(
        ["Verificación", "Valor", "Límite / criterio", "Estado", "Referencia", "Observación"],
        filas,
        anchos=[3.6, 2.7, 3.2, 2.0, 2.3, 4.2],
    )


def _formula_detallada(doc: Documento, formulas) -> None:
    for f in formulas:
        doc.formula(
            f"{f.titulo}\n{f.expresion}\n{f.sustitucion}\n→ {f.resultado}",
            referencia=f.referencia,
        )


def _seccion_identificacion(doc: Documento, r: ResultadoViga) -> None:
    v, g, m = r.viga, r.viga.geometria, r.viga.materiales
    doc.tabla(
        ["Identificación", "Valor", "Identificación", "Valor"],
        [
            ["ID de la viga", v.id, "Nombre ETABS", v.nombre],
            ["Piso (Story)", v.piso, "Eje / ubicación", v.eje],
            ["Sección", v.seccion, "Material", f"Concreto f'c = {m.fc:.0f} kgf/cm²"],
            ["Nudo I", v.punto_i, "Nudo J", v.punto_j],
            ["Coordenada I (m)", f"({v.coord_i[0]:.2f}; {v.coord_i[1]:.2f}; {v.coord_i[2]:.2f})",
             "Coordenada J (m)", f"({v.coord_j[0]:.2f}; {v.coord_j[1]:.2f}; {v.coord_j[2]:.2f})"],
            ["L entre ejes (m)", f"{g.L:.3f}", "Luz libre ln (m)", f"{g.ln:.3f}"],
            ["Apoyos detectados", v.soportes or "No identificados", "Recubrimiento libre r (cm)", f"{g.r:.2f}"],
        ],
        anchos=[3.4, 4.6, 3.4, 4.6],
    )


def _seccion_materiales(doc: Documento, r: ResultadoViga) -> None:
    v, g, m = r.viga, r.viga.geometria, r.viga.materiales
    doc.tabla(
        ["Parámetro", "Símbolo", "Valor", "Unidad", "Referencia"],
        [
            ["Resistencia del concreto", "f'c", f"{m.fc:.1f}", "kgf/cm²", "E.060 4.2 / 5"],
            ["Fluencia del acero longitudinal", "fy", f"{m.fy:.0f}", "kgf/cm²", "E.060 4.3"],
            ["Fluencia del acero transversal", "fyt", f"{m.fyt:.0f}", "kgf/cm²", "E.060 4.3"],
            ["Módulo de elasticidad del acero", "Es", f"{m.es:.0f}", "kgf/cm²", "E.060 10.2.4"],
            ["Factor del bloque rectangular", "β1", f"{m.beta1:.3f}", "—", "E.060 10.2.7.3"],
            ["Cuantía balanceada", "ρb", f"{m.rho_b:.5f}", "—", "E.060 10.3.2"],
            ["Ancho", "b", f"{g.b:.1f}", "cm", "—"],
            ["Peralte total", "h", f"{g.h:.1f}", "cm", "—"],
            ["Peralte efectivo estimado", "d", f"{g.d_estimado:.2f}", "cm", "E.060 10.2.2"],
            ["Recubrimiento libre al estribo", "r", f"{g.r:.2f}", "cm", "E.060 7.7.1"],
            ["Diámetro de estribo", "Øe", f"{g.diametro_estribo:.3f}", "cm", "E.060 21.5.3.2"],
            ["Área bruta", "Ag", f"{g.area_bruta:.1f}", "cm²", "—"],
            ["Longitud entre ejes", "L", f"{g.L:.3f}", "m", "—"],
            ["Luz libre", "ln", f"{g.ln:.3f}", "m", "E.060 21.5.1.1"],
        ],
        anchos=[5.2, 1.6, 2.2, 2.0, 3.2],
    )
    if v.recubrimiento_etabs_cm is not None:
        doc.nota(
            f"ETABS reporta un recubrimiento al centroide de la armadura de "
            f"{v.recubrimiento_etabs_cm:.2f} cm. El valor de r usado en el diseño "
            f"es el recubrimiento libre al estribo ({g.r:.2f} cm)."
        )


def _seccion_fuerzas(doc: Documento, r: ResultadoViga) -> None:
    f = r.fuerzas
    filas = []
    for nombre in ("I-End", "Cara-I", "Centro", "Cara-J", "J-End"):
        e = f.estaciones_clave.get(nombre)
        if not e:
            continue
        filas.append([
            nombre,
            f"{e.estacion_m:.3f}",
            f"{e.M3_max_tm:.2f}",
            f"{e.M3_min_tm:.2f}",
            f"{e.V2_max_t:.2f}",
            f"{e.P_min_t:.2f} / {e.P_max_t:.2f}",
            f"{e.T_max_tm:.2f}",
            f"{e.combo_M3_min}",
        ])
    doc.tabla(
        ["Estación", "x (m)", "M3 máx (t·m)", "M3 mín (t·m)", "|V2| máx (t)",
         "P mín / máx (t)", "|T| máx (t·m)", "Combo M3 mín"],
        filas,
        anchos=[2.1, 1.4, 2.1, 2.1, 2.0, 2.8, 2.0, 3.0],
    )
    doc.tabla(
        ["Máximo global", "Valor", "Estación (m)", "Combinación"],
        [
            ["Momento positivo M+", f"{f.M_pos_max_tm:.2f} t·m", f"{f.estacion_M_pos_m:.3f}", f.combo_M_pos or "—"],
            ["Momento negativo M−", f"{f.M_neg_max_tm:.2f} t·m", f"{f.estacion_M_neg_m:.3f}", f.combo_M_neg or "—"],
            ["Cortante |V2|", f"{f.V_max_t:.2f} t", f"{f.estacion_V_max_m:.3f}", f.combo_V_max or "—"],
            ["Torsión |T|", f"{f.T_max_tm:.2f} t·m", "—", f.combo_T_max or "—"],
            ["Compresión máxima P", f"{f.P_compresion_max_t:.2f} t", "—", "—"],
            ["Cortante gravitacional en caras", f"{f.V_gravedad_caras[0]:.2f} / {f.V_gravedad_caras[1]:.2f} t", "—", f.combo_gravedad or "—"],
        ],
        anchos=[5.0, 3.6, 3.0, 4.2],
    )
    doc.nota(
        "Convención: M3 positivo produce tracción en la fibra inferior (momento "
        "positivo o sagging); M3 negativo produce tracción en la fibra superior "
        "(momento negativo o hogging). V2 y P se presentan en valor absoluto y "
        "con signo según ETABS, respectivamente. Verifique los ejes locales del "
        "elemento si el modelo tiene rotaciones distintas de la vertical."
    )


def _tabla_parametros_flexion(doc: Documento, x: ResultadoFlexion) -> None:
    doc.tabla(
        ["Parámetro", "Valor", "Parámetro", "Valor"],
        [
            ["Ubicación", x.ubicacion, "Fibra diseñada", x.lado],
            ["Mu (t·m)", f"{x.Mu_tm:.3f}", "d (cm)", f"{x.d_cm:.2f}"],
            ["As mínimo (cm²)", f"{x.As_min_cm2:.3f}", "As máximo (cm²)", f"{x.As_max_cm2:.3f}"],
            ["Criterio de As máximo", x.criterio if hasattr(x, "criterio") else "—", "Mu máximo simple (t·m)", f"{x.Mu_max_simple_tm:.3f}"],
            ["As calculado (cm²)", f"{x.As_calculado_cm2:.3f}", "As requerido (cm²)", f"{x.As_req_cm2:.3f}"],
            ["As colocado (cm²)", f"{x.As_prov_cm2:.3f}", "Varillas", x.seleccion.etiqueta if x.seleccion else "—"],
            ["¿Doble refuerzo?", "Sí" if x.doble else "No", "As' requerido (cm²)", f"{x.As_prima_req_cm2:.3f}" if x.doble else "—"],
            ["As' colocado (cm²)", f"{x.As_prima_prov_cm2:.3f}" if x.doble else "—", "Varillas de compresión", x.seleccion_compresion.etiqueta if x.seleccion_compresion else "—"],
            ["a (cm)", f"{x.a_cm:.3f}", "c (cm)", f"{x.c_cm:.3f}"],
            ["εt", f"{x.eps_t:.5f}", "φ", f"{x.phi:.3f}"],
            ["Mn (t·m)", f"{x.Mn_tm:.3f}", "φMn (t·m)", f"{x.phiMn_tm:.3f}"],
            ["As colocado / requerido", f"{x.ratio_As:.2f}", "Estado", "CUMPLE" if x.cumple else "REVISAR"],
        ]
        + (
            [["Motivo de ampliación", x.motivo_ampliacion,
              "Demanda ETABS (t·m)", f"{x.Mu_original_tm:.3f}"]]
            if x.motivo_ampliacion else []
        ),
        anchos=[4.2, 3.6, 4.2, 4.2],
    )


def _seccion_flexion(doc: Documento, r: ResultadoViga) -> None:
    doc.h3("Diseño por flexión")
    doc.p(
        "Se diseñaron las secciones críticas de apoyo y centro, además de las "
        "estaciones donde la envolvente global alcanza sus máximos dentro de la "
        "luz libre (los valores en el eje de la columna no son secciones de "
        "diseño). El acero mínimo se verificó en todas las secciones "
        "(E.060 10.5.1) y la cuantía máxima se limitó a 0.025 (E.060 21.5.2.2). "
        "El factor φ se recalcula a partir de la deformación εt (E.060 9.3.2). "
        "Las secciones marcadas con (*) se ampliaron para cumplir los mínimos "
        "de continuidad Mn+ ≥ Mn−/2 y Mn ≥ Mn,max/4 (E.060 21.5.2.3 y 21.5.2.4)."
    )

    # Tabla resumen de todas las secciones
    filas = [
        [
            x.ubicacion + (" (*)" if x.motivo_ampliacion else ""), x.lado,
            f"{x.Mu_tm:.2f}", f"{x.As_req_cm2:.2f}",
            f"{x.As_prov_cm2:.2f}", x.seleccion.etiqueta if x.seleccion else "—",
            "Sí" if x.doble else "No", f"{x.phiMn_tm:.2f}", "CUMPLE" if x.cumple else "REVISAR",
        ]
        for x in r.flexion
    ]
    doc.tabla(
        ["Sección", "Fibra", "Mu (t·m)", "As req (cm²)", "As prov (cm²)",
         "Varillas", "Doble", "φMn (t·m)", "Estado"],
        filas,
        anchos=[4.6, 1.7, 1.7, 1.8, 1.8, 3.4, 1.3, 1.8, 1.8],
    )

    # Detalle paso a paso de las secciones diseñadas: se toma la sección
    # gobernante de cada par (ubicación, fibra).
    grupos: dict[tuple[str, str], list[ResultadoFlexion]] = {}
    for x in r.flexion:
        grupos.setdefault((x.ubicacion, x.lado), []).append(x)
    detalle: list[ResultadoFlexion] = [
        max(g, key=lambda x: x.Mu_tm) for g in grupos.values()
    ]

    # Orden de lectura: apoyo izquierdo, centro, máximos en la luz, apoyo
    # derecho; dentro de cada ubicación, fibra superior antes que inferior.
    def _orden(x: ResultadoFlexion) -> tuple[int, int]:
        u = x.ubicacion.lower()
        if u.startswith("apoyo izquierdo"):
            pos = 0
        elif u.startswith("centro"):
            pos = 1
        elif u.startswith("m+"):
            pos = 2
        elif u.startswith("m−"):
            pos = 3
        else:
            pos = 4
        return pos, 0 if x.lado == "superior" else 1

    detalle.sort(key=_orden)

    for x in detalle:
        titulo = (
            f"Detalle: {x.ubicacion} — fibra {x.lado} "
            f"(Mu de diseño = {x.Mu_tm:.2f} t·m)"
        )
        if x.motivo_ampliacion:
            titulo += (
                f" — ampliada por {x.motivo_ampliacion}; demanda ETABS = "
                f"{x.Mu_original_tm:.2f} t·m"
            )
        doc.h4(titulo)
        _tabla_parametros_flexion(doc, x)
        _formula_detallada(doc, x.formulas)
        doc.p("Verificaciones de la sección:")
        _tabla_verificaciones(doc, x.verificaciones)

    doc.h3("Resumen de acero teórico vs. acero colocado")
    filas = []
    for x in r.flexion:
        filas.append([
            x.ubicacion,
            x.lado,
            f"{x.Mu_tm:.2f}",
            f"{x.As_req_cm2:.2f}",
            f"{x.As_prov_cm2:.2f}",
            x.seleccion.etiqueta if x.seleccion else "—",
            f"{x.phiMn_tm:.2f}",
            "Sí" if x.doble else "No",
        ])
    doc.tabla(
        ["Sección", "Fibra", "Mu (t·m)", "As teórico (cm²)", "As colocado (cm²)",
         "Varillas comerciales", "φMn (t·m)", "Doble"],
        filas,
        anchos=[4.6, 1.7, 1.7, 2.2, 2.2, 4.2, 1.8, 1.3],
    )

    doc.h3("Armado longitudinal propuesto")
    filas = []
    for fila in resumen_armado(r):
        if fila["Zona"].startswith("Estribos"):
            continue
        filas.append([
            fila["Zona"], fila["Superior"], fila["Inferior"],
            fila["Mu− (t·m)"], fila["Mu+ (t·m)"],
        ])
    doc.tabla(
        ["Zona", "Armadura superior", "Armadura inferior", "Mu− (t·m)", "Mu+ (t·m)"],
        filas,
        anchos=[4.5, 4.3, 4.3, 2.8, 2.8],
    )
    doc.nota(
        "Se disponen como mínimo dos barras continuas superior e inferior en "
        "toda la longitud de la viga (E.060 21.5.2.1). El armado de la memoria "
        "es una propuesta de diseño; el despiece final debe compatibilizarse "
        "con longitudes de desarrollo, traslapes y detalles del proyecto."
    )


def _seccion_cortante(doc: Documento, r: ResultadoViga) -> None:
    c = r.cortante
    if c is None:
        return
    doc.h3("Diseño por cortante")
    doc.p(
        "El cortante de diseño se determinó por capacidad, sumando el cortante "
        "asociado a las resistencias probables en flexión Mpr = 1.25·Mn en los "
        "extremos y el cortante gravitacional (E.060 21.5.4.1). Se comparó con "
        "la envolvente de ETABS y se adoptó el mayor. En la zona de "
        "confinamiento se aplicó la reducción de Vc a cero cuando el sismo "
        "aporta al menos la mitad del cortante y la carga axial es baja "
        "(E.060 21.5.4.2)."
    )
    doc.tabla(
        ["Parámetro", "Valor", "Parámetro", "Valor"],
        [
            ["d de cortante (cm)", f"{c.d_cm:.2f}", "ln (m)", f"{c.ln_m:.3f}"],
            ["Mpr,i (t·m)", f"{c.Mpr_i_tm:.2f}", "Mpr,j (t·m)", f"{c.Mpr_j_tm:.2f}"],
            ["Ve = ΣMpr/ln (t)", f"{c.Ve_t:.2f}", "Vg caras i/j (t)", f"{c.Vg_i_t:.2f} / {c.Vg_j_t:.2f}"],
            ["Vu,i (t)", f"{c.Vu_i_t:.2f}", "Vu,j (t)", f"{c.Vu_j_t:.2f}"],
            ["Vu de diseño (t)", f"{c.Vu_diseno_t:.2f}", "V envolvente ETABS (t)", f"{c.Vu_envolvente_t:.2f}"],
            ["Vc (t)", f"{c.Vc_t:.2f}", "Vc zona confinada (t)", f"{c.Vc_conf_t:.2f}"],
            ["φ cortante", f"{c.phi:.2f}", "Vs req izquierdo (t)", f"{c.Vs_req_i_t:.2f}"],
            ["Vs req derecho (t)", f"{c.Vs_req_j_t:.2f}", "s req izquierdo (cm)", f"{c.s_req_i_cm:.2f}" if c.s_req_i_cm < 1e5 else "mínimo"],
            ["s req derecho (cm)", f"{c.s_req_j_cm:.2f}" if c.s_req_j_cm < 1e5 else "mínimo", "s conf. izquierdo (cm)", f"{c.s_conf_i_cm:.2f}"],
            ["s conf. derecho (cm)", f"{c.s_conf_j_cm:.2f}", "s central (cm)", f"{c.s_central_cm:.2f}"],
            ["s máx. confinamiento (cm)", f"{c.s_max_conf_cm:.2f}", "s máx. central (cm)", f"{c.s_max_central_cm:.2f}"],
            ["Av (cm²)", f"{c.Av_cm2:.2f}", "Ramas por estribo", f"{c.ramas}"],
            ["Estribo", f"Φ {c.estribo.nombre}", "L zona confinada (m)", f"{c.L_conf_m:.2f}"],
        ],
        anchos=[4.4, 3.2, 4.4, 3.2],
    )
    doc.p("Fórmulas aplicadas:")
    _formula_detallada(doc, c.formulas)

    doc.h4("Detalle de estribado")
    doc.tabla(
        ["Tramo", "Distribución", "Separación (m)"],
        [
            ["Apoyo izquierdo (zona de confinamiento, 2h)", c.distribucion_i, f"{c.s_conf_i_cm/100:.2f}"],
            ["Tramo central", c.distribucion_central, f"{c.s_central_cm/100:.2f}"],
            ["Apoyo derecho (zona de confinamiento, 2h)", c.distribucion_j, f"{c.s_conf_j_cm/100:.2f}"],
            ["Total de estribos", f"{c.total_estribos} piezas", "—"],
            ["Peso aproximado de estribos", f"{c.peso_estribos_kg:.2f} kg", "—"],
        ],
        anchos=[6.2, 8.0, 3.6],
    )
    doc.formula(
        f"Distribución: {c.distribucion_completa}\n"
        f"Estribo: Φ {c.estribo.nombre} de {c.ramas} ramas, Av = {c.Av_cm2:.2f} cm²\n"
        "Ganchos sísmicos a 135° con extensión ≥ 8db y ≥ 75 mm (E.060 7.1.3.c).",
        referencia="Detalle de estribado",
    )
    doc.p("Verificaciones de cortante:")
    _tabla_verificaciones(doc, c.verificaciones)


def _seccion_globales(doc: Documento, r: ResultadoViga) -> None:
    doc.h3("Verificaciones globales de la viga")
    _tabla_verificaciones(doc, r.verificaciones)
    if r.advertencias:
        doc.h4("Observaciones")
        doc.bullets(r.advertencias)


def _memoria_viga(
    doc: Documento,
    indice: int,
    r: ResultadoViga,
    verificaciones_combos: list[VerificacionCombo],
    combos_diseno: list[str],
) -> None:
    v = r.viga
    doc.h2(f"4.{indice} Viga {v.id} — {v.piso}")
    doc.p(
        f"Elemento {v.nombre} de sección {v.seccion}, ubicado en {v.piso} "
        f"({v.eje}). Diseño según E.060 para f'c = {v.materiales.fc:.0f} kgf/cm² "
        f"y fy = {v.materiales.fy:.0f} kgf/cm²."
    )
    doc.h3("Identificación del elemento")
    _seccion_identificacion(doc, r)
    doc.h3("Propiedades de materiales y geometría")
    _seccion_materiales(doc, r)
    doc.h3("Resumen de cargas y momentos críticos de ETABS")
    _seccion_fuerzas(doc, r)
    _seccion_flexion(doc, r)
    _seccion_cortante(doc, r)
    _seccion_globales(doc, r)


def construir_memoria(
    resultados: list[ResultadoViga],
    metadatos: MetadatosProyecto,
    verificaciones_combos: list[VerificacionCombo],
    combos_diseno_etabs: list[str],
    config: ConfiguracionDiseno,
) -> Documento:
    doc = Documento()
    fecha = metadatos.fecha or _hoy()

    # ------------------------------------------------------------------
    # Portada
    # ------------------------------------------------------------------
    doc.h1("MEMORIA DE CÁLCULO")
    doc.h2("DISEÑO DE VIGAS DE CONCRETO ARMADO — NORMA E.060")
    doc.p(
        "Diseño por flexión y cortante de vigas rectangulares de concreto "
        "armado, con extracción automática de fuerzas internas desde ETABS y "
        "verificación de las disposiciones sísmicas del capítulo 21 de la "
        "Norma Técnica E.060 del Reglamento Nacional de Edificaciones."
    )
    datos_portada = [
        ["Proyecto", metadatos.proyecto],
            ["Ubicación", metadatos.ubicacion],
            ["Cliente", metadatos.cliente or "—"],
            ["Ingeniero responsable", metadatos.ingeniero],
            ["Revisión", metadatos.revision],
            ["Fecha", fecha],
            ["Software", "vigas-e060 — Python + API ETABS (comtypes/pywin32)"],
            ["Versión ETABS", metadatos.etabs_version or "—"],
            ["Modelo ETABS", metadatos.modelo or "—"],
            ["Ruta del modelo", metadatos.ruta_modelo or "—"],
        ["Número de vigas", str(len(resultados))],
    ]
    if metadatos.observaciones:
        datos_portada.append(["Observaciones", metadatos.observaciones])
    doc.tabla(
        ["Dato", "Valor"],
        datos_portada,
        anchos=[5.0, 12.0],
    )
    doc.nota(
        "Este documento es una memoria de cálculo asistida por computadora. "
        "Los resultados deben ser revisados y validados por un ingeniero "
        "estructural colegiado antes de su uso en obra."
    )
    doc.salto()

    # ------------------------------------------------------------------
    # 1. Generalidades
    # ------------------------------------------------------------------
    doc.h1("1. GENERALIDADES")
    doc.h2("1.1 Alcance")
    doc.bullets([
        "Diseño a flexión de vigas rectangulares de concreto armado, incluyendo "
        "armadura simple y doble.",
        "Diseño a cortante con estribos, zona de confinamiento y cortante por "
        "capacidad para pórticos especiales a momento y sistemas duales tipo II.",
        "Verificación de límites de acero, ductilidad, cuantías y detalles "
        "mínimos del capítulo 21 de la E.060.",
        "Generación de memoria de cálculo por elemento y resumen global.",
    ])
    doc.h2("1.2 Normativa aplicada")
    doc.bullets([
        "NTE E.060 Concreto Armado — D.S. N° 010-2009 (RNE).",
        "NTE E.020 Cargas.",
        "NTE E.030 Diseño Sismorresistente.",
        "ACI 318-05 / ACI 318-08 como referencia concordante para los artículos "
        "no desarrollados explícitamente en la E.060.",
    ])
    doc.h2("1.3 Unidades y convención")
    doc.tabla(
        ["Magnitud", "Unidad de cálculo", "Unidad de reporte"],
        [
            ["Longitud", "cm", "cm / m"],
            ["Fuerza", "kgf", "t"],
            ["Momento", "kgf·cm", "t·m"],
            ["Esfuerzo", "kgf/cm²", "kgf/cm²"],
            ["Área de acero", "cm²", "cm²"],
        ],
        anchos=[5.0, 6.0, 6.0],
    )
    doc.p(
        "Convención de momentos: M3 positivo = tracción en fibra inferior "
        "(sagging); M3 negativo = tracción en fibra superior (hogging). "
        "La armadura superior se diseña para el momento negativo y la inferior "
        "para el positivo. Si el modelo ETABS tiene los ejes locales rotados, "
        "el usuario debe verificar la convención antes de usar los resultados."
    )
    doc.h2("1.4 Limitaciones")
    doc.bullets([
        "No se diseña torsión; ETABS reporta T pero la memoria solo la informa. "
        "Si T es significativa, se debe hacer un diseño específico (E.060 11.6).",
        "No se verifica deflexión ni fisuración por servicio.",
        "No se diseñan columnas, nudos ni cimentación.",
        "No se verifican longitudes de desarrollo, traslapes ni detalles de "
        "anclaje; se indica el detalle de estribado y el armado longitudinal.",
        "El diseño asume secciones rectangulares sin losa colaborante; si la "
        "viga es parte de un sistema T, debe revisarse el ancho efectivo.",
        "Las fuerzas se toman de ETABS; la calidad del resultado depende del "
        "modelo, las combinaciones y el análisis ejecutado.",
    ])
    doc.salto()

    # ------------------------------------------------------------------
    # 2. Combinaciones
    # ------------------------------------------------------------------
    doc.h1("2. COMBINACIONES DE CARGA")
    doc.p(
        "La resistencia requerida se evaluó con las combinaciones de la E.060, "
        "artículo 9.2. El programa verifica que cada combinación requerida "
        "exista en ETABS con los mismos casos y factores; las combinaciones "
        "ausentes se informan y, si se solicita, se crean automáticamente."
    )
    filas = []
    for i, ver in enumerate(verificaciones_combos, 1):
        req = ver.requerida
        filas.append([
            str(i),
            req.nombre,
            req.etiqueta,
            req.referencia,
            ver.encontrada or "—",
            ver.estado.upper(),
            ver.detalle,
        ])
    doc.tabla(
        ["N°", "Combinación requerida", "Factores", "Referencia", "Combinación ETABS", "Estado", "Detalle"],
        filas,
        anchos=[0.8, 3.4, 3.0, 2.6, 2.8, 2.0, 4.4],
    )
    no_disponibles = [
        v for v in verificaciones_combos if v.estado != "coincide"
    ]
    if no_disponibles:
        doc.nota(
            f"Advertencia: {len(no_disponibles)} de {len(verificaciones_combos)} "
            "combinaciones requeridas no coinciden exactamente con las del "
            "modelo. El diseño se realizó únicamente con las combinaciones "
            "disponibles; los resultados pueden ser incompletos. Revise la "
            "columna Estado de la tabla anterior."
        )
    doc.h2("2.1 Combinaciones de diseño de concreto en ETABS")
    if combos_diseno_etabs:
        doc.p("ETABS reporta las siguientes combinaciones para el diseño de concreto:")
        doc.bullets(combos_diseno_etabs)
    else:
        doc.p(
            "No se pudo leer la lista de combinaciones de diseño de concreto "
            "(DesignConcrete.GetComboStrength) o el modelo no tiene diseño "
            "de concreto configurado. Se usan las combinaciones verificadas "
            "en la tabla anterior."
        )
    doc.h2("2.2 Criterio sobre el factor sísmico")
    if abs(config.factor_sismo - 1.25) < 1e-9:
        variante = (
            "La variante adoptada en este proyecto es U = 1.25(D + L) ± 1.25S "
            "y U = 0.9D ± 1.25S (factor 1.25 sobre la acción sísmica)."
        )
    else:
        variante = (
            "La variante adoptada en este proyecto es U = 1.25(D + L) ± 1.00S "
            "y U = 0.9D ± 1.00S (factor 1.00 sobre la acción sísmica), "
            "concordante con la reproducción de la E.060 2009 que usa ±CS."
        )
    doc.p(
        variante + " La E.060 2009, artículo 9.2.3, se reproduce en algunas "
        "ediciones con ±CS (factor 1.0), mientras que la edición 2006 y la "
        "práctica ACI emplean ±1.25CS. El programa permite ambas variantes "
        "con el parámetro --norma-combos; la variante usada se indica en la "
        "tabla anterior."
    )
    doc.salto()

    # ------------------------------------------------------------------
    # 3. Resumen
    # ------------------------------------------------------------------
    doc.h1("3. RESUMEN DE RESULTADOS")
    filas = []
    for r in resultados:
        c = r.cortante
        filas.append([
            r.viga.id,
            r.viga.piso,
            f"{r.viga.geometria.b:.0f}×{r.viga.geometria.h:.0f}",
            f"{r.viga.geometria.ln:.2f}",
            f"{r.fuerzas.M_pos_max_tm:.2f}",
            f"{r.fuerzas.M_neg_max_tm:.2f}",
            f"{r.fuerzas.V_max_t:.2f}",
            c.distribucion_i if c else "—",
            _estado(r.cumple, r.advertencias),
        ])
    doc.tabla(
        ["Viga", "Piso", "b×h (cm)", "ln (m)", "M+ (t·m)", "M− (t·m)", "V (t)",
         "Estribos (zona conf.)", "Estado"],
        filas,
        anchos=[1.8, 2.0, 1.8, 1.4, 1.6, 1.6, 1.4, 3.8, 2.2],
    )
    doc.nota(
        "M+ y M− son los máximos de la envolvente en toda la longitud de la "
        "viga, incluidos los ejes de columna; el diseño a flexión se realiza en "
        "la cara del apoyo y en el centro de la luz. De igual modo, la columna "
        "V (t) es la envolvente global y el cortante de diseño se toma en la "
        "cara del apoyo (E.060 21.5.4.1)."
    )
    total_obs = sum(len(r.advertencias) for r in resultados)
    doc.p(
        f"Se procesaron {len(resultados)} vigas. Se registraron {total_obs} "
        "observaciones; consulte el detalle por elemento y el Anexo C."
    )
    doc.salto()

    # ------------------------------------------------------------------
    # 4. Memoria por viga
    # ------------------------------------------------------------------
    doc.h1("4. MEMORIA DE CÁLCULO POR VIGA")
    doc.p(
        "Cada elemento incluye identificación, materiales, geometría, fuerzas "
        "críticas, fórmulas con valores sustituidos, comparación de acero "
        "teórico vs. colocado y detalle de estribado."
    )
    for i, r in enumerate(resultados, 1):
        _memoria_viga(doc, i, r, verificaciones_combos, combos_diseno_etabs)
        doc.salto()

    # ------------------------------------------------------------------
    # 5. Conclusiones
    # ------------------------------------------------------------------
    doc.h1("5. CONCLUSIONES Y RECOMENDACIONES")
    no_cumplen = [r.viga.id for r in resultados if not r.cumple]
    if no_cumplen:
        doc.p(
            "Las siguientes vigas requieren revisión o ajuste de sección, "
            "armadura o espaciamiento: " + ", ".join(no_cumplen) + "."
        )
    else:
        doc.p(
            "Todas las vigas procesadas cumplen las verificaciones de resistencia "
            "y detalle implementadas en esta memoria."
        )
    doc.bullets([
        "Verificar en obra el recubrimiento, la posición de las barras y los "
        "ganchos sísmicos a 135°.",
        "Revisar las longitudes de desarrollo y los traslapes en la etapa de "
        "despiece; no forman parte del alcance de este cálculo.",
        "Si la torsión reportada por ETABS es significativa, realizar el diseño "
        "por torsión según E.060 11.6.",
        "Actualizar la memoria si cambian las combinaciones, el modelo ETABS o "
        "las propiedades de los materiales.",
    ])
    doc.salto()

    # ------------------------------------------------------------------
    # Anexo A
    # ------------------------------------------------------------------
    doc.h1("ANEXO A. FORMULACIÓN Y REFERENCIAS")
    doc.h2("A.1 Flexión")
    doc.formula(
        "β1 = 0.85                                          si f'c ≤ 280 kgf/cm²\n"
        "β1 = 0.85 − 0.05(f'c − 280)/70                     si f'c > 280 kgf/cm²\n"
        "ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]\n"
        "As,min = 0.7·√(f'c)/fy · b·d\n"
        "As,max = mín(0.75ρb·b·d; As(εt=0.005); 0.025·b·d)\n"
        "Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)\n"
        "As' = [Mu/φ − Cc(d − a/2)]/[f's(d − d')],  Cc = 0.85·f'c·b·a\n"
        "εt = 0.003(d − c)/c,  c = a/β1",
        referencia="E.060 10.2.7, 10.3, 10.5.1, 21.5.2.2, 9.3.2",
    )
    doc.h2("A.2 Cortante")
    doc.formula(
        "Vc = 0.53·√(f'c)·b·d\n"
        "Vs = Av·fy·d/s\n"
        "Vu = φ(Vc + Vs)\n"
        "s ≤ d/2 ≤ 60 cm\n"
        "Av,min/s = máx(0.20√(f'c)·b/fy; 3.5·b/fy)\n"
        "Vs ≤ 2.1·√(f'c)·b·d\n"
        "Vu,capacidad = (Mpr,i + Mpr,j)/ln + Vg,  Mpr = 1.25·Mn\n"
        "sconf ≤ mín(d/4; 8db,long; 24db,est; 30 cm);  scentral ≤ d/2",
        referencia="E.060 11.3.1.1, 11.5.5, 11.5.6, 11.5.7, 21.5.3, 21.5.4",
    )
    doc.h2("A.3 Tabla de artículos aplicados")
    doc.tabla(
        ["Tema", "Artículo E.060", "Aplicación en el programa"],
        [
            ["Combinaciones de carga", "9.2.1, 9.2.3", "Generación y verificación de combos"],
            ["Factor φ flexión", "9.3.2.1 / 9.3.2.2", "φ = 0.90 si εt ≥ 0.005; interpolación"],
            ["Factor φ cortante", "9.3.2.3", "φ = 0.85"],
            ["Bloque rectangular", "10.2.7", "β1, a = As fy/(0.85 f'c b)"],
            ["Cuantía balanceada", "10.3.2", "ρb y límite 0.75ρb"],
            ["Ductilidad", "10.3.5", "εt ≥ 0.004"],
            ["Acero mínimo", "10.5.1", "As,min = 0.7√f'c b d/fy"],
            ["Cortante del concreto", "11.3.1.1", "Vc = 0.53√f'c b d"],
            ["Estribos mínimos", "11.5.6.3", "Av,min/s"],
            ["Espaciamiento", "11.5.5.1", "s ≤ d/2 ≤ 60 cm"],
            ["Vigas sísmicas: geometría", "21.5.1", "ln ≥ 4h; b ≥ 0.25h; b ≥ 25 cm"],
            ["Refuerzo longitudinal", "21.5.2", "2 barras continuas; ρ ≤ 0.025; Mn+/Mn−"],
            ["Confinamiento", "21.5.3", "2h; primer estribo 5 cm; sconf"],
            ["Cortante por capacidad", "21.5.4", "Mpr = 1.25Mn; Vc = 0"],
            ["Recubrimiento", "7.7.1", "r = 4 cm (configurable)"],
            ["Ganchos sísmicos", "7.1.3", "135°, 8db ≥ 75 mm"],
        ],
        anchos=[4.2, 3.4, 9.4],
    )
    doc.salto()

    # ------------------------------------------------------------------
    # Anexo B
    # ------------------------------------------------------------------
    doc.h1("ANEXO B. SUPUESTOS, ALCANCE Y TRAZABILIDAD")
    doc.h2("B.1 Supuestos")
    doc.bullets([
        "Secciones rectangulares de concreto armado, sin participación de losa.",
        "Flexión uniaxial alrededor del eje local 3 (M3) y cortante en V2.",
        "No se considera carga axial significativa en la viga; P se informa y se "
        "usa solo para la condición Vc = 0 de 21.5.4.2.",
        "El acero longitudinal fluye en tracción (fy = 4200 kgf/cm²).",
        "La armadura de compresión se evalúa con compatibilidad de deformaciones "
        "y puede no fluir; se reporta f's.",
        "El cortante por capacidad se calcula con Mpr = 1.25Mn de la armadura "
        "colocada, en ambas direcciones de sway.",
        "La luz libre se estima a partir de las columnas conectadas; si no se "
        "detectan, se usa la longitud entre ejes.",
    ])
    doc.h2("B.2 Trazabilidad ETABS")
    doc.tabla(
        ["Dato", "Valor"],
        [
            ["Versión ETABS", metadatos.etabs_version or "—"],
            ["Modelo", metadatos.modelo or "—"],
            ["Ruta", metadatos.ruta_modelo or "—"],
            ["API", "ETABSv1 — comtypes/pywin32"],
            ["Unidades de trabajo", "kgf_m (eUnits = 8) con conversión interna"],
            ["Funciones usadas", "GetAllFrames, GetRectangle, GetOConcrete, GetLabelFromName, FrameForce"],
        ],
        anchos=[4.5, 12.5],
    )
    doc.h2("B.3 Limitaciones y advertencias")
    doc.p(
        "Esta memoria no sustituye la revisión profesional ni el despiece. "
        "Los resultados deben contrastarse con el modelo ETABS, las cargas de "
        "proyecto y los requisitos particulares de la E.030 y del expediente "
        "técnico."
    )
    doc.salto()

    # ------------------------------------------------------------------
    # Anexo C
    # ------------------------------------------------------------------
    doc.h1("ANEXO C. REGISTRO DE OBSERVACIONES")
    if any(r.advertencias for r in resultados):
        for r in resultados:
            if r.advertencias:
                doc.h3(f"Viga {r.viga.id}")
                doc.bullets(r.advertencias)
    else:
        doc.p("No se registraron observaciones.")
    doc.p(
        f"Documento generado el {fecha}. Revisión {metadatos.revision}."
    )
    return doc
