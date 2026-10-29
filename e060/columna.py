"""
Diseño de columnas de concreto armado según la NTP E.060 (RNE, Perú).

Cubre:
  * Flexo-compresión uniaxial y biaxial (superficie de interacción exacta).
  * Carga axial máxima φPn,max (10.3.6) y cuantías 1 % ≤ ρ ≤ 6 % (10.9.1).
  * Esbeltez y magnificación de momentos (10.10): k·lu/r, límite
    34 − 12·(M1/M2) ≤ 40, δns.
  * Refuerzo transversal: estribos (7.10.5) y confinamiento sísmico
    (21.4.4.4): Ash/s, espaciamientos y número de ramas.
  * Selección automática de la distribución de barras.

Unidades internas: kgf, cm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import normas
from .normas import PHI, VARILLAS, ES
from .seccion import Barra, Fibra, LayoutBarras, Seccion


# ===========================================================================
# Entrada de datos
# ===========================================================================
@dataclass
class DemandaColumna:
    """Una combinación de carga: P, M2, M3 (kgf, kgf·cm)."""
    combo: str
    P: float
    M2: float = 0.0           # momento alrededor del eje local 2
    M3: float = 0.0           # momento alrededor del eje local 3
    V2: float = 0.0
    V3: float = 0.0
    T: float = 0.0


@dataclass
class EntradaColumna:
    nombre: str
    b: float
    h: float
    fc: float
    fy: float
    Pu: float = 0.0
    Mux: float = 0.0           # momento que flexiona sobre el peralte h
    Muy: float = 0.0           # momento que flexiona sobre el ancho b
    L: float = 300.0           # longitud libre [cm]
    k: float = 1.0
    recubrimiento: float = 4.0
    db_estribo: float = 0.953
    sismico: bool = True
    zunchada: bool = False
    amplificar: bool = False   # magnificar por esbeltez (10.10.7)
    beta_dns: float = 0.0
    M1: float = 0.0            # momentos extremos para Cm
    M2: float = 0.0
    # demanda por combinaciones (opcional, para envolvente)
    demandas: List[DemandaColumna] = field(default_factory=list)
    # disposición de barras (si se conoce); si no, se diseña
    layout: Optional[LayoutBarras] = None
    db_long_pref: Optional[str] = None
    # cortante
    Vu: float = 0.0
    estribo_pref: str = "#3"


# ===========================================================================
# Esbeltez
# ===========================================================================
def revisar_esbeltez(b: float, h: float, L: float, k: float,
                     M1: float, M2: float, Pu: float, fc: float,
                     beta_dns: float = 0.0) -> dict:
    """
    Verifica los efectos de esbeltez (E.060 10.10) y calcula la magnificación
    de momentos en cada eje local.

    Eje 3 (momento M3): flexiona sobre el peralte h  → I = b·h³/12
    Eje 2 (momento M2): flexiona sobre el ancho b    → I = h·b³/12

    Se aplica 10.10.7 (pórticos arriostrados):
        δns = Cm / (1 − Pu/(0.75·Pc)) ≥ 1.0
        Pc  = π²·EI/(k·lu)² ,  EI = 0.4·Ec·Ig/(1 + βdns)
        Cm  = 0.6 + 0.4·(M1/M2) ≥ 0.4
    """
    r = normas.radio_giro_aprox(b, h)
    klur = k * L / r
    limite = normas.limite_esbeltez(M1, M2)
    esbelto = klur > limite
    ec = normas.modulo_elasticidad_concreto(fc)
    ig3 = b * h ** 3 / 12.0          # flexión sobre h (M3)
    ig2 = h * b ** 3 / 12.0          # flexión sobre b (M2)
    ei3 = 0.4 * ec * ig3 / (1.0 + beta_dns)
    ei2 = 0.4 * ec * ig2 / (1.0 + beta_dns)
    lu = k * L
    pc3 = math.pi ** 2 * ei3 / lu ** 2
    pc2 = math.pi ** 2 * ei2 / lu ** 2
    relacion = 0.0 if abs(M2) < 1e-9 else max(-1.0, min(1.0, M1 / M2))
    cm = max(0.4, 0.6 + 0.4 * relacion)

    def delta(pc: float) -> float:
        if pc <= 0:
            return float("inf")
        den = 1.0 - Pu / (0.75 * pc)
        if den <= 0.10:
            return float("inf")
        return max(1.0, cm / den)

    d3 = delta(pc3) if esbelto else 1.0
    d2 = delta(pc2) if esbelto else 1.0
    return {
        "r": r, "klu_r": klur, "limite": limite, "esbelto": esbelto,
        "delta_ns": max(d3, d2), "delta_3": d3, "delta_2": d2,
        "delta_usado": max(d3, d2),
        "Cm": cm, "k": k, "lu": L,
        "M1_M2": relacion,
        "Ec": ec, "Ig3": ig3, "Ig2": ig2, "Pc3": pc3, "Pc2": pc2,
        "EI3": ei3, "EI2": ei2,
    }


# ===========================================================================
# Refuerzo transversal
# ===========================================================================
def disenar_estribos(b: float, h: float, fc: float, fy: float, db_long: float,
                     recubrimiento: float, db_estribo: float,
                     sismico: bool = True, zunchada: bool = False,
                     lu: Optional[float] = None, vu: float = 0.0,
                     pu: float = 0.0) -> dict:
    """
    Refuerzo transversal de columnas: requisitos generales (7.10.5) y
    confinamiento sismorresistente (21.4.4.4).

        Ash/s = MAYOR[ 0.3·(Ag/Ach − 1)·f'c/fy , 0.09·f'c/fy ]·bc
        lo    = MAYOR[b, h, lu/6, 45 cm]
        s     ≤ MENOR[b/4, h/4, 10 cm, 6·db_long, 24·db_est]

    Se elige el menor número de ramas que permita un espaciamiento
    constructivo (≥ 8 cm) y luego se ajusta s al corte y al confinamiento.
    """
    est = VARILLAS[db_estribo] if db_estribo in VARILLAS else VARILLAS["#3"]
    de = est.diametro_cm
    ae = est.area_cm2
    bc_x = max(b - 2.0 * recubrimiento - de, 5.0)     # centro a centro del estribo
    bc_y = max(h - 2.0 * recubrimiento - de, 5.0)
    ag = b * h
    ach = bc_x * bc_y
    bc = max(bc_x, bc_y)

    def ash_s(bc_dir: float) -> float:
        return max(0.3 * (ag / ach - 1.0) * fc / fy, 0.09 * fc / fy) * bc_dir

    ash_s_x = ash_s(bc_y)          # ramas que confinan la dirección b
    ash_s_y = ash_s(bc_x)          # ramas que confinan la dirección h
    ash_s_req = max(ash_s_x, ash_s_y)

    s_max_conf = normas.espaciamiento_confinamiento(b, h, db_long, de)
    s_max_conf = max(min(round(s_max_conf * 2) / 2.0, 10.0), 5.0)

    # --- corte (11.4 y 21.4.5.1) ----------------------------------------
    d_col = max(bc_x, bc_y) - db_long / 2.0
    phi_v = normas.phi_corte_columna(confina=True)
    vc = 0.53 * math.sqrt(fc) * min(b, h) * d_col * (1.0 + max(pu, 0.0) / (14.0 * ag))
    vc = min(vc, 0.93 * math.sqrt(fc) * min(b, h) * d_col)
    vu = abs(vu)
    vs_req = max(0.0, vu / phi_v - vc) if vu > 0 else 0.0

    # --- número de ramas y espaciamiento ---------------------------------
    ramas = 2
    for cand in (2, 3, 4, 5, 6, 8):
        if cand * ae / ash_s_req >= 8.0:      # espaciamiento constructivo
            ramas = cand
            break
        ramas = cand
    av = ramas * ae
    s_confin = av / ash_s_req if ash_s_req > 0 else 99.0
    s_corte = av * fy * d_col / vs_req if vs_req > 1e-9 else float("inf")
    s_lim = min(s_confin, s_max_conf, s_corte)
    if s_lim >= 10.0:
        s_conf = min(10.0, math.floor(s_lim))
    elif s_lim >= 5.0:
        s_conf = math.floor(s_lim * 2.0) / 2.0      # múltiplos de 0.5 cm
    else:
        s_conf = 5.0
    ash_prov = av
    ash_req = ash_s_req * s_conf

    # fuera de la zona de confinamiento (21.4.4.5)
    if sismico:
        s_ext = min(6.0 * db_long, 15.0)
    else:
        s_ext = min(16.0 * db_long, 48.0 * de, 30.0)
    s_ext = max(math.floor(s_ext / 2.5) * 2.5, s_conf)
    s_ext = min(s_ext, 20.0)

    lo = max(b, h, 45.0, (lu or 0.0) / 6.0)
    return {
        "estribo": est.nombre,
        "db_estribo": de,
        "Av_estribo": ae,
        "Ash_s": ash_s_req,
        "Ash_s_x": ash_s_x, "Ash_s_y": ash_s_y,
        "bc": bc, "bc_x": bc_x, "bc_y": bc_y,
        "Ag": ag, "Ach": ach,
        "s_conf": s_conf,
        "s_max_conf": s_max_conf,
        "ramas": int(ramas),
        "Ash_prov": ash_prov,
        "Ash_req": ash_req,
        "cumple_ash": ash_prov >= ash_req - 1e-6,
        "s_confin": s_confin,
        "s_ext": s_ext,
        "longitud_confinamiento": lo,
        "d_corte": d_col,
        "Vc": vc, "phi_corte": phi_v, "Av": av,
        "Vs_req": vs_req, "s_corte": s_corte,
        "s_corte_bajo": bool(s_corte < s_conf),
        "separacion_min_estribos": s_ext,
    }


# ===========================================================================
# Selección automática de refuerzo longitudinal
# ===========================================================================
def opciones_layout(b: float, h: float, rec: float, db_est: float,
                    catalogo: Sequence[str] = normas.VARILLAS_COLUMNA
                    ) -> List[LayoutBarras]:
    """Genera disposiciones candidatas (simétricas) de barras, por área creciente."""
    opciones: List[tuple] = []
    for nombre in catalogo:
        db = VARILLAS[nombre].diametro_cm
        for nx in range(2, 7):
            for ny in range(2, 7):
                if nx == 2 and ny == 2:
                    n = 4
                elif nx == 2 or ny == 2:
                    n = 2 * (nx + ny) - 4
                else:
                    n = 2 * (nx + ny) - 4
                lay = LayoutBarras(nx, ny, db, db_est, rec)
                n_real = len(lay.posiciones(b, h))
                if n_real < 4:
                    continue
                # separación libre entre barras de una misma cara ≤ 30 cm
                # (buena práctica y soporte de barras, E.060 7.10.5)
                util_x = b - 2 * (rec + db_est + db / 2)
                util_y = h - 2 * (rec + db_est + db / 2)
                # separación entre barras de una misma cara ≤ 30 cm: garantiza el
                # soporte lateral de las barras y permite crossties (7.10.5.3)
                if nx > 1 and util_x / (nx - 1) > 30.0 + 1e-9:
                    continue
                if ny > 1 and util_y / (ny - 1) > 30.0 + 1e-9:
                    continue
                if nx == 2 and ny == 2 and max(b, h) > 35.0:
                    continue
                area = n_real * VARILLAS[nombre].area_cm2
                if area / (b * h) > 0.065:      # por encima del 6 % no interesa
                    continue
                opciones.append((area, lay))
    opciones.sort(key=lambda t: t[0])
    # elimina disposiciones duplicadas en área y barras
    vistas = set()
    salida = []
    for area, lay in opciones:
        clave = (round(area, 2), lay.n_cara_x, lay.n_cara_y, round(lay.db, 3))
        if clave in vistas:
            continue
        vistas.add(clave)
        salida.append(lay)
    return salida


def construye_seccion(b: float, h: float, lay: LayoutBarras, fc: float, fy: float,
                      zunchada: bool = False, nombre: str = "") -> Seccion:
    barras = lay.posiciones(b, h)
    return Seccion(b, h, barras, fc, fy, nombre=nombre,
                   recubrimiento=lay.recubrimiento_libre,
                   db_estribo=lay.db_estribo, zunchada=zunchada)


def _dcr_biaxial(sec: Seccion, pu: float, mux: float, muy: float,
                 alfa_deg: Optional[float] = None) -> Tuple[float, dict]:
    """
    Relación demanda/capacidad en flexo-compresión biaxial.

    Parámetros
    ----------
    pu   : carga axial [kgf], compresión positiva (admite tracción negativa)
    mux  : momento alrededor del eje x local = M3 (flexiona sobre el peralte h)
    muy  : momento alrededor del eje y local = M2 (flexiona sobre el ancho b)

    Si uno de los momentos es despreciable (<5 % del otro) se resuelve el caso
    uniaxial; en caso contrario se resuelve la superficie de interacción
    P-Mx-My en la dirección exacta del momento resultante.
    """
    m_dem = math.hypot(mux, muy)
    info_base = {"Mdem": m_dem, "phiPmax": sec.phiPn_max(),
                 "phiPt": PHI.flexion * sec.fy * sec.As_total}
    # --- Tracción neta: φPn,t = 0.90·fy·As (E.060 10.3.5) ---------------
    if pu < 0:
        if -pu > info_base["phiPt"]:
            info_base.update(Mcap=0.0, metodo="tracción")
            return float("inf"), info_base
        # con tracción no hay "capacidad axial de compresión" que controlar
    elif pu >= sec.phiPn_max():
        info_base.update(Mcap=0.0, metodo="axial")
        return float("inf"), info_base

    if m_dem < 1e-6:
        # solicitación axial pura
        phi_p = sec.phiPn_max() if pu >= 0 else info_base["phiPt"]
        cap = phi_p
        info_base.update(Mcap=cap, metodo="axial pura")
        return (max(pu, 0.0) / cap if cap > 0 else float("inf")), info_base

    # --- Momento en un solo eje ----------------------------------------
    if abs(muy) <= 0.05 * abs(mux):
        cap, fb = sec.capacidad_uniaxial(90.0, pu)
        info = {**info_base, "Mcap": cap, "theta": fb.theta, "eps_t": fb.eps_t,
                "phi": fb.phi, "c": fb.c, "metodo": "uniaxial M3 (peralte h)"}
    elif abs(mux) <= 0.05 * abs(muy):
        cap, fb = sec.capacidad_uniaxial(0.0, pu)
        info = {**info_base, "Mcap": cap, "theta": fb.theta, "eps_t": fb.eps_t,
                "phi": fb.phi, "c": fb.c, "metodo": "uniaxial M2 (ancho b)"}
    else:
        alfa = math.degrees(math.atan2(muy, mux)) if alfa_deg is None else alfa_deg
        cap, fb = sec.capacidad_biaxial(pu, alfa)
        info = {**info_base, "Mcap": cap, "alfa": alfa, "theta": fb.theta,
                "eps_t": fb.eps_t, "phi": fb.phi, "c": fb.c,
                "metodo": "biaxial (superficie P-Mx-My)"}
    if cap <= 1e-9:
        return float("inf"), info
    return m_dem / cap, info


# ===========================================================================
# Diseño completo
# ===========================================================================
def disenar_columna(entrada: EntradaColumna) -> dict:
    """
    Diseño de columna: verifica la disposición dada o busca la más económica
    que cumpla todos los estados de carga con DCR ≤ 1.0.
    """
    b, h, fc, fy = entrada.b, entrada.h, entrada.fc, entrada.fy
    rec, db_est = entrada.recubrimiento, entrada.db_estribo

    # ---------- 1. Demanda envolvente ---------------------------------
    demandas = list(entrada.demandas)
    if not demandas:
        demandas = [DemandaColumna("Envolvente", entrada.Pu, entrada.Mux, entrada.Muy)]

    pu_max = max((d.P for d in demandas), default=0.0)
    pu_min = min((d.P for d in demandas), default=0.0)
    # Convención de ejes locales (coherente con ETABS):
    #   M3  → flexiona sobre el peralte h  → Mux
    #   M2  → flexiona sobre el ancho b    → Muy
    mux_max = max((abs(d.M3) for d in demandas), default=0.0)
    muy_max = max((abs(d.M2) for d in demandas), default=0.0)

    # ---------- 2. Esbeltez -------------------------------------------
    esbeltez = revisar_esbeltez(b, h, entrada.L, entrada.k, entrada.M1,
                                entrada.M2 or max(mux_max, 1.0), max(pu_max, 0.0),
                                fc, entrada.beta_dns)
    if entrada.amplificar:
        d3 = esbeltez["delta_3"]
        d2 = esbeltez["delta_2"]
        tope = 3.0                     # aviso: amplificación excesiva
        d3 = min(d3, tope) if math.isfinite(d3) else tope
        d2 = min(d2, tope) if math.isfinite(d2) else tope
    else:
        d3 = d2 = 1.0
    delta = max(d3, d2)

    # Excentricidad mínima (E.060 10.10.6.5): M2,min = Pu·(1.5 + 0.03·h) [cm]
    def momento_minimo(p: float, dim: float) -> float:
        return max(0.0, p) * (1.5 + 0.03 * dim)

    # ---------- 3. Búsqueda de la disposición de refuerzo -------------
    #   a) se ordenan las disposiciones por área de acero creciente;
    #   b) se evalúan primero unos pocos estados críticos (cribado);
    #   c) la primera disposición que cumple todos los estados es la adoptada.
    candidatas: List[LayoutBarras] = []
    if entrada.layout is not None:
        candidatas = [entrada.layout]
    else:
        catalogo = list(normas.VARILLAS_COLUMNA)
        if entrada.db_long_pref and entrada.db_long_pref in VARILLAS:
            catalogo = [entrada.db_long_pref]
        candidatas = opciones_layout(b, h, rec, db_est, catalogo)

    # Costo constructivo: área de acero con una penalización por número de barras
    # (menos barras = menos mano de obra y menor riesgo de congestión).
    def _costo(lay: LayoutBarras) -> float:
        n = len(lay.posiciones(b, h))
        area = n * VARILLAS.get(_nombre_varilla(lay.db), VARILLAS["#6"]).area_cm2
        return area * (1.0 + 0.05 * (n - 4))

    candidatas.sort(key=_costo)

    # estados de cribado: máxima flexión M3, máxima M2, máxima y mínima axial
    def _clave_severidad(d: DemandaColumna) -> float:
        return abs(d.P) / 50.0 + (abs(d.M2) + abs(d.M3)) / 1e5

    cribado = []
    if demandas:
        cribado.append(max(demandas, key=lambda d: abs(d.M3)))
        cribado.append(max(demandas, key=lambda d: abs(d.M2)))
        cribado.append(max(demandas, key=lambda d: d.P))
        cribado.append(min(demandas, key=lambda d: d.P))
        cribado.append(max(demandas, key=_clave_severidad))
    # elimina duplicados conservando el orden
    vistos = set()
    cribado_u = []
    for d in cribado:
        k = (round(d.P / 500.0), round(d.M2 / 1e4), round(d.M3 / 1e4))
        if k not in vistos:
            vistos.add(k)
            cribado_u.append(d)

    mejor: Optional[dict] = None
    fallidas: List[dict] = []

    def evaluar(sec: Seccion, lista: List[DemandaColumna],
                cortar_en_falla: bool = True) -> Tuple[float, List[dict]]:
        dcr_max = 0.0
        detalle = []
        for dem in lista:
            pu = dem.P if dem.P > 0 else dem.P          # compresión positiva
            mux = max(abs(dem.M3) * d3, momento_minimo(pu, h))
            muy = max(abs(dem.M2) * d2, momento_minimo(pu, b))
            dcr, info = _dcr_biaxial(sec, pu, mux, muy)
            detalle.append({"demanda": dem, "dcr": dcr, "info": info,
                            "Mux": mux, "Muy": muy})
            dcr_max = max(dcr_max, dcr if math.isfinite(dcr) else 99.0)
            if cortar_en_falla and dcr_max > 1.0:
                break
        return dcr_max, detalle

    for lay in candidatas:
        sec = construye_seccion(b, h, lay, fc, fy, entrada.zunchada, entrada.nombre)
        rho = sec.cuantia_geometrica()
        if rho < 0.01 - 1e-9 or rho > 0.06 + 1e-9:
            continue
        dcr_criba, _ = evaluar(sec, cribado_u)
        base = {
            "layout": lay, "seccion": sec, "rho": rho, "As": sec.As_total,
            "dcr": dcr_criba, "detalle": [], "n_barras": len(sec.barras),
        }
        if dcr_criba > 1.0:
            fallidas.append(base)
            continue
        dcr_total, detalle = evaluar(sec, demandas, cortar_en_falla=True)
        base["dcr"] = dcr_total
        base["detalle"] = detalle
        if dcr_total <= 1.0:
            mejor = base
            break                      # primera (menor área) que cumple todo
        fallidas.append(base)
        if mejor is None and len(fallidas) > 60:
            break

    if mejor is None:
        if fallidas:
            mejor = min(fallidas, key=lambda t: t["dcr"])
        else:
            lay = entrada.layout or LayoutBarras(2, 2, 1.905, db_est, rec)
            sec = construye_seccion(b, h, lay, fc, fy, entrada.zunchada, entrada.nombre)
            mejor = {"layout": lay, "seccion": sec,
                     "rho": sec.cuantia_geometrica(), "As": sec.As_total,
                     "dcr": float("inf"), "detalle": [], "n_barras": len(sec.barras)}
        mejor["insuficiente"] = True
        if not mejor["detalle"]:
            _, mejor["detalle"] = evaluar(mejor["seccion"], demandas, False)

    sec: Seccion = mejor["seccion"]
    lay: LayoutBarras = mejor["layout"]

    # ---------- 4. Estribos / confinamiento ---------------------------
    db_long = lay.db
    estribos = disenar_estribos(b, h, fc, fy, db_long, rec, db_est,
                                sismico=entrada.sismico, zunchada=entrada.zunchada,
                                lu=entrada.L, vu=entrada.Vu, pu=max(pu_max, 0.0))

    # ---------- 5. Cortante de columna (11.4 / 21.4.5) ---------------
    d_col = estribos["d_corte"]
    av = estribos["Av"]
    phi_v = estribos["phi_corte"]
    s_adoptado = min(estribos["s_conf"], estribos["s_corte"]) \
        if estribos["s_corte"] < estribos["s_conf"] else estribos["s_conf"]
    phi_vn = phi_v * (estribos["Vc"] + av * fy * d_col / max(s_adoptado, 1e-6))
    cortante = {
        "Vu": entrada.Vu, "Vc": estribos["Vc"], "phiVc": phi_v * estribos["Vc"],
        "Vs_req": estribos["Vs_req"], "Av": av, "s_corte": estribos["s_corte"],
        "s_adoptado": s_adoptado,
        "phiVn": phi_vn,
        "dcr": entrada.Vu / phi_vn if phi_vn > 0 else 0.0,
        "ramas": estribos["ramas"], "phi": phi_v, "d": d_col,
    }

    # ---------- 6. Diagramas para gráficos ----------------------------
    diagramas = []
    for th, etiqueta in ((0.0, "M sobre b (eje 2)"), (90.0, "M sobre h (eje 3)")):
        pts = sec.diagrama(th, n=40)
        diagramas.append({
            "theta": th, "etiqueta": etiqueta,
            "P": [p.phi * p.P / 1000.0 for p in pts],
            "M": [p.phi * math.hypot(p.Mx, p.My) / 1e5 for p in pts],
        })

    # ---------- 7. Verificaciones normativas -------------------------
    verificaciones = []
    verificaciones.append({
        "nombre": "Cuantía geométrica 1 % ≤ ρ ≤ 6 %",
        "valor": mejor["rho"], "limite": "0.01 – 0.06",
        "cumple": 0.01 <= mejor["rho"] <= 0.06, "ref": "E.060 10.9.1"})
    verificaciones.append({
        "nombre": "Número mínimo de barras ≥ 4",
        "valor": mejor["n_barras"], "limite": 4,
        "cumple": mejor["n_barras"] >= 4, "ref": "E.060 10.9.2"})
    verificaciones.append({
        "nombre": "Carga axial Pu ≤ φPn,max",
        "valor": pu_max / 1000.0, "limite": sec.phiPn_max() / 1000.0,
        "cumple": pu_max <= sec.phiPn_max(), "ref": "E.060 10.3.6"})
    verificaciones.append({
        "nombre": "DCR flexo-compresión biaxial ≤ 1.0",
        "valor": mejor["dcr"], "limite": 1.0,
        "cumple": mejor["dcr"] <= 1.0, "ref": "E.060 10.3 / 21.4"})
    verificaciones.append({
        "nombre": "Confinamiento Ash ≥ Ash requerido",
        "valor": estribos["Ash_prov"], "limite": estribos["Ash_req"],
        "cumple": estribos["cumple_ash"], "ref": "E.060 21.4.4.4"})
    verificaciones.append({
        "nombre": "Dimensión mínima ≥ 25 cm (sismorresistente)",
        "valor": min(b, h), "limite": 25.0, "cumple": min(b, h) >= 25.0,
        "ref": "E.060 21.4.4 / 21.3.1.2"})
    if entrada.sismico:
        relacion = min(b, h) / max(b, h)
        verificaciones.append({
            "nombre": "Relación de aspecto ≥ 0.4",
            "valor": relacion, "limite": 0.4, "cumple": relacion >= 0.4,
            "ref": "E.060 21.3.1.3"})
    # separación libre entre barras (7.6.3): ≥ max(1.5db, 4 cm)
    sep_libre = _separacion_libre(b, h, lay)
    verificaciones.append({
        "nombre": "Separación libre entre barras ≥ máx(1.5·db, 4 cm)",
        "valor": sep_libre, "limite": max(1.5 * lay.db, 4.0),
        "cumple": sep_libre >= max(1.5 * lay.db, 4.0) - 1e-6,
        "ref": "E.060 7.6.3"})
    verificaciones.append({
        "nombre": "Cortante Vu ≤ φVn",
        "valor": entrada.Vu / 1000.0, "limite": phi_vn / 1000.0,
        "cumple": entrada.Vu <= phi_vn, "ref": "E.060 11.1.1 / 21.4.5"})
    if pu_min < 0:
        phi_pt = PHI.flexion * fy * sec.As_total
        verificaciones.append({
            "nombre": "Tracción Pu ≤ φPn,t = 0.90·fy·As",
            "valor": -pu_min / 1000.0, "limite": phi_pt / 1000.0,
            "cumple": -pu_min <= phi_pt, "ref": "E.060 10.3.5"})
    verificaciones.append({
        "nombre": "Longitud de confinamiento lo ≥ máx(b, h, lu/6, 45 cm)",
        "valor": estribos["longitud_confinamiento"], "limite": 45.0,
        "cumple": True, "ref": "E.060 21.4.4.4"})

    return {
        "entrada": entrada,
        "b": b, "h": h, "fc": fc, "fy": fy,
        "barras": {
            "n": mejor["n_barras"], "db": db_long,
            "varilla": _nombre_varilla(db_long),
            "nx": lay.n_cara_x, "ny": lay.n_cara_y,
            "As": sec.As_total, "rho": mejor["rho"],
            "descripcion": (f"{mejor['n_barras']} Ø {_etiqueta_varilla(db_long)}"
                            f" — {lay.n_cara_x} por cara horizontal y "
                            f"{lay.n_cara_y} por cara vertical"),
            "posiciones": [(br.x, br.y, br.db) for br in sec.barras],
        },
        "seccion": sec,
        "dcr": mejor["dcr"],
        "detalle_demanda": mejor["detalle"],
        "insuficiente": mejor.get("insuficiente", False),
        "esbeltez": esbeltez,
        "delta": delta,
        "delta_3": d3,
        "delta_2": d2,
        "Mr_min": {"M3": max(0.0, pu_max) * (1.5 + 0.03 * h),
                   "M2": max(0.0, pu_max) * (1.5 + 0.03 * b)},
        "estribos": estribos,
        "cortante": cortante,
        "diagramas": diagramas,
        "verificaciones": verificaciones,
        "phiPn_max": sec.phiPn_max(),
        "P0": sec.P0,
        "Ag": sec.Ag,
    }


def _etiqueta_varilla(db: float) -> str:
    """Etiqueta comercial de una varilla por su diámetro ('#6' → '3/4" (#6)')."""
    v = VARILLAS.get(_nombre_varilla(db))
    return v.etiqueta if v else f"{db*10:.1f} mm"


def _separacion_libre(b: float, h: float, lay: LayoutBarras) -> float:
    """Mínima separación libre entre barras longitudinales (E.060 7.6.3)."""
    d_centro = lay.recubrimiento_libre + lay.db_estribo + lay.db / 2.0
    util_x = b - 2.0 * d_centro
    util_y = h - 2.0 * d_centro
    sep = float("inf")
    if lay.n_cara_x > 1:
        sep = min(sep, util_x / (lay.n_cara_x - 1) - lay.db)
    if lay.n_cara_y > 1:
        sep = min(sep, util_y / (lay.n_cara_y - 1) - lay.db)
    return sep if math.isfinite(sep) else 99.0


def _nombre_varilla(db: float) -> str:
    for k, v in VARILLAS.items():
        if abs(v.diametro_cm - db) < 1e-9:
            return k
    return f"Ø{db*10:.0f}mm"


# ===========================================================================
# Columna fuerte – viga débil (E.060 21.4.2.2)
# ===========================================================================
def verificar_columna_fuerte(momento_columnas: float, momento_vigas: float,
                             factor: float = 1.2) -> dict:
    """
    ΣMnc ≥ 1.2·ΣMnb en cada nudo (E.060 21.4.2.2). Los momentos deben ser
    capacidades nominales (no amplificadas por φ) en la cara del nudo.
    """
    requerido = factor * momento_vigas
    return {
        "suma_Mnc": momento_columnas,
        "suma_Mnb": momento_vigas,
        "requerido": requerido,
        "cumple": momento_columnas >= requerido,
        "ratio": momento_columnas / requerido if requerido > 0 else float("inf"),
    }
