"""
Diseño a cortante de vigas de pórticos especiales y sistemas duales tipo II.

Se aplican simultáneamente:

* E.060 11.3.1.1:  Vc = 0.53·√(f'c)·b·d
* E.060 11.5.6.9:  Vs ≤ 2.1·√(f'c)·b·d
* E.060 11.5.6.3:  Av,min/s = máx(0.20√(f'c)·b/fy; 3.5·b/fy)
* E.060 11.5.5.1:  s ≤ d/2 ≤ 60 cm
* E.060 21.5.4.1:  Vu por capacidad = (Mpr,i + Mpr,j)/ln + cortante gravitacional
* E.060 21.5.4.2:  Vc = 0 en la zona de confinamiento cuando el sismo aporta al
  menos la mitad del cortante y la carga axial es baja
* E.060 21.5.3.1:  zona de confinamiento = 2h desde la cara del apoyo
* E.060 21.5.3.3:  primer estribo a ≤ 5 cm de la cara
* E.060 21.5.3.4:  s ≤ mín(d/4; 8db,long; 24db,estribo; 30 cm)
* E.060 21.5.3.5:  fuera de la zona de confinamiento s ≤ d/2
* E.060 21.5.3.6:  separación entre ramas verticales ≤ 30 cm
"""

from __future__ import annotations

from math import floor, inf, isfinite

from ..config import ConfiguracionDiseno
from ..modelos import (
    Formula,
    FuerzasViga,
    GeometriaViga,
    Materiales,
    ResultadoCortante,
    ResultadoFlexion,
    Verificacion,
    VigaETABS,
)
from ..normativa import e060
from .varillas import peso_estribos_kg, seleccionar_estribo


def _redondear_abajo(valor: float, paso: float = 1.0) -> float:
    if valor is None or not isfinite(valor):
        return valor
    return max(paso, floor(valor / paso + 1e-9) * paso)


def _mpr(
    res_t: ResultadoFlexion | None,
    res_c: ResultadoFlexion | None,
    geom: GeometriaViga,
    mat: Materiales,
) -> float:
    """Mpr = 1.25·Mn para una dirección de flexión (E.060 21.5.4.1)."""
    if res_t is None or res_t.seleccion is None:
        return 0.0
    d_t = geom.h - res_t.seleccion.y_cm
    if res_c is not None and res_c.seleccion is not None:
        As_c = res_c.seleccion.area_cm2
        # d' se mide desde la cara comprimida, que es la cara de la armadura
        # de compresión; y_cm ya está referido a esa cara.
        d_c = res_c.seleccion.y_cm
    else:
        As_c = 0.0
        d_c = geom.r + geom.diametro_estribo + 1.905 / 2.0
    cap = e060.momento_nominal(
        res_t.seleccion.area_cm2, As_c, geom.b, d_t, d_c,
        mat.fc, mat.fy, mat.es,
    )
    return 1.25 * cap.Mn_tm


def _s_requerido(
    Vu_t: float,
    Vc_t: float,
    phi: float,
    Av_cm2: float,
    fy: float,
    d_cm: float,
) -> tuple[float, float]:
    """Devuelve (Vs requerido en kgf, s requerido en cm).

    ``Vu_t`` y ``Vc_t`` se reciben en toneladas; internamente se convierten a
    kgf para obtener el espaciamiento en cm.
    """
    Vs_t = Vu_t / phi - Vc_t
    if Vs_t <= 1e-9:
        return 0.0, inf
    Vs_kg = Vs_t * 1_000.0
    return Vs_kg, Av_cm2 * fy * d_cm / Vs_kg


def _distribucion(
    ln_m: float,
    L_conf_m: float,
    s_conf_i: float,
    s_conf_j: float,
    s_central: float,
) -> tuple[str, str, str, int]:
    """
    Genera la distribución de estribos y cuenta las piezas.

    Devuelve ``(texto_i, texto_j, texto_central, total)``.
    """
    s_conf_i_m = s_conf_i / 100.0
    s_conf_j_m = s_conf_j / 100.0
    s_central_m = s_central / 100.0

    def posiciones(desde: float, hasta: float, s: float) -> list[float]:
        if s <= 0:
            return []
        n = int(floor((hasta - desde) / s + 1e-9))
        return [desde + k * s for k in range(n + 1)]

    izq = posiciones(0.05, L_conf_m, s_conf_i_m)
    if abs(s_conf_i_m - s_conf_j_m) < 1e-9:
        der = [ln_m - x for x in izq]
    else:
        der = [ln_m - x for x in posiciones(0.05, L_conf_m, s_conf_j_m)]

    # Zona central: se evita duplicar los estribos de los extremos.
    x_ini = L_conf_m
    x_fin = ln_m - L_conf_m
    central: list[float] = []
    if x_fin > x_ini + 1e-9 and s_central_m > 0:
        x = x_ini
        while x <= x_fin + 1e-9:
            if x > 1e-6 and (not izq or min(abs(x - p) for p in izq) > 1e-3) \
                    and (not der or min(abs(x - p) for p in der) > 1e-3):
                central.append(x)
            x += s_central_m

    todas = sorted({round(p, 3) for p in izq + der + central})
    total = len(todas)

    def texto(n_pos: int, s_conf_cm: float, invertido: bool = False) -> str:
        if n_pos <= 1:
            return "1 @ 0.05 m"
        if invertido:
            # El tramo derecho se detalla desde el eje de columna hacia el
            # centro de la luz: primero la separación menor y al final 5 cm.
            return f"{n_pos - 1} @ {s_conf_cm/100:.2f}, 1 @ 0.05 m"
        return f"1 @ 0.05, {n_pos - 1} @ {s_conf_cm/100:.2f} m"

    texto_i = texto(len(izq), s_conf_i)
    texto_j = texto(len(der), s_conf_j, invertido=True)
    texto_c = (
        f"{len(central)} @ {s_central/100:.2f} m" if central
        else "sin tramo central"
    )
    return texto_i, texto_j, texto_c, total


def disenar_cortante(
    viga: VigaETABS,
    fuerzas: FuerzasViga,
    flexion: list[ResultadoFlexion],
    config: ConfiguracionDiseno,
) -> ResultadoCortante:
    geom, mat = viga.geometria, viga.materiales
    b, h, r = geom.b, geom.h, geom.r
    ln = geom.ln
    advertencias: list[str] = []

    # ------------------------------------------------------------------
    # Resistencias probables en los extremos
    # ------------------------------------------------------------------
    res_izq_sup = next((x for x in flexion if x.ubicacion.startswith("Apoyo izquierdo") and x.lado == "superior"), None)
    res_izq_inf = next((x for x in flexion if x.ubicacion.startswith("Apoyo izquierdo") and x.lado == "inferior"), None)
    res_der_sup = next((x for x in flexion if x.ubicacion.startswith("Apoyo derecho") and x.lado == "superior"), None)
    res_der_inf = next((x for x in flexion if x.ubicacion.startswith("Apoyo derecho") and x.lado == "inferior"), None)

    if None in (res_izq_sup, res_izq_inf, res_der_sup, res_der_inf):
        advertencias.append(
            "No se encontraron las cuatro secciones de apoyo; "
            "Mpr se calcula con la información disponible."
        )

    Mpr_hog_izq = _mpr(res_izq_sup, res_izq_inf, geom, mat)
    Mpr_sag_izq = _mpr(res_izq_inf, res_izq_sup, geom, mat)
    Mpr_hog_der = _mpr(res_der_sup, res_der_inf, geom, mat)
    Mpr_sag_der = _mpr(res_der_inf, res_der_sup, geom, mat)

    Ve = max(
        (Mpr_hog_izq + Mpr_sag_der) / ln,
        (Mpr_sag_izq + Mpr_hog_der) / ln,
    ) if ln > 0 else 0.0

    # ------------------------------------------------------------------
    # Cortante gravitacional y envolvente de ETABS
    # ------------------------------------------------------------------
    Vg_i, Vg_j = fuerzas.V_gravedad_caras
    Vg_c = fuerzas.V_gravedad_centro

    def V2_clave(nombre: str) -> float:
        est = fuerzas.estaciones_clave.get(nombre)
        return est.V2_max_t if est else 0.0

    Vu_env_i = V2_clave("Cara-I")
    Vu_env_j = V2_clave("Cara-J")
    Vu_env_c = V2_clave("Centro")

    Vu_i = max(Ve + Vg_i, Vu_env_i)
    Vu_j = max(Ve + Vg_j, Vu_env_j)
    Vu_c = max(Ve + Vg_c, Vu_env_c)
    Vu_diseno = max(Vu_i, Vu_j, Vu_c)

    # Peralte efectivo de cortante: el menor de las secciones críticas.
    d_cortante = min((x.d_cm for x in flexion if x.seleccion), default=geom.d_estimado)
    if d_cortante <= 0:
        d_cortante = geom.d_estimado

    # ------------------------------------------------------------------
    # Resistencia del concreto
    # ------------------------------------------------------------------
    Vc = e060.vc_concreto(mat.fc, b, d_cortante) / 1_000.0      # t
    Ag = b * h
    limite_axial = 0.05 * mat.fc * Ag / 1_000.0                  # t
    # Se compara el cortante sísmico con el cortante de cada extremo; si en
    # cualquiera de ellos el sismo aporta ≥ 50 %, se aplica Vc = 0 en toda la
    # zona de confinamiento (criterio conservador).
    relaciones = [Ve / v for v in (Vu_i, Vu_j) if v > 1e-9]
    relacion_sismo = max(relaciones) if relaciones else 0.0
    aplica_vc_cero = (
        config.usar_vc_cero_sismo
        and relacion_sismo >= 0.5 - 1e-9
        and fuerzas.P_compresion_max_t < limite_axial
    )
    Vc_conf = 0.0 if aplica_vc_cero else Vc

    # ------------------------------------------------------------------
    # Estribos
    # ------------------------------------------------------------------
    selecciones = [x.seleccion for x in flexion if x.seleccion is not None]
    db_long_max = max((s.diametro_max for s in selecciones), default=1.905)
    db_long_min = min((s.diametro_min for s in selecciones if s.cantidad > 0), default=1.27)
    estribo, ramas = seleccionar_estribo(config.estribo, db_long_max, b, r)
    Av = ramas * estribo.area_cm2

    db_est = estribo.diametro_cm
    s_max_conf = e060.s_maximo_confinamiento(d_cortante, db_long_min, db_est)
    s_max_central = e060.s_maximo_general(d_cortante)
    av_min_s = e060.av_minimo_por_s(mat.fc, b, mat.fyt)
    s_av_min = Av / av_min_s if av_min_s > 0 else inf
    s_lim_conf = min(s_max_conf, s_av_min)
    s_lim_central = min(s_max_central, s_av_min)

    Vs_req_i, s_req_i = _s_requerido(Vu_i, Vc_conf, e060.PHI_CORTANTE, Av, mat.fyt, d_cortante)
    Vs_req_j, s_req_j = _s_requerido(Vu_j, Vc_conf, e060.PHI_CORTANTE, Av, mat.fyt, d_cortante)
    Vs_req_c, s_req_c = _s_requerido(Vu_c, Vc, e060.PHI_CORTANTE, Av, mat.fyt, d_cortante)

    # Se adopta un mínimo constructivo de 5 cm.  Si la demanda exige menos,
    # se coloca 5 cm y la verificación de resistencia fallará, obligando a
    # revisar la sección o el estribo (no se oculta el problema).
    s_conf_i = max(5.0, _redondear_abajo(min(s_req_i, s_lim_conf)))
    s_conf_j = max(5.0, _redondear_abajo(min(s_req_j, s_lim_conf)))
    s_central = max(5.0, _redondear_abajo(min(s_req_c, s_lim_central)))

    if s_req_i < 5.0 or s_req_j < 5.0:
        advertencias.append(
            "El cortante exige un espaciamiento menor a 5 cm en la zona de "
            "confinamiento. Aumente la sección o la resistencia del concreto."
        )
    if s_req_c < 5.0:
        advertencias.append(
            "El cortante exige un espaciamiento menor a 5 cm en la zona central."
        )

    L_conf = min(e060.longitud_confinamiento(h) / 100.0, ln / 2.0)
    dist_i, dist_j, dist_c, total = _distribucion(
        ln, L_conf, s_conf_i, s_conf_j, s_central
    )
    peso_kg = peso_estribos_kg(total, b, h, r, db_est, estribo)

    # ------------------------------------------------------------------
    # Verificaciones
    # ------------------------------------------------------------------
    phi = e060.PHI_CORTANTE
    vs_max = e060.vs_maximo(mat.fc, b, d_cortante) / 1_000.0
    Vs_prov_i = Av * mat.fyt * d_cortante / s_conf_i / 1_000.0
    Vs_prov_j = Av * mat.fyt * d_cortante / s_conf_j / 1_000.0
    Vs_prov_c = Av * mat.fyt * d_cortante / s_central / 1_000.0
    phiVn_i = phi * (Vc_conf + Vs_prov_i)
    phiVn_j = phi * (Vc_conf + Vs_prov_j)
    phiVn_c = phi * (Vc + Vs_prov_c)

    vs: list[Verificacion] = []
    vs.append(Verificacion(
        "Cortante resistente en apoyo izquierdo",
        f"φVn = {phiVn_i:.3f} t",
        f"Vu = {Vu_i:.3f} t",
        phiVn_i + 1e-6 >= Vu_i,
        "E.060 11.5.7.2 / 21.5.4.1",
    ))
    vs.append(Verificacion(
        "Cortante resistente en apoyo derecho",
        f"φVn = {phiVn_j:.3f} t",
        f"Vu = {Vu_j:.3f} t",
        phiVn_j + 1e-6 >= Vu_j,
        "E.060 11.5.7.2 / 21.5.4.1",
    ))
    vs.append(Verificacion(
        "Cortante resistente en el centro",
        f"φVn = {phiVn_c:.3f} t",
        f"Vu = {Vu_c:.3f} t",
        phiVn_c + 1e-6 >= Vu_c,
        "E.060 11.5.7.2 / 21.5.4.1",
    ))
    Vs_req_max_t = max(Vs_req_i, Vs_req_j, Vs_req_c) / 1_000.0
    vs.append(Verificacion(
        "Máximo cortante del refuerzo",
        f"Vs,req = {Vs_req_max_t:.3f} t",
        f"Vs,max = {vs_max:.3f} t",
        Vs_req_max_t <= vs_max + 1e-6,
        "E.060 11.5.6.9",
        "El límite se aplica al cortante usado en el diseño (Vs,req), no a la "
        "capacidad nominal de un estribado más cerrado que el requerido.",
    ))
    vs.append(Verificacion(
        "Espaciamiento en confinamiento",
        f"s = {min(s_conf_i, s_conf_j):.2f} cm",
        f"s,max = {s_max_conf:.2f} cm",
        min(s_conf_i, s_conf_j) <= s_max_conf + 1e-6,
        "E.060 21.5.3.4",
    ))
    vs.append(Verificacion(
        "Espaciamiento central",
        f"s = {s_central:.2f} cm",
        f"s,max = {s_max_central:.2f} cm",
        s_central <= s_max_central + 1e-6,
        "E.060 21.5.3.5 / 11.5.5.1",
    ))
    vs.append(Verificacion(
        "Cuantía mínima de estribos (confinamiento)",
        f"Av/s = {Av / min(s_conf_i, s_conf_j):.4f} cm²/cm",
        f"Av,min/s = {av_min_s:.4f} cm²/cm",
        Av / min(s_conf_i, s_conf_j) + 1e-9 >= av_min_s,
        "E.060 11.5.6.3",
    ))
    vs.append(Verificacion(
        "Cuantía mínima de estribos (tramo central)",
        f"Av/s = {Av / s_central:.4f} cm²/cm",
        f"Av,min/s = {av_min_s:.4f} cm²/cm",
        Av / s_central + 1e-9 >= av_min_s,
        "E.060 11.5.6.3",
    ))
    vs.append(Verificacion(
        "Separación entre ramas",
        f"{b - 2 * (r + db_est):.1f}/({ramas} − 1) = {(b - 2 * (r + db_est)) / max(ramas - 1, 1):.2f} cm",
        "≤ 30 cm",
        (b - 2 * (r + db_est)) / max(ramas - 1, 1) <= 30.0 + 1e-6,
        "E.060 21.5.3.6",
    ))
    vs.append(Verificacion(
        "Primer estribo",
        "0.05 m desde la cara del apoyo",
        "≤ 0.05 m",
        True,
        "E.060 21.5.3.3",
    ))
    vs.append(Verificacion(
        "Diámetro mínimo del estribo",
        f"Φ {estribo.nombre}",
        "≥ " + ('1/2"' if db_long_max > 2.54 else '3/8"'),
        estribo.diametro_cm + 1e-9 >= e060.diametro_minimo_estribo(db_long_max),
        "E.060 21.5.3.2",
    ))
    if aplica_vc_cero:
        vs.append(Verificacion(
            "Vc = 0 en zona de confinamiento",
            f"Ve/Vu = {relacion_sismo:.2f}; P = {fuerzas.P_compresion_max_t:.2f} t",
            f"Ve/Vu ≥ 0.50; P < 0.05f'cAg = {limite_axial:.2f} t",
            True,
            "E.060 21.5.4.2",
        ))

    if Vu_diseno > phi * (Vc_conf + vs_max) + 1e-6:
        advertencias.append(
            "La sección no puede resistir el cortante ni con el Vs máximo "
            "(E.060 11.5.6.9). Aumente b, h o f'c."
        )

    # ------------------------------------------------------------------
    # Fórmulas con valores
    # ------------------------------------------------------------------
    formulas = [
        Formula(
            "Resistencia probable a flexión en los extremos",
            "Mpr = 1.25·Mn (con el acero realmente colocado)",
            (
                f"Mpr−,izq = 1.25·{Mpr_hog_izq/1.25:.3f} = {Mpr_hog_izq:.3f}; "
                f"Mpr+,izq = 1.25·{Mpr_sag_izq/1.25:.3f} = {Mpr_sag_izq:.3f}; "
                f"Mpr−,der = 1.25·{Mpr_hog_der/1.25:.3f} = {Mpr_hog_der:.3f}; "
                f"Mpr+,der = 1.25·{Mpr_sag_der/1.25:.3f} = {Mpr_sag_der:.3f} t·m"
            ),
            (
                "ΣMpr gobierna = "
                f"{max(Mpr_hog_izq + Mpr_sag_der, Mpr_sag_izq + Mpr_hog_der):.3f} t·m"
            ),
            "E.060 21.5.4.1",
        ),
        Formula(
            "Cortante por capacidad",
            "Ve = (Mpr,i + Mpr,j)/ln",
            (
                f"Ve = máx[({Mpr_hog_izq:.3f}+{Mpr_sag_der:.3f})/{ln:.2f}; "
                f"({Mpr_sag_izq:.3f}+{Mpr_hog_der:.3f})/{ln:.2f}]"
            ),
            f"Ve = {Ve:.3f} t",
            "E.060 21.5.4.1",
        ),
        Formula(
            "Cortante de diseño",
            "Vu = máx(Ve + Vg; V_ETABS)",
            (
                f"Vu,izq = máx({Ve + Vg_i:.3f}; {Vu_env_i:.3f}) = {Vu_i:.3f} t; "
                f"Vu,der = máx({Ve + Vg_j:.3f}; {Vu_env_j:.3f}) = {Vu_j:.3f} t; "
                f"Vu,centro = máx({Ve + Vg_c:.3f}; {Vu_env_c:.3f}) = {Vu_c:.3f} t"
            ),
            f"Vu,gobierna = {Vu_diseno:.3f} t",
            "E.060 21.5.4.1",
        ),
        Formula(
            "Resistencia del concreto",
            "Vc = 0.53·√(f'c)·b·d",
            f"Vc = 0.53·√{mat.fc:.0f}·{b:.1f}·{d_cortante:.2f}/1000",
            f"Vc = {Vc:.3f} t" + (" (Vc = 0 en zona confinada, 21.5.4.2)" if aplica_vc_cero else ""),
            "E.060 11.3.1.1",
        ),
        Formula(
            "Cortante del refuerzo requerido",
            "Vs,req = Vu/φ − Vc",
            (
                f"Vs,req,izq = {Vu_i:.3f}/0.85 − {Vc_conf:.3f} = {Vs_req_i/1000:.3f} t; "
                f"Vs,req,der = {Vs_req_j/1000:.3f} t"
            ),
            f"Vs,req = {max(Vs_req_i, Vs_req_j)/1000:.3f} t",
            "E.060 11.5.7.2",
        ),
        Formula(
            "Espaciamiento requerido",
            "s = Av·fy·d/Vs",
            (
                f"s = {Av:.2f}·{mat.fyt:.0f}·{d_cortante:.2f}/"
                f"{max(Vs_req_i, 1e-9):.1f}"
            ),
            f"s,req = {min(s_req_i, s_req_j):.2f} cm",
            "E.060 11.5.7.2",
        ),
        Formula(
            "Límites de espaciamiento",
            "sconf ≤ mín(d/4; 8db,long; 24db,est; 30 cm); scentral ≤ d/2",
            (
                f"sconf ≤ mín({d_cortante/4:.2f}; {8*db_long_min:.2f}; "
                f"{24*db_est:.2f}; 30) = {s_max_conf:.2f} cm; "
                f"scentral ≤ {s_max_central:.2f} cm"
            ),
            f"sconf = {s_conf_i:.2f}/{s_conf_j:.2f} cm; scentral = {s_central:.2f} cm",
            "E.060 21.5.3.4 / 21.5.3.5",
        ),
        Formula(
            "Cuantía mínima de estribos",
            "Av,min/s = máx(0.20√(f'c)·b/fy; 3.5·b/fy)",
            (
                f"Av,min/s = máx(0.20·√{mat.fc:.0f}·{b:.1f}/{mat.fyt:.0f}; "
                f"3.5·{b:.1f}/{mat.fyt:.0f}) = {av_min_s:.4f} cm²/cm"
            ),
            f"Av/s provisto = {Av/min(s_conf_i, s_conf_j):.4f} cm²/cm",
            "E.060 11.5.6.3",
        ),
    ]

    return ResultadoCortante(
        d_cm=d_cortante,
        ln_m=ln,
        Vu_envolvente_t=fuerzas.V_max_t,
        Mpr_i_tm=max(Mpr_hog_izq, Mpr_sag_izq),
        Mpr_j_tm=max(Mpr_hog_der, Mpr_sag_der),
        Ve_t=Ve,
        Vg_i_t=Vg_i,
        Vg_j_t=Vg_j,
        Vu_i_t=Vu_i,
        Vu_j_t=Vu_j,
        Vu_diseno_t=Vu_diseno,
        Vc_t=Vc,
        Vc_conf_t=Vc_conf,
        phi=phi,
        Vs_req_i_t=Vs_req_i / 1_000.0,
        Vs_req_j_t=Vs_req_j / 1_000.0,
        s_req_i_cm=s_req_i,
        s_req_j_cm=s_req_j,
        s_conf_i_cm=s_conf_i,
        s_conf_j_cm=s_conf_j,
        s_central_cm=s_central,
        s_max_conf_cm=s_max_conf,
        s_max_central_cm=s_max_central,
        s_av_min_cm=s_av_min,
        Av_cm2=Av,
        ramas=ramas,
        estribo=estribo,
        distribucion_i=dist_i,
        distribucion_j=dist_j,
        distribucion_central=dist_c,
        total_estribos=total,
        peso_estribos_kg=peso_kg,
        L_conf_m=L_conf,
        verificaciones=vs,
        formulas=formulas,
        advertencias=advertencias,
    )
