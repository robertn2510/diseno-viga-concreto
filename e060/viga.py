"""
Diseño de vigas de concreto armado según la NTP E.060 (RNE, Perú).

Cubre:
  * Flexión: As requerido, As mínimo (10.5.1), cuantía máxima dúctil,
    selección de varillas verificando espaciamiento y número de capas.
  * Corte: Vc (11.3), Vs, espaciamientos, acero mínimo (11.4.6.3),
    límite Vs ≤ 2.1√f'c·bw·d (11.4.7.9) y distribución por zonas.
  * Torsión: torsión de compatibilidad / equilibrio (11.5 y 11.6).
  * Requisitos de pórticos sismorresistentes (cap. 21.4):
    dimensiones, cuantías mínimas, refuerzo continuo y confinamiento.
  * Capacidad φMn y verificación de que φMn ≥ Mu en cada estación.

Unidades internas: kgf, cm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import normas
from .normas import PHI, Varilla, VARILLAS, acero_minimo_flexion
from .seccion import area_acero_requerida, verificar_cuantias


# ===========================================================================
# Utilidades de selección de acero
# ===========================================================================
def separacion_minima(db: float, agregado: float = 2.0) -> float:
    """Separación libre mínima entre barras paralelas (E.060 7.6.1): 1.33·db, 2.5 cm, 1.33·agregado."""
    return max(2.5, 1.33 * db, 1.33 * agregado)


def barras_por_capa(b: float, db: float, rec: float, db_est: float,
                    agregado: float = 2.0) -> int:
    """Cantidad máxima de barras de diámetro db que caben en una capa."""
    util = b - 2.0 * (rec + db_est)
    s_min = separacion_minima(db, agregado)
    if util <= db:
        return 1
    return max(1, int(math.floor((util + s_min) / (db + s_min) + 1e-9)))


def _evaluar_opcion(n: int, var: Varilla, b: float, h: float, rec: float,
                    db_est: float, mu_kgfcm: float, fc: float, fy: float,
                    sismico: bool) -> Optional[dict]:
    """Verifica si 'n' barras de 'var' cubren el momento y caben en la sección."""
    if n < 2:
        return None
    n_capa = barras_por_capa(b, var.diametro_cm, rec, db_est)
    capas = int(math.ceil(n / n_capa))
    if capas > 2:
        return None
    s_min = separacion_minima(var.diametro_cm)
    if capas == 1:
        dc = rec + db_est + var.diametro_cm / 2.0
    else:
        # dos capas: separación vertical entre centros ≥ s_min
        separacion = max(s_min, var.diametro_cm)
        dc = rec + db_est + var.diametro_cm / 2.0 + separacion / 2.0
    d = h - dc
    if d <= 0.25 * h:
        return None
    as_prov = n * var.area_cm2

    # As requerido para el d real (iterando una vez es suficiente)
    try:
        as_req = area_acero_requerida(mu_kgfcm, b, d, fc, fy)
    except ValueError:
        return None
    as_min = normas.acero_minimo_flexion(b, d, fc, fy)
    as_diseno = max(as_req, as_min)
    if as_prov < as_diseno - 1e-9:
        return None

    a = as_prov * fy / (0.85 * fc * b)
    mn = as_prov * fy * (d - a / 2.0)
    phi_mn = PHI.flexion * mn
    # revisión de ductilidad (εt)
    b1 = normas.beta1(fc)
    c = a / b1
    eps_t = normas.EPS_CU * (d - c) / c if c > 0 else 0.0
    cumple_ductilidad = eps_t >= (0.004 if sismico else 0.005)
    rho = as_prov / (b * d)
    if sismico and rho > 0.025:
        return None
    return {
        "varilla": var.nombre,
        "n": int(n),
        "capas": capas,
        "barras_por_capa": int(min(n, n_capa)),
        "db": var.diametro_cm,
        "area": as_prov,
        "d": d,
        "dc": dc,
        "a": a,
        "c": c,
        "eps_t": eps_t,
        "rho": rho,
        "phiMn": phi_mn,
        "Mn": mn,
        "As_req": as_req,
        "As_min": as_min,
        "As_max": normas.cuantia_maxima(fc, fy, 0.004 if sismico else 0.005) * b * d,
        "exceso_pct": 100.0 * (as_prov - as_diseno) / max(as_diseno, 1e-9),
        "cumple_ductilidad": cumple_ductilidad,
        "cumple_capacidad": phi_mn >= mu_kgfcm,
        "dcr": mu_kgfcm / phi_mn if phi_mn > 0 else 99.0,
    }


def seleccionar_refuerzo(mu_kgfcm: float, b: float, h: float, rec: float,
                         db_est: float, fc: float, fy: float,
                         catalogo: Sequence[str] = normas.VARILLAS_VIGA,
                         sismico: bool = True,
                         varilla_preferida: Optional[str] = None) -> Optional[dict]:
    """
    Elige la combinación de barras comerciales que cubre Mu con el menor
    exceso de acero, verificando espaciamiento, capas y ductilidad.
    """
    candidatos: List[dict] = []
    for nombre in catalogo:
        var = VARILLAS[nombre]
        for n in range(2, 13):
            op = _evaluar_opcion(n, var, b, h, rec, db_est, mu_kgfcm, fc, fy, sismico)
            if op and op["cumple_capacidad"]:
                candidatos.append(op)
    if not candidatos:
        return None
    if varilla_preferida:
        pref = [c for c in candidatos if c["varilla"] == varilla_preferida]
        if pref:
            candidatos = pref
    # función de costo: exceso de acero + penalización por número de barras y capas
    # (criterio constructivo: pocas barras de mayor diámetro se arman más rápido)
    for o in candidatos:
        o["costo"] = (o["exceso_pct"] + 2.5 * (o["n"] - 2)
                      + 8.0 * (o["capas"] - 1))
    candidatos.sort(key=lambda o: (o["costo"], o["n"], o["barras_por_capa"]))
    return candidatos[0]


def posiciones_longitudinales(op: dict, b: float, h: float, rec: float,
                              db_est: float, cara: str = "inferior"):
    """
    Coordenadas (x, y, db) de las barras de una capa de refuerzo, respecto al
    centroide de la sección. Se usa para dibujar la sección en la memoria.
    """
    if not op:
        return []
    n = int(op["n"])
    db = float(op["db"])
    n_capa = max(1, int(op["barras_por_capa"]))
    x_half = b / 2.0 - rec - db_est - db / 2.0
    y = (-(h / 2.0 - rec - db_est - db / 2.0) if cara == "inferior"
         else (h / 2.0 - rec - db_est - db / 2.0))
    paso_vert = max(separacion_minima(db), db)
    barras = []
    restantes = n
    capa = 0
    while restantes > 0:
        en_capa = min(restantes, n_capa)
        yc = y + (1 if cara == "inferior" else -1) * capa * paso_vert
        for i in range(en_capa):
            x = (-x_half + 2.0 * x_half * i / (en_capa - 1)) if en_capa > 1 else 0.0
            barras.append((x, yc, db))
        restantes -= en_capa
        capa += 1
    return barras


# ===========================================================================
# Estructuras de datos
# ===========================================================================
@dataclass
class DemandaViga:
    """Solicitaciones en una estación o sección de la viga."""
    estacion: str                     # 'extremo i', 'centro', 'extremo j'
    Mu_pos: float = 0.0               # kgf·cm
    Mu_neg: float = 0.0               # kgf·cm
    Vu: float = 0.0                   # kgf
    Vu_sismo: float = 0.0             # kgf (cortante de combinaciones sísmicas)
    Vu_grav: float = 0.0              # kgf (cortante de combinaciones gravitacionales)
    Tu: float = 0.0                   # kgf·cm
    Nu: float = 0.0                   # kgf (tracción negativa)
    combo_pos: str = ""
    combo_neg: str = ""
    combo_vu: str = ""
    combo_tu: str = ""


@dataclass
class EntradaViga:
    nombre: str
    b: float
    h: float
    fc: float
    fy: float
    L: float = 600.0                  # luz libre [cm]
    recubrimiento: float = 4.0
    db_estribo: float = 0.953
    sismico: bool = True
    agregado: float = 2.0
    # demanda
    estaciones: List[DemandaViga] = field(default_factory=list)
    # capacidades de diseño para columnas fuertes (opcional)
    Mpr_extremos: Tuple[float, float] = (0.0, 0.0)   # capacidad probable en extremos
    Vu_sismo: float = 0.0                            # cortante por capacidad (21.4.5.1)
    usar_vc_sismo: bool = True
    # opciones
    varilla_pref: Optional[str] = None
    db_estribo_pref: Optional[str] = None
    por_capacidad: bool = True        # cortante sísmico por capacidad (21.4.5.1)
    ln: float = 0.0                   # luz libre [cm]


# ===========================================================================
# Diseño de corte
# ===========================================================================
def disenar_corte(vu_kgf: float, b: float, d: float, fc: float, fy: float,
                  h: float, db_long: float, tu_kgfcm: float = 0.0,
                  nu_kgf: float = 0.0, sismico: bool = True,
                  estribo_pref: str = "#3",
                  vc_cero: bool = False,
                  recubrimiento: float = 4.0,
                  vu_conf_kgf: Optional[float] = None,
                  av_s_torsion_extra: float = 0.0) -> dict:
    """
    Diseño del refuerzo transversal por corte y torsión (E.060 11.4 / 11.5
    y 21.4.5).

    vu_kgf      : cortante último en el resto de la luz (kgf)
    vu_conf_kgf : cortante de diseño en la zona de confinamiento (por
                  capacidad, E.060 21.4.5.1); si es None se usa vu_kgf
    vc_cero     : si True, Vc = 0 en la zona de confinamiento (rótula
                  plástica, E.060 21.4.5.2)

    Se obtienen dos espaciamientos: s_conf (zona de 2h junto a los apoyos) y
    s_resto (centro de la luz), con sus capacidades y DCR respectivos.
    """
    vu_resto = abs(vu_kgf)
    vu_conf = abs(vu_conf_kgf) if vu_conf_kgf is not None else vu_resto
    phi = PHI.corte                       # 0.85 (E.060 9.3.2.3 / 21.2.4.3)
    est = VARILLAS[estribo_pref]
    av = 2.0 * est.area_cm2               # estribo de dos ramas
    de = est.diametro_cm

    # --- Concreto --------------------------------------------------------
    vc = normas.cortante_concreto_viga(b, d, fc, nu_kgf, ag=b * h)
    vc = min(vc, 0.93 * math.sqrt(fc) * b * d)          # 11.3.2.2
    vc_conf = 0.0 if (sismico and vc_cero) else vc
    phi_vc = phi * vc
    phi_vc_conf = phi * vc_conf

    # --- Torsión (11.5.1: se desprecia si Tu ≤ 0.27·φ·√f'c·Acp²/Pcp) -----
    acp = b * h
    pcp = 2.0 * (b + h)
    tcr = 0.27 * math.sqrt(fc) * acp ** 2 / pcp
    torsion_requiere = abs(tu_kgfcm) > 0.27 * phi * math.sqrt(fc) * acp ** 2 / pcp
    at_s_torsion = 0.0
    if torsion_requiere and tu_kgfcm > 0:
        x1 = max(b - 2.0 * (recubrimiento + de), 2.0)
        y1 = max(h - 2.0 * (recubrimiento + de), 2.0)
        aoh = x1 * y1
        at_s_torsion = abs(tu_kgfcm) / (phi * 2.0 * 0.85 * aoh * fy)   # cm²/cm
    at_s_total = at_s_torsion + max(0.0, av_s_torsion_extra)

    # --- Acero transversal requerido -------------------------------------
    vs_req = max(0.0, vu_resto / phi - vc)
    vs_req_conf = max(0.0, vu_conf / phi - vc_conf)
    av_s_min = max(0.062 * math.sqrt(fc) * b / fy, 0.35 * b / fy)   # 11.4.6.3
    av_s_corte = max(vs_req * av / (fy * d), av_s_min) if d > 0 else av_s_min
    av_s_conf = max(vs_req_conf * av / (fy * d), av_s_min) if d > 0 else av_s_min
    av_s = max(av_s_corte, 2.0 * at_s_total)
    av_s_c = max(av_s_conf, 2.0 * at_s_total)

    vs_max = normas.cortante_maximo_acero(b, d, fc)     # 11.4.7.9
    cumple_vs_max = max(vs_req, vs_req_conf) <= vs_max
    vu_max = phi * (vc + vs_max)
    seccion_ok = max(vu_resto, vu_conf) <= vu_max

    # --- Espaciamientos ---------------------------------------------------
    s_max_general = min(d / 2.0, 30.0) if sismico else min(d / 2.0, 60.0)
    if max(vs_req, vs_req_conf) > 1.1 * math.sqrt(fc) * b * d:
        s_max_general = min(s_max_general, d / 4.0)
    if sismico:
        s_conf_lim = min(normas.espaciamiento_max_estribos(d, h, vu_conf, phi_vc_conf,
                                                           sismico=True),
                         d / 4.0, 8.0 * db_long, 24.0 * de, 30.0)
    else:
        s_conf_lim = s_max_general

    s_req = av / av_s if av_s > 0 else 1e9
    s_req_conf = av / av_s_c if av_s_c > 0 else 1e9
    s_lim_conf = min(s_req_conf, s_conf_lim)

    def redondear(s_val: float, minimo: float = 5.0) -> float:
        if s_val < 10.0:
            return max(minimo, math.floor(s_val))
        if s_val < 15.0:
            return max(minimo, math.floor(s_val / 2.5) * 2.5)
        return max(minimo, math.floor(s_val / 5.0) * 5.0)

    s_conf = redondear(s_lim_conf)
    s_resto = redondear(min(s_req, s_max_general))
    s_resto = max(s_conf, s_resto)          # el centro nunca con menos estribos
    s_adoptado = min(s_conf, s_resto)

    # --- Capacidades provistas y DCR --------------------------------------
    vs_prov_conf = av * fy * d / s_conf if s_conf > 0 else 0.0
    vs_prov_resto = av * fy * d / s_resto if s_resto > 0 else 0.0
    phi_vn_conf = phi * (vc_conf + vs_prov_conf)
    phi_vn_resto = phi * (vc + vs_prov_resto)
    dcr_conf = vu_conf / phi_vn_conf if phi_vn_conf > 0 else 99.0
    dcr_resto = vu_resto / phi_vn_resto if phi_vn_resto > 0 else 99.0
    dcr = max(dcr_conf, dcr_resto)

    zonas = []
    l_conf = min(2.0 * h, 60.0)             # E.060 21.4.4.4 (2h desde el apoyo)
    if sismico:
        zonas = [
            {"zona": f"Confinamiento (0 a {l_conf:.0f} cm = 2h)", "longitud_cm": l_conf,
             "s": s_conf},
            {"zona": "Resto de la luz", "longitud_cm": None, "s": s_resto},
        ]
    else:
        zonas = [{"zona": "Toda la luz", "longitud_cm": None, "s": s_resto}]

    return {
        "estribo": estribo_pref,
        "db_estribo": de,
        "Av": av,
        "estribo_ramas": 2,
        "Vc": vc,
        "phiVc": phi_vc,
        "Vc_conf": vc_conf,
        "Vs_req": vs_req,
        "Vs_req_conf": vs_req_conf,
        "Vs_max": vs_max,
        "vu_max": vu_max,
        "Vu": vu_resto,
        "Vu_conf": vu_conf,
        "d": d,
        "phi": phi,
        "Tu": tu_kgfcm,
        "torsion_requiere": torsion_requiere,
        "Tcr": tcr,
        "At_s": at_s_torsion,
        "Av_s_corte": av_s_corte,
        "Av_s_min": av_s_min,
        "Av_s": av_s,
        "Av_s_conf": av_s_c,
        "s_req": s_req,
        "s_req_conf": s_req_conf,
        "s_max": s_max_general,
        "s_conf_lim": s_conf_lim,
        "s_conf": s_conf,
        "s_resto": s_resto,
        "s_adoptado": s_adoptado,
        "Vs_prov_conf": vs_prov_conf,
        "Vs_prov_resto": vs_prov_resto,
        "phiVn_conf": phi_vn_conf,
        "phiVn": phi_vn_resto,
        "dcr_conf": dcr_conf,
        "dcr_resto": dcr_resto,
        "dcr": dcr,
        "cumple_vs_max": cumple_vs_max,
        "cumple_seccion": seccion_ok,
        "vc_cero": bool(sismico and vc_cero),
        "zonas": zonas,
        "phi_vc_conf": phi_vc_conf,
        "zona_conf_cm": l_conf,
    }


# ===========================================================================
# Diseño de torsión (resumen numérico)
# ===========================================================================
def disenar_torsion(tu_kgfcm: float, b: float, h: float, fc: float, fy: float,
                    recubrimiento: float, db_estribo: float,
                    at_s: float = 0.0) -> dict:
    """Verificación de torsión según E.060 11.5 (sección hueca equivalente)."""
    acp = b * h
    pcp = 2.0 * (b + h)
    tcr = 0.27 * math.sqrt(fc) * acp ** 2 / pcp
    t_limite = PHI.torsion * tcr
    x1 = b - 2 * (recubrimiento + db_estribo)
    y1 = h - 2 * (recubrimiento + db_estribo)
    aoh = x1 * y1
    ph = 2 * (x1 + y1)
    at_s_min = 0.062 * math.sqrt(fc) * b / fy
    al_min = 0.42 * math.sqrt(fc) * aoh * at_s_min / ph if ph > 0 else 0.0
    return {
        "Acp": acp, "Pcp": pcp, "Tcr": tcr, "phiTcr": t_limite,
        "Aoh": aoh, "Ph": ph,
        "requiere_armadura": abs(tu_kgfcm) > t_limite,
        "Ats": at_s,
        "Ats_min": at_s_min,
        "Al_min": al_min,
    }


# ===========================================================================
# Requisitos sismorresistentes de vigas (E.060 21.4.4)
# ===========================================================================
def requisitos_sismicos(b: float, h: float, d: float, fc: float, fy: float,
                        luz_libre: float, db_est: float) -> List[dict]:
    """
    Requisitos sismorresistentes adicionales del capítulo 21.4.
    Las verificaciones geométricas (b, b/h, luz) se informan en
    `verificaciones_dim` para no duplicar el cuadro de verificaciones.
    """
    checks = []
    as_min_sismo = max(0.25 * math.sqrt(fc) / fy, 1.4 / fy) * b * d
    checks.append({
        "nombre": "As mínimo sismorresistente (0.25√f'c/fy ; 1.4/fy)·b·d",
        "valor": as_min_sismo, "limite": as_min_sismo, "cumple": True,
        "ref": "E.060 21.4.4.1"})
    checks.append({
        "nombre": "Cuantía máxima ρ ≤ 0.025",
        "valor": 0.025, "limite": 0.025, "cumple": True,
        "ref": "E.060 21.4.4.1"})
    checks.append({
        "nombre": "Al menos 2 barras continuas superior e inferior",
        "valor": 2, "limite": 2, "cumple": True,
        "ref": "E.060 21.4.4.1"})
    return checks


def acero_minimo_sismico(b: float, d: float, fc: float, fy: float) -> float:
    """As mínimo en vigas sismorresistentes: máx(0.25√f'c/fy ; 1.4/fy)·b·d."""
    return max(0.25 * math.sqrt(fc) / fy, 1.4 / fy) * b * d


def acero_maximo(b: float, d: float, fc: float, fy: float) -> float:
    """As máximo para ρ ≤ 0.025 (E.060 21.4.4.1)."""
    return 0.025 * b * d


# ===========================================================================
# Diseño completo de la viga
# ===========================================================================
def disenar_viga(entrada: EntradaViga) -> dict:
    """
    Ejecuta el diseño completo de una viga y devuelve un diccionario con
    todos los resultados (usado por la memoria de cálculo).
    """
    b, h, fc, fy = entrada.b, entrada.h, entrada.fc, entrada.fy
    rec, db_est = entrada.recubrimiento, entrada.db_estribo
    sismico = entrada.sismico
    d0 = h - rec - db_est - 1.905 / 2.0      # peralte inicial estimado

    # ---------- 1. Verificaciones previas ------------------------------
    verificaciones_dim = []
    verificaciones_dim.append({
        "nombre": "Ancho mínimo b ≥ 25 cm", "valor": b, "limite": 25.0,
        "cumple": b >= 25.0, "ref": "E.060 21.4.4 / 21.3.1.2"})
    verificaciones_dim.append({
        "nombre": "Relación b/h ≥ 0.3", "valor": b / h, "limite": 0.3,
        "cumple": b / h >= 0.3, "ref": "E.060 21.4.4 / 21.3.1.3"})
    verificaciones_dim.append({
        "nombre": "Luz libre ≥ 4·h", "valor": entrada.L, "limite": 4 * h,
        "cumple": entrada.L >= 4 * h, "ref": "E.060 21.4.4 / 21.3.1.4"})
    verificaciones_dim.append({
        "nombre": "Peralte efectivo d ≥ 0.3·h", "valor": d0, "limite": 0.3 * h,
        "cumple": d0 >= 0.3 * h, "ref": "Buena práctica"})

    # ---------- 2. Flexión por estación --------------------------------
    disenos = []
    if not entrada.estaciones:
        entrada.estaciones = [DemandaViga("centro", Mu_pos=0.0)]

    for est in entrada.estaciones:
        item = {"estacion": est.estacion, "demandas": est}
        # Momento positivo
        op_pos = None
        if est.Mu_pos > 1.0:
            op_pos = seleccionar_refuerzo(est.Mu_pos, b, h, rec, db_est, fc, fy,
                                          sismico=sismico, varilla_preferida=entrada.varilla_pref)
        # Momento negativo
        op_neg = None
        if est.Mu_neg > 1.0:
            op_neg = seleccionar_refuerzo(est.Mu_neg, b, h, rec, db_est, fc, fy,
                                          sismico=sismico, varilla_preferida=entrada.varilla_pref)
        # As mínimo sismorresistente
        as_min_sismo = acero_minimo_sismico(b, d0, fc, fy) if sismico else 0.0

        if op_pos is None and est.Mu_pos > 1.0:
            op_pos = _opcion_fuera_de_rango(est.Mu_pos, b, h, fc, fy, rec, db_est)
            item["requiere_mayor_seccion_pos"] = True
        if op_neg is None and est.Mu_neg > 1.0:
            op_neg = _opcion_fuera_de_rango(est.Mu_neg, b, h, fc, fy, rec, db_est)
            item["requiere_mayor_seccion_neg"] = True

        # Verificar mínimo sismorresistente en ambas caras
        for clave in ("pos", "neg"):
            op = op_pos if clave == "pos" else op_neg
            if op is not None and sismico and op["area"] < as_min_sismo:
                # incrementar barras hasta cumplir
                mu_equiv = max(est.Mu_pos if clave == "pos" else est.Mu_neg, 1.0)
                mejor = _buscar_con_area_minima(mu_equiv, as_min_sismo, b, h, fc, fy,
                                                rec, db_est, sismico)
                if mejor:
                    if clave == "pos":
                        op_pos = mejor
                    else:
                        op_neg = mejor
        # refuerzo mínimo continuo en ambas caras (E.060 21.4.4.1)
        if sismico:
            area_min = max(as_min_sismo, acero_minimo_flexion(b, d0, fc, fy))
            if op_pos is None:
                op_pos = _buscar_con_area_minima(max(est.Mu_pos, 1.0), area_min,
                                                 b, h, fc, fy, rec, db_est, sismico)
            if op_neg is None:
                op_neg = _buscar_con_area_minima(max(est.Mu_neg, 1.0), area_min,
                                                 b, h, fc, fy, rec, db_est, sismico)

        item["positivo"] = op_pos
        item["negativo"] = op_neg
        item["As_min_sismo"] = as_min_sismo
        disenos.append(item)


    # ---------- 4. Diseño por corte y torsión (global) -----------------
    d_ref = max((op["d"] for est in disenos for op in (est["positivo"], est["negativo"])
                 if op), default=d0)
    db_long = max((op["db"] for est in disenos for op in (est["positivo"], est["negativo"])
                   if op), default=1.905)

    vu_combos = max((e.Vu for e in entrada.estaciones), default=0.0)
    vu_grav = max((getattr(e, "Vu_grav", 0.0) for e in entrada.estaciones), default=0.0)
    tu_max = max((e.Tu for e in entrada.estaciones), default=0.0)

    # momentos probables en los extremos (1.25·fy, sin φ) → E.060 21.4.5.1
    def _mpr(op) -> float:
        if not op:
            return 0.0
        a = 1.25 * op["area"] * fy / (0.85 * fc * b)
        return 1.25 * op["area"] * fy * (op["d"] - a / 2.0)

    def _mpr_extremo(item) -> float:
        return max(_mpr(item.get("positivo")), _mpr(item.get("negativo")))

    mpr_i = _mpr_extremo(disenos[0]) if disenos else 0.0
    mpr_j = _mpr_extremo(disenos[-1]) if disenos else 0.0
    ln = entrada.ln or max(entrada.L - entrada.h, 0.5 * entrada.L)
    vu_capacidad = (mpr_i + mpr_j) / ln if ln > 0 else 0.0
    vu_cap_total = vu_capacidad + vu_grav

    if sismico and entrada.por_capacidad:
        vu_diseno = max(vu_combos, vu_cap_total)
        # E.060 21.4.5.2: Vc = 0 si el sismoinducido ≥ 50 % del cortante de diseño
        vc_cero = vu_capacidad >= 0.5 * max(vu_diseno, 1.0)
    else:
        vu_diseno = vu_combos
        vc_cero = False

    corte = disenar_corte(
        vu_combos, b, d_ref, fc, fy, h, db_long, tu_kgfcm=tu_max,
        nu_kgf=min((e.Nu for e in entrada.estaciones), default=0.0),
        sismico=sismico, estribo_pref=entrada.db_estribo_pref or "#3",
        vc_cero=vc_cero, recubrimiento=rec,
        vu_conf_kgf=max(vu_diseno, vu_combos))
    corte["Mpr_i"] = mpr_i
    corte["Mpr_j"] = mpr_j
    corte["ln"] = ln
    corte["Vu_capacidad"] = vu_capacidad
    corte["Vu_grav"] = vu_grav
    corte["Vu_diseno"] = max(vu_diseno, vu_combos)
    corte["sismo_inducido"] = vu_capacidad
    torsion = disenar_torsion(tu_max, b, h, fc, fy, rec, db_est, corte["At_s"])
    for item in disenos:
        item["corte"] = corte
        item["torsion"] = torsion

    # ---------- 4b. Refuerzo en los extremos (21.4.4.1) ---------------
    verif_extremos = []
    if sismico and disenos:
        for etiqueta, item in (("i", disenos[0]), ("j", disenos[-1])):
            ap = item["positivo"]["area"] if item.get("positivo") else 0.0
            an = item["negativo"]["area"] if item.get("negativo") else 0.0
            mayor = max(ap, an)
            menor = min(ap, an)
            verif_extremos.append({
                "nombre": f"Extremo {etiqueta}: As menor ≥ 25 % del As mayor",
                "valor": menor / mayor if mayor > 0 else 0.0, "limite": 0.25,
                "cumple": mayor <= 0 or menor >= 0.25 * mayor,
                "ref": "E.060 21.4.4.1"})

    # ---------- 5. Refuerzo longitudinal mínimo continuo --------------
    as_min_101 = acero_minimo_flexion(b, d0, fc, fy)          # E.060 10.5.1
    as_min_214 = acero_minimo_sismico(b, d0, fc, fy) if sismico else as_min_101
    as_max = min(normas.cuantia_maxima(fc, fy, 0.004) * b * d0,
                 acero_maximo(b, d0, fc, fy) if sismico else float("inf"))

    return {
        "entrada": entrada,
        "b": b, "h": h, "d0": d0, "fc": fc, "fy": fy, "L": entrada.L,
        "recubrimiento": rec, "db_estribo": db_est,
        "sismico": sismico,
        "verificaciones_dim": verificaciones_dim,
        "estaciones": disenos,
        "corte": corte,
        "torsion": torsion,
        "corte_gobernante": corte,
        "As_min_10_5_1": as_min_101,
        "As_min_21_4_4": as_min_214,
        "As_max": as_max,
        "rho_min": as_min_101 / (b * d0),
        "rho_max": as_max / (b * d0),
        "requisitos_sismicos": (requisitos_sismicos(b, h, d0, fc, fy, entrada.L, db_est)
                                + verif_extremos) if sismico else [],
    }


def _opcion_fuera_de_rango(mu: float, b: float, h: float, fc: float, fy: float,
                           rec: float, db_est: float) -> dict:
    """Devuelve la mejor opción posible aunque la sección sea insuficiente."""
    var = VARILLAS["#8"]
    n = 6
    d = h - rec - db_est - var.diametro_cm
    a = n * var.area_cm2 * fy / (0.85 * fc * b)
    mn = n * var.area_cm2 * fy * (d - a / 2)
    return {
        "varilla": var.nombre, "n": n, "capas": 2,
        "barras_por_capa": 3, "db": var.diametro_cm,
        "area": n * var.area_cm2, "d": d,
        "dc": h - d, "a": a, "c": a / normas.beta1(fc),
        "eps_t": normas.EPS_CU * (d - a / normas.beta1(fc)) / (a / normas.beta1(fc)),
        "rho": n * var.area_cm2 / (b * d),
        "phiMn": PHI.flexion * mn, "Mn": mn,
        "As_req": 0.0, "As_min": 0.0, "As_max": float("inf"),
        "exceso_pct": 0.0, "cumple_ductilidad": True,
        "cumple_capacidad": False,
        "dcr": mu / (PHI.flexion * mn) if mn > 0 else 99.0,
        "insuficiente": True,
    }


def _buscar_con_area_minima(mu: float, area_min: float, b: float, h: float,
                            fc: float, fy: float, rec: float, db_est: float,
                            sismico: bool) -> Optional[dict]:
    """Busca refuerzo que cumpla capacidad y área mínima exigida."""
    mejor = None
    for nombre in normas.VARILLAS_VIGA:
        var = VARILLAS[nombre]
        for n in range(2, 13):
            op = _evaluar_opcion(n, var, b, h, rec, db_est, max(mu, 1.0), fc, fy, sismico)
            if op and op["cumple_capacidad"] and op["area"] >= area_min:
                if mejor is None or op["area"] < mejor["area"]:
                    mejor = op
    return mejor
