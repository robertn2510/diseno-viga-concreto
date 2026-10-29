"""
Servicio de alto nivel: de un elemento de ETABS al diseño E.060 y su memoria.

Es la capa que usan tanto la interfaz de escritorio (Tkinter) como la web.
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

from . import normas
from .combinaciones import es_combinacion_sismica
from .columna import DemandaColumna, EntradaColumna, disenar_columna
from .etabs import Elemento, FuenteETABS
from .seccion import Seccion
from .viga import DemandaViga, EntradaViga, disenar_viga


# ===========================================================================
# Opciones de diseño
# ===========================================================================
@dataclass
class OpcionesDiseno:
    """Parámetros de diseño que el usuario puede ajustar."""
    tipo: str = "auto"                 # 'auto' | 'Viga' | 'Columna'
    sismico: bool = True
    recubrimiento: float = 4.0
    db_estribo: str = "#3"
    n_estaciones: int = 5
    considerar_torsion: bool = True
    amplificar_esbeltez: bool = False
    beta_dns: float = 0.0
    varilla_pref: Optional[str] = None
    b: Optional[float] = None          # sobreescribe la dimensión del modelo
    h: Optional[float] = None
    fc: Optional[float] = None
    fy: Optional[float] = None
    luz_libre: Optional[float] = None  # cm; si None usa la longitud del elemento
    usar_vc_nulo_sismo: bool = True    # Vc = 0 si el cortante sísmico domina (21.4.5.2)
    proyecto: str = "Proyecto"
    ubicacion: str = ""
    autor: str = "Ing. Estructural"
    norma_sismo: str = "E.030-2018"
    notas: str = ""


# ===========================================================================
# Utilidades
# ===========================================================================
def _aplicar_opciones(el: Elemento, opc: OpcionesDiseno) -> Elemento:
    nuevo = replace(el)
    nuevo.puntos = list(el.puntos)
    if opc.b:
        nuevo.b = float(opc.b)
    if opc.h:
        nuevo.h = float(opc.h)
    if opc.fc:
        nuevo.fc = float(opc.fc)
    if opc.fy:
        nuevo.fy = float(opc.fy)
    if opc.luz_libre:
        nuevo.L = float(opc.luz_libre)
    return nuevo


def _nombre_estacion(x: float, L: float) -> str:
    if L <= 0:
        return f"x = {x/100:.2f} m"
    f = x / L
    if f <= 0.02:
        return "Extremo i"
    if f >= 0.98:
        return "Extremo j"
    if abs(f - 0.5) < 0.02:
        return "Centro de luz"
    return f"x = {x/100:.2f} m"


def estaciones_diseno(el: Elemento, n: int = 5) -> List[float]:
    """Estaciones a diseñar: extremos, centro y puntos intermedios."""
    disponibles = el.estaciones
    if not disponibles:
        L = el.L or 1.0
        return [L * i / max(n - 1, 1) for i in range(n)]
    if len(disponibles) <= n:
        return disponibles
    objetivo = [disponibles[0], disponibles[-1]]
    # centro
    centro = min(disponibles, key=lambda x: abs(x - el.L / 2.0))
    objetivo.append(centro)
    # puntos que maximizan momento
    envs = sorted(el.envolventes(), key=lambda e: -(e["Mu_pos"] + e["Mu_neg"]))
    for e in envs:
        if len(objetivo) >= n:
            break
        if all(abs(e["estacion"] - o) > 1.0 for o in objetivo):
            objetivo.append(e["estacion"])
    return sorted(objetivo)[:n]


# ===========================================================================
# Construcción de entradas de diseño
# ===========================================================================
def entrada_viga_desde_elemento(el: Elemento, opc: OpcionesDiseno) -> EntradaViga:
    L = el.L or 600.0
    estaciones = estaciones_diseno(el, opc.n_estaciones)
    demandas: List[DemandaViga] = []
    for est in estaciones:
        pts = el.puntos_en(est, tol=max(1.0, 0.005 * L))
        if not pts:
            continue
        # envolventes de la estación
        env = _envolvente_estacion(pts, "viga")
        vu_sismo = max((math.hypot(p.V2, p.V3) for p in pts
                        if es_combinacion_sismica(p.combo)), default=0.0)
        vu_grav = max((math.hypot(p.V2, p.V3) for p in pts
                       if not es_combinacion_sismica(p.combo)), default=0.0)
        demandas.append(DemandaViga(
            estacion=_nombre_estacion(est, L),
            Mu_pos=env["Mu_pos"], Mu_neg=env["Mu_neg"], Vu=env["Vu"],
            Vu_sismo=vu_sismo, Vu_grav=vu_grav,
            Tu=env["Tu"] if opc.considerar_torsion else 0.0,
            Nu=env["Nu"],
            combo_pos=env["combo_pos"], combo_neg=env["combo_neg"],
            combo_vu=env["combo_Vu"], combo_tu=env["combo_Tu"]))
    if not demandas:
        demandas = [DemandaViga("Centro de luz", 0.0, 0.0, 0.0)]
    return EntradaViga(
        nombre=el.nombre, b=el.b, h=el.h, fc=el.fc, fy=el.fy,
        L=L, recubrimiento=opc.recubrimiento, db_estribo=0.953,
        sismico=opc.sismico, estaciones=demandas,
        varilla_pref=opc.varilla_pref, db_estribo_pref=opc.db_estribo,
        Vu_sismo=0.0, usar_vc_sismo=opc.usar_vc_nulo_sismo)


def _envolvente_estacion(pts, tipo: str) -> dict:
    """Envolvente de solicitaciones en una estación."""
    m_pos = max((p.M3 for p in pts), default=0.0)
    m_neg = min((p.M3 for p in pts), default=0.0)
    c_pos = max(pts, key=lambda p: p.M3)
    c_neg = min(pts, key=lambda p: p.M3)
    c_vu = max(pts, key=lambda p: math.hypot(p.V2, p.V3))
    c_tu = max(pts, key=lambda p: abs(p.T))
    c_pu = max(pts, key=lambda p: abs(p.P))
    return {
        "Mu_pos": max(0.0, m_pos), "combo_pos": c_pos.combo if m_pos > 0 else "",
        "Mu_neg": abs(min(0.0, m_neg)), "combo_neg": c_neg.combo if m_neg < 0 else "",
        "Vu": math.hypot(c_vu.V2, c_vu.V3), "combo_Vu": c_vu.combo,
        "Tu": abs(c_tu.T), "combo_Tu": c_tu.combo,
        "Nu": c_pu.P, "combo_Pu": c_pu.combo,
    }


def demandas_columna_desde_elemento(el: Elemento,
                                    max_demandas: int = 24) -> Tuple[List[DemandaColumna], dict]:
    """
    Selecciona las combinaciones críticas de (P, M2, M3) de una columna.

    Se toman, por cada combinación, las estaciones con máximo |M3|, máximo |M2|,
    máximo P y mínimo P (los estados que gobiernan el diagrama de interacción).
    """
    por_combo: Dict[str, List] = {}
    for p in el.puntos:
        por_combo.setdefault(p.combo, []).append(p)

    seleccion: List[DemandaColumna] = []
    vistos = set()
    for combo, pts in por_combo.items():
        candidatos = []
        candidatos.append(max(pts, key=lambda p: abs(p.M3)))
        candidatos.append(max(pts, key=lambda p: abs(p.M2)))
        candidatos.append(max(pts, key=lambda p: p.P))
        candidatos.append(min(pts, key=lambda p: p.P))
        for p in candidatos:
            clave = (round(p.P / 100.0), round(p.M2 / 1e4), round(p.M3 / 1e4))
            if clave in vistos:
                continue
            vistos.add(clave)
            etiqueta = combo
            if p.estacion is not None and el.L:
                f = p.estacion / el.L
                pos = ("extremo i" if f <= 0.05 else
                       "extremo j" if f >= 0.95 else
                       "centro" if abs(f - 0.5) < 0.05 else f"x={p.estacion/100:.2f} m")
                etiqueta = f"{combo} · {pos}"
            seleccion.append(DemandaColumna(combo=etiqueta, P=p.P, M2=p.M2, M3=p.M3,
                                            V2=p.V2, V3=p.V3, T=p.T))
    # ordena por severidad aproximada y recorta
    seleccion.sort(key=lambda d: -(abs(d.M3) + abs(d.M2)) / 1e5)
    if len(seleccion) > max_demandas:
        # conserva los más severos y los de máxima compresión
        seleccion = seleccion[:max_demandas - 4] + sorted(
            seleccion[-4:], key=lambda d: -abs(d.P))[:4]
    env = {
        "Pu_max": max((d.P for d in seleccion), default=0.0),
        "Pu_min": min((d.P for d in seleccion), default=0.0),
        "M3_max": max((abs(d.M3) for d in seleccion), default=0.0),
        "M2_max": max((abs(d.M2) for d in seleccion), default=0.0),
        "n": len(seleccion),
    }
    return seleccion, env


def entrada_columna_desde_elemento(el: Elemento,
                                   opc: OpcionesDiseno) -> EntradaColumna:
    demandas, env = demandas_columna_desde_elemento(el)
    Pu_max = max(env["Pu_max"], 0.0)
    M_max = max((abs(d.M3) for d in demandas), default=0.0)
    vu = max((math.hypot(d.V2, d.V3) for d in demandas), default=0.0)
    return EntradaColumna(
        nombre=el.nombre, b=el.b, h=el.h, fc=el.fc, fy=el.fy,
        Pu=Pu_max, Mux=M_max, Muy=max((abs(d.M2) for d in demandas), default=0.0),
        L=el.L or 300.0, k=1.0, recubrimiento=opc.recubrimiento,
        db_estribo=0.953, sismico=opc.sismico,
        amplificar=opc.amplificar_esbeltez, beta_dns=opc.beta_dns,
        M1=0.0, M2=M_max, demandas=demandas, Vu=vu,
        estribo_pref=opc.db_estribo, db_long_pref=opc.varilla_pref)


# ===========================================================================
# Diseño
# ===========================================================================
def determinar_tipo(el: Elemento, opc: OpcionesDiseno) -> str:
    if opc.tipo in ("Viga", "Columna"):
        return opc.tipo
    if el.tipo in ("Viga", "Columna"):
        return el.tipo
    # heurística geométrica: columnas suelen tener L/h menor y sección cuadrada
    if el.h > 0 and el.L > 0:
        relacion = el.L / el.h
        if relacion < 8 and 0.6 <= el.b / el.h <= 1.6:
            return "Columna"
    return "Viga"


def disenar_elemento(el: Elemento, opc: Optional[OpcionesDiseno] = None) -> dict:
    """
    Diseña el elemento y devuelve un resultado completo listo para la
    memoria de cálculo y para las interfaces.
    """
    opc = opc or OpcionesDiseno()
    elemento = _aplicar_opciones(el, opc)
    errores = elemento.validar()
    if errores:
        raise ValueError("No se puede diseñar el elemento:\n- " + "\n- ".join(errores))

    tipo = determinar_tipo(elemento, opc)
    salida = {
        "tipo": tipo,
        "elemento": elemento,
        "opciones": opc,
        "fecha": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    if tipo == "Viga":
        entrada = entrada_viga_desde_elemento(elemento, opc)
        resultado = disenar_viga(entrada)
        salida["entrada"] = entrada
        salida["resultado"] = resultado
        salida["resumen"] = resumen_viga(resultado)
        salida["envolventes"] = elemento.envolventes()
    else:
        entrada = entrada_columna_desde_elemento(elemento, opc)
        resultado = disenar_columna(entrada)
        salida["entrada"] = entrada
        salida["resultado"] = resultado
        salida["resumen"] = resumen_columna(resultado)
        salida["envolventes"] = elemento.envolventes()
    return salida


# ===========================================================================
# Resúmenes
# ===========================================================================
def resumen_viga(res: dict) -> dict:
    ests = res["estaciones"]
    filas = []
    for e in ests:
        pos, neg = e.get("positivo"), e.get("negativo")
        filas.append({
            "estacion": e["estacion"],
            "Mu_pos": e["demandas"].Mu_pos / 1e5,
            "Mu_neg": e["demandas"].Mu_neg / 1e5,
            "As_pos": pos["area"] if pos else 0.0,
            "As_neg": neg["area"] if neg else 0.0,
            "ref_pos": (f"{pos['n']} Ø {normas.VARILLAS[pos['varilla']].etiqueta}"
                        if pos else "—"),
            "ref_neg": (f"{neg['n']} Ø {normas.VARILLAS[neg['varilla']].etiqueta}"
                        if neg else "—"),
            "phiMn_pos": pos["phiMn"] / 1e5 if pos else 0.0,
            "phiMn_neg": neg["phiMn"] / 1e5 if neg else 0.0,
            "dcr_pos": pos["dcr"] if pos else 0.0,
            "dcr_neg": neg["dcr"] if neg else 0.0,
            "Vu": e["demandas"].Vu / 1e3,
            "corte": e.get("corte"),
        })
    corte_gob = res.get("corte")
    return {
        "filas": filas,
        "corte_gobernante": corte_gob,
        "As_min": res["As_min_10_5_1"],
        "As_min_sismo": res["As_min_21_4_4"],
        "As_max": res["As_max"],
        "rho_min": res["rho_min"], "rho_max": res["rho_max"],
        "verificaciones": res["verificaciones_dim"] + res["requisitos_sismicos"],
        "requiere_mayor_seccion": any(
            e.get("requiere_mayor_seccion_pos") or e.get("requiere_mayor_seccion_neg")
            for e in res["estaciones"]),
        "sismico": res["sismico"],
    }


def resumen_columna(res: dict) -> dict:
    e = res["entrada"]
    return {
        "refuerzo": res["barras"]["descripcion"],
        "As": res["barras"]["As"], "rho": res["barras"]["rho"],
        "dcr": res["dcr"],
        "estribos": (f"Ø {estribo_etiqueta(res['estribos']['estribo'])} @ "
                     f"{res['estribos']['s_conf']:g} cm "
                     f"({res['estribos']['ramas']} ramas)"),
        "s_ext": res["estribos"]["s_ext"],
        "esbeltez": res["esbeltez"],
        "verificaciones": res["verificaciones"],
        "insuficiente": res["insuficiente"],
        "phiPn_max": res["phiPn_max"], "P0": res["P0"],
        "Pu": max((d.P for d in e.demandas), default=e.Pu),
        "Mux": max((abs(d.M3) for d in e.demandas), default=e.Mux),
        "Muy": max((abs(d.M2) for d in e.demandas), default=e.Muy),
    }


def estribo_etiqueta(nombre: str) -> str:
    """Etiqueta comercial de un estribo ('#3' → '3/8"')."""
    v = normas.VARILLAS.get(nombre)
    return v.etiqueta if v else str(nombre)


# ===========================================================================
# Fuentes
# ===========================================================================
def crear_fuente_demo(**kwargs) -> FuenteETABS:
    from .etabs import ETABSDemo
    return ETABSDemo(**kwargs)


def crear_fuente_tablas(ruta_fuerzas: str, ruta_secciones: Optional[str] = None,
                        ruta_materiales: Optional[str] = None,
                        unidades: Optional[str] = None,
                        tipo_defecto: str = "Viga") -> FuenteETABS:
    from .etabs import ETABSTablas
    return ETABSTablas.desde_archivos(
        ruta_fuerzas, ruta_secciones, ruta_materiales, unidades, tipo_defecto)


def crear_fuente_etabs(adjuntar: bool = True,
                       ruta: Optional[str] = None) -> FuenteETABS:
    from .etabs import conectar
    return conectar(adjuntar=adjuntar, ruta=ruta)


# ===========================================================================
# Validación de resultados
# ===========================================================================
def verificar_resultado(salida: dict) -> List[dict]:
    """Lista de verificaciones globales (CUMPLE / NO CUMPLE) del resultado."""
    checks: List[dict] = []
    vistos = set()
    res = salida["resultado"]
    if salida["tipo"] == "Viga":
        for f in salida["resumen"]["verificaciones"]:
            checks.append({"nombre": f["nombre"], "valor": f.get("valor"),
                           "limite": f.get("limite"), "cumple": f.get("cumple"),
                           "ref": f.get("ref", "")})
        resumen = salida["resumen"]
        checks.append({
            "nombre": "Capacidad a flexión φMn ≥ Mu en todas las estaciones",
            "valor": max((max(f["dcr_pos"], f["dcr_neg"]) for f in resumen["filas"]),
                         default=0.0),
            "limite": 1.0,
            "cumple": all(max(f["dcr_pos"], f["dcr_neg"]) <= 1.0
                          for f in resumen["filas"]),
            "ref": "E.060 9.3 / 10.3"})
        corte = resumen["corte_gobernante"]
        if corte:
            checks.append({
                "nombre": "Capacidad a corte φVn ≥ Vu",
                "valor": corte["dcr"], "limite": 1.0,
                "cumple": corte["dcr"] <= 1.0, "ref": "E.060 11.4"})
            checks.append({
                "nombre": "Sección suficiente para corte (Vs ≤ Vs,max)",
                "valor": corte["Vs_req"], "limite": corte["Vs_max"],
                "cumple": corte["cumple_vs_max"], "ref": "E.060 11.4.7.9"})
    else:
        for f in salida["resumen"]["verificaciones"]:
            checks.append({"nombre": f["nombre"], "valor": f.get("valor"),
                           "limite": f.get("limite"), "cumple": f.get("cumple"),
                           "ref": f.get("ref", "")})
    # elimina verificaciones repetidas conservando el orden
    unicos = []
    for c in checks:
        clave = c["nombre"]
        if clave in vistos:
            continue
        vistos.add(clave)
        unicos.append(c)
    return unicos


def aprobado(salida: dict) -> bool:
    checks = verificar_resultado(salida)
    return all(c.get("cumple", False) for c in checks)
