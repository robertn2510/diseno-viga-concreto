"""
Diseño a flexión de vigas rectangulares según la E.060.

Flujo
-----
1. Se calculan los límites de acero (mínimo 10.5.1, máximo 21.5.2.2 y límite
   de sección controlada por tracción 9.3.2.1).
2. Si Mu ≤ φMn,máx se diseña con armadura simple resolviendo la ecuación
   cuadrática de flexión.
3. Si Mu > φMn,máx se diseña con armadura doble: se fija c = 0.375d para
   garantizar εt = 0.005 (φ = 0.90), se calcula el acero en compresión por
   equilibrio y se verifica la fluencia del acero superior.
4. Se seleccionan barras comerciales, se recalcula el peralte efectivo real y
   se verifica la resistencia con φ obtenido de εt (no se supone φ = 0.90 si
   la sección deja de ser controlada por tracción).
"""

from __future__ import annotations

from math import isfinite

from ..config import ConfiguracionDiseno
from ..modelos import (
    Formula,
    GeometriaViga,
    Materiales,
    ResultadoFlexion,
    SeleccionVarillas,
    Verificacion,
)
from ..normativa import e060
from .varillas import (
    diametros_disponibles,
    etiqueta_varillas,
    opciones_seleccion,
)


def _crear_formulas_base(
    Mu: float,
    b: float,
    h: float,
    d: float,
    mat: Materiales,
    lim: e060.LimitesAcero,
    As_min: float,
    lado: str,
) -> list[Formula]:
    fc, fy = mat.fc, mat.fy
    b1 = mat.beta1
    if fc <= 280:
        expr_b1 = "β1 = 0.85"
        sust_b1 = f"f'c = {fc:.0f} kgf/cm² ≤ 280 → β1 = 0.85"
    else:
        expr_b1 = "β1 = 0.85 − 0.05·(f'c − 280)/70 ≥ 0.65"
        sust_b1 = (
            f"β1 = 0.85 − 0.05·({fc:.0f} − 280)/70 = {b1:.4f}"
        )

    formulas = [
        Formula(
            "Factor β1 del bloque rectangular",
            expr_b1,
            sust_b1,
            f"β1 = {b1:.4f}",
            "E.060 10.2.7.3",
        ),
        Formula(
            "Cuantía balanceada",
            "ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]",
            (
                f"ρb = 0.85·{b1:.4f}·({fc:.0f}/{fy:.0f})·"
                f"[0.003/(0.003 + {fy:.0f}/{mat.es:.0f})]"
            ),
            f"ρb = {lim.rho_b:.5f}",
            "E.060 10.3.2",
        ),
        Formula(
            "Acero mínimo a flexión",
            "As,min = 0.7·√(f'c)/fy · b·d",
            (
                f"As,min = 0.7·√{fc:.0f}/{fy:.0f} · {b:.1f} · {d:.2f} = "
                f"{As_min:.3f} cm²"
            ),
            f"As,min = {As_min:.3f} cm²",
            "E.060 10.5.1",
        ),
        Formula(
            "Acero máximo y momento máximo con armadura simple",
            "As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)",
            (
                f"As,max = mín({lim.As_rho_b_cm2:.3f}; "
                f"{lim.As_tension_controlada_cm2:.3f}; "
                f"{lim.As_rho_abs_cm2:.3f}) = {lim.As_max_cm2:.3f} cm² "
                f"(gobierna: {lim.criterio})"
            ),
            (
                f"a_max = {lim.a_max_cm:.3f} cm; "
                f"Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = "
                f"{lim.Mu_max_tm:.3f} t·m"
            ),
            "E.060 21.5.2.2 / 9.3.2.1",
        ),
    ]
    # El peralte efectivo se mide desde la fibra comprimida hasta el centroide
    # de la armadura traccionada colocada (E.060 10.2.2).  Como y_s está
    # referido a la cara traccionada, d = h − y_s en ambas direcciones.
    y_s = h - d
    formulas.append(
        Formula(
            "Peralte efectivo",
            "d = h − y_s",
            f"d = {h:.1f} − {y_s:.2f} = {d:.2f} cm",
            (
                f"d = {d:.2f} cm (y_s = {y_s:.2f} cm: centroide de la armadura "
                f"traccionada medido desde la cara {lado} del elemento)"
            ),
            "E.060 10.2.2",
        )
    )
    return formulas


def _verificaciones_finales(
    res: ResultadoFlexion,
    lim: e060.LimitesAcero,
    mat: Materiales,
    seleccion: SeleccionVarillas,
    b: float,
    h: float,
) -> list[Verificacion]:
    As = seleccion.area_cm2
    d = h - seleccion.y_cm
    rho = As / (b * d) if b > 0 and d > 0 else 0.0
    vs: list[Verificacion] = []

    vs.append(Verificacion(
        "Acero mínimo",
        f"As = {As:.3f} cm²",
        f"As,min = {res.As_min_cm2:.3f} cm²",
        As + 1e-6 >= res.As_min_cm2,
        "E.060 10.5.1",
    ))
    vs.append(Verificacion(
        "Cuantía máxima sísmica",
        f"ρ = {rho:.5f}",
        "ρ ≤ 0.025",
        rho <= e060.RHO_MAX_SISMICA + 1e-6,
        "E.060 21.5.2.2",
    ))

    if not res.doble:
        vs.append(Verificacion(
            "Límite de armadura simple (ductilidad)",
            f"As = {As:.3f} cm²",
            f"As,max = {lim.As_max_cm2:.3f} cm²",
            As <= lim.As_max_cm2 * 1.02,
            "E.060 10.3.5 / 9.3.2.1",
            "El límite asegura εt ≥ 0.005 y φ = 0.90." if As <= lim.As_max_cm2 * 1.02
            else "Se excede el límite; se verifica la ductilidad con εt y φ real.",
        ))
    else:
        vs.append(Verificacion(
            "Armadura de compresión",
            f"As' = {res.As_prima_prov_cm2:.3f} cm²",
            "As' > 0 y fluye o se evalúa f's",
            res.seleccion_compresion is not None and res.As_prima_prov_cm2 > 0,
            "E.060 10.3.4 / 21.5.2",
            f"f's = {res.fs_prima:.1f} kgf/cm²",
        ))

    vs.append(Verificacion(
        "Control de ductilidad",
        f"εt = {res.eps_t:.5f}",
        "εt ≥ 0.004",
        res.eps_t + 1e-9 >= e060.DEF_MIN_DUCTIL,
        "E.060 10.3.5",
    ))
    phi_esperado = e060.phi_flexion(res.eps_t)
    vs.append(Verificacion(
        "Factor de reducción φ",
        f"φ = {res.phi:.3f} (εt = {res.eps_t:.5f})",
        "φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90",
        abs(res.phi - phi_esperado) <= 0.01,
        "E.060 9.3.2.2",
        "Sección controlada por tracción (φ = 0.90)." if res.phi >= e060.PHI_FLEXION - 1e-9
        else "Sección en transición: φ se redujo según εt; la resistencia se verifica con φMn ≥ Mu.",
    ))
    vs.append(Verificacion(
        "Resistencia a flexión",
        f"φMn = {res.phiMn_tm:.3f} t·m",
        f"Mu = {res.Mu_tm:.3f} t·m",
        res.phiMn_tm + 1e-6 >= res.Mu_tm,
        "E.060 9.3.2.1",
    ))
    vs.append(Verificacion(
        "Separación libre entre barras",
        f"s = {seleccion.separacion_libre_cm:.2f} cm",
        f"s ≥ máx(Ø; 2.5 cm) = {max(seleccion.diametro_max, 2.5):.2f} cm",
        seleccion.separacion_libre_cm + 1e-6 >= max(seleccion.diametro_max, 2.5),
        "E.060 7.6.1",
    ))
    vs.append(Verificacion(
        "Número mínimo de barras",
        f"{seleccion.cantidad} barras",
        "≥ 2 barras",
        seleccion.cantidad >= 2,
        "E.060 21.5.2.1",
    ))
    vs.append(Verificacion(
        "Colocación en la sección",
        f"y = {seleccion.y_cm:.2f} cm",
        f"y ≤ h/2 = {h/2:.2f} cm",
        seleccion.y_cm <= h / 2.0 + 1e-6,
        "E.060 7.6 / 7.7",
        seleccion.mensaje,
    ))
    return vs


def _resguardo_maximo(
    b: float,
    h: float,
    r: float,
    dst: float,
    varillas,
    config: ConfiguracionDiseno,
    fc: float,
    fy: float,
    es: float,
    Mu_tm: float,
) -> tuple[SeleccionVarillas | None, SeleccionVarillas | None, float]:
    """
    Busca la distribución comercial que maximiza φMn cuando la sección no
    alcanza la demanda.

    Se evalúan las combinaciones de armadura de tracción y de compresión y se
    elige la de mayor resistencia nominal.  El resultado se informa como NO
    CUMPLE; el objetivo es que la memoria muestre la mayor capacidad posible
    en lugar de un armado mínimo que oculte la insuficiencia.
    """
    opciones = opciones_seleccion(
        0.0, b, h, r, dst,
        varillas=varillas, max_capas=config.max_capas,
        n_max=config.n_max_barras,
    )
    if not opciones:
        return None, None, 0.0

    # La armadura de tracción no debe superar ρ = 0.025 (E.060 21.5.2.2).
    # Se usa un peralte efectivo estimado (una capa) para acotar el área.
    d_est = max(h - r - dst - 1.27, 1.0)
    limite_area = e060.RHO_MAX_SISMICA * b * d_est
    traccion = [s for s in opciones if s.area_cm2 <= limite_area]
    if not traccion:
        traccion = [min(opciones, key=lambda s: s.area_cm2)]
    compresion = [None] + opciones

    mejor: tuple[SeleccionVarillas | None, SeleccionVarillas | None, float] = (
        None, None, -1.0,
    )
    for sel_t in traccion:
        d_t = h - sel_t.y_cm
        if d_t <= 1.0:
            continue
        for sel_c in compresion:
            if sel_c is not None:
                if sel_c.area_cm2 >= sel_t.area_cm2:
                    continue
                d_c = sel_c.y_cm
            else:
                d_c = r + dst + 1.905 / 2.0
            if d_c >= d_t - 1.0:
                continue
            cap = e060.momento_nominal(
                sel_t.area_cm2,
                sel_c.area_cm2 if sel_c else 0.0,
                b, d_t, d_c, fc, fy, es,
            )
            if cap.phiMn_tm > mejor[2]:
                mejor = (sel_t, sel_c, cap.phiMn_tm)
    return mejor


def disenar_flexion(
    Mu_tm: float,
    geom: GeometriaViga,
    mat: Materiales,
    lado: str,
    config: ConfiguracionDiseno,
    ubicacion: str,
    d_inicial: float | None = None,
) -> ResultadoFlexion:
    """
    Diseña una sección rectangular a flexión simple o doble.

    Parámetros
    ----------
    Mu_tm:
        Momento último en t·m.  Su signo se ignora; ``lado`` indica la cara
        traccionada ("inferior" para momento positivo, "superior" para
        momento negativo).
    geom, mat:
        Geometría y materiales.
    lado:
        "inferior" o "superior".
    config:
        Configuración de diseño.
    ubicacion:
        Texto descriptivo (p. ej., "Apoyo izquierdo (cara)").
    """
    if lado not in {"inferior", "superior"}:
        raise ValueError("lado debe ser 'inferior' o 'superior'.")

    b, h, r = geom.b, geom.h, geom.r
    dst = geom.diametro_estribo
    fc, fy, es = mat.fc, mat.fy, mat.es
    Mu = max(0.0, abs(Mu_tm))
    d = d_inicial or geom.d_estimado
    d = min(d, h - r - dst - 0.5)

    varillas = diametros_disponibles(
        config.diametro_long_min_cm, config.diametro_long_max_cm
    )
    advertencias: list[str] = []
    simple = True
    sel: SeleccionVarillas | None = None
    sel_c: SeleccionVarillas | None = None
    As_floor = 0.0
    As_c_floor = 0.0
    As_t_floor = 0.0
    As_calc = 0.0
    As_t_req = 0.0
    As_c_req = 0.0
    cap = None
    lim = e060.limites_acero(fc, fy, b, d, config.fraccion_rho_b)
    As_min = e060.as_minimo(fc, fy, b, d)

    # Si el momento supera la capacidad simple, se entra directamente al
    # diseño doble.
    if Mu > lim.Mu_max_tm + 1e-9:
        simple = False

    for intento in range(14):
        lim = e060.limites_acero(fc, fy, b, d, config.fraccion_rho_b)
        As_min = e060.as_minimo(fc, fy, b, d)

        if simple:
            As_calc, disc = e060.as_requerido_simple(Mu, fc, fy, b, d)
            if disc < 0 or As_calc > lim.As_max_cm2:
                simple = False
                continue
            As_t_req = max(As_calc, As_min, As_floor)
            if As_t_req > lim.As_max_cm2:
                simple = False
                continue
            opciones = [
                s for s in opciones_seleccion(
                    As_t_req, b, h, r, dst, varillas=varillas,
                    max_capas=config.max_capas, n_max=config.n_max_barras,
                )
                if s.area_cm2 <= lim.As_max_cm2 + 1e-6
            ]
            sel = opciones[0] if opciones else None
            if sel is None:
                simple = False
                continue
            sel_c = None
            As_c_req = 0.0
        else:
            # ------------------------------------------------------------------
            # Armadura doble: se fija c = 0.375d para εt = 0.005 y φ = 0.90.
            # E.060 9.3.2.1 y 10.3.4.
            # ------------------------------------------------------------------
            c = e060.C_TENSION_CONTROLADA * d
            a = mat.beta1 * c
            dc_est = r + dst + 1.905 / 2.0
            fs_c = min(fy, max(0.0, es * e060.ECU * (c - dc_est) / c))
            if fs_c <= 0.05 * fy:
                advertencias.append(
                    "El acero de compresión no fluye con c = 0.375d; "
                    "se requiere revisar el peralte o aumentar la sección."
                )
            Cc = 0.85 * fc * b * a
            M1 = Cc * (d - a / 2.0)                        # kgf·cm
            M2 = Mu * 100_000.0 / e060.PHI_FLEXION - M1    # kgf·cm
            if M2 <= 0:
                simple = True
                continue
            As_c_calc = M2 / max(fs_c * (d - dc_est), 1e-9)
            As_t_calc = (Cc + As_c_calc * fs_c) / fy
            As_c_req = max(As_c_calc, As_c_floor)
            As_t_req = max(As_t_calc, As_min, As_t_floor)

            if As_t_req > e060.RHO_MAX_SISMICA * b * d:
                advertencias.append(
                    "El acero de tracción requerido supera ρ = 0.025 "
                    "(E.060 21.5.2.2). Aumente la sección."
                )

            opciones_t = opciones_seleccion(
                As_t_req, b, h, r, dst, varillas=varillas,
                max_capas=config.max_capas, n_max=config.n_max_barras,
            )
            if not opciones_t:
                advertencias.append(
                    "No existe distribución de barras que quepa en la sección."
                )
                sel = None
                break
            sel = opciones_t[0]

            area_c_min = 2.0 * varillas[0].area_cm2
            opciones_c = opciones_seleccion(
                max(As_c_req, area_c_min), b, h, r, dst, varillas=varillas,
                max_capas=config.max_capas, n_max=config.n_max_barras,
            )
            sel_c = opciones_c[0] if opciones_c else None
            if sel_c is None:
                advertencias.append("No se pudo colocar el acero de compresión.")
                break

        d_new = h - sel.y_cm
        dc = sel_c.y_cm if sel_c is not None else (r + dst + 1.905 / 2.0)
        As_c = sel_c.area_cm2 if sel_c is not None else 0.0
        cap = e060.momento_nominal(
            sel.area_cm2, As_c, b, d_new, dc, fc, fy, es
        )
        As_min_new = e060.as_minimo(fc, fy, b, d_new)
        cumple_capacidad = cap.phiMn_tm + 1e-6 >= Mu
        cumple_min = sel.area_cm2 + 1e-9 >= As_min_new
        cumple_limite = simple is False or sel.area_cm2 <= lim.As_max_cm2 * 1.02

        if cumple_capacidad and cumple_min and cumple_limite:
            d = d_new
            break

        # Si el cambio de peralte efectivo es significativo, se repite el
        # cálculo con la geometría real antes de aumentar el acero.
        if abs(d_new - d) > 0.20:
            d = d_new
            continue

        if simple:
            if sel.area_cm2 > lim.As_max_cm2 * 1.02:
                simple = False
            else:
                As_floor = max(As_floor, sel.area_cm2 * 1.04)
        else:
            As_c_floor = max(As_c_floor, (As_c_req if As_c_req > 0 else As_c) * 1.06)
            As_t_floor = max(As_t_floor, sel.area_cm2 * 1.04)
        d = d_new
    else:
        advertencias.append(
            "El proceso iterativo de flexión no convergió en 14 pasos; "
            "revise los resultados con especial cuidado."
        )

    if sel is None:
        # Solución de resguardo: se coloca la distribución comercial que
        # maximiza φMn (evaluando también el acero de compresión).  Así la
        # memoria muestra la mayor capacidad alcanzable y la verificación
        # queda marcada como NO CUMPLE.
        from .varillas import construir_seleccion

        sel_r, sel_c_r, phiMn_r = _resguardo_maximo(
            b, h, r, dst, varillas, config, fc, fy, es, Mu,
        )
        if sel_r is not None:
            sel, sel_c = sel_r, sel_c_r
            simple = False
        else:
            sel = construir_seleccion(varillas[0], 2, b, h, r, dst)
            sel_c = None
            simple = True
        advertencias.append(
            "La sección no resiste el momento con una distribución comercial; "
            f"se coloca la armadura de mayor capacidad (φMn ≈ {phiMn_r:.2f} t·m) "
            "y la verificación se marca como NO CUMPLE. Aumente b, h o f'c."
        )

    d_final = h - sel.y_cm
    lim = e060.limites_acero(fc, fy, b, d_final, config.fraccion_rho_b)
    As_min = e060.as_minimo(fc, fy, b, d_final)
    dc_final = sel_c.y_cm if sel_c is not None else (r + dst + 1.905 / 2.0)
    cap = e060.momento_nominal(
        sel.area_cm2,
        sel_c.area_cm2 if sel_c is not None else 0.0,
        b, d_final, dc_final, fc, fy, es,
    )

    # Si la distribución final no alcanza la demanda (sección insuficiente),
    # se sustituye por la de mayor φMn para no reportar una capacidad menor
    # que la realmente alcanzable.
    if cap.phiMn_tm + 1e-6 < Mu:
        sel_r, sel_c_r, phiMn_r = _resguardo_maximo(
            b, h, r, dst, varillas, config, fc, fy, es, Mu,
        )
        if sel_r is not None and phiMn_r > cap.phiMn_tm + 1e-9:
            sel, sel_c = sel_r, sel_c_r
            simple = sel_c is None
            d_final = h - sel.y_cm
            lim = e060.limites_acero(fc, fy, b, d_final, config.fraccion_rho_b)
            As_min = e060.as_minimo(fc, fy, b, d_final)
            dc_final = (
                sel_c.y_cm if sel_c is not None
                else (r + dst + 1.905 / 2.0)
            )
            cap = e060.momento_nominal(
                sel.area_cm2,
                sel_c.area_cm2 if sel_c is not None else 0.0,
                b, d_final, dc_final, fc, fy, es,
            )
            advertencias.append(
                "La armadura se ajustó a la de mayor capacidad posible "
                f"(φMn ≈ {cap.phiMn_tm:.2f} t·m) porque la sección no alcanza "
                "la demanda; la verificación queda como NO CUMPLE."
            )

    insuficiente = cap.phiMn_tm + 1e-6 < Mu
    if insuficiente:
        # No existe una solución comercial: se informa el acero colocado y la
        # verificación de resistencia marca el déficit.
        As_req = sel.area_cm2
        As_c_req = sel_c.area_cm2 if sel_c is not None else 0.0
        As_calc = sel.area_cm2
    elif simple:
        As_calc, _ = e060.as_requerido_simple(Mu, fc, fy, b, d_final)
        As_req = max(As_calc, As_min) if isfinite(As_calc) else sel.area_cm2
        As_c_req = 0.0
    else:
        As_req = max(As_t_req, As_min)
        As_c_req = max(As_c_req, 0.0)

    res = ResultadoFlexion(
        ubicacion=ubicacion,
        lado=lado,
        Mu_tm=Mu,
        b_cm=b,
        h_cm=h,
        d_cm=d_final,
        beta1=mat.beta1,
        rho_b=lim.rho_b,
        rho_max=lim.rho_max,
        As_min_cm2=As_min,
        As_max_cm2=lim.As_max_cm2,
        Mu_max_simple_tm=lim.Mu_max_tm,
        As_req_cm2=As_req,
        As_calculado_cm2=As_calc if simple else As_t_req,
        doble=not simple,
        As_prima_req_cm2=As_c_req,
        seleccion=sel,
        seleccion_compresion=sel_c if not simple else None,
        d_final_cm=d_final,
        a_cm=cap.a_cm,
        c_cm=cap.c_cm,
        eps_t=cap.eps_t,
        phi=cap.phi,
        fs_prima=cap.fs_prima_kgcm2,
        Mn_tm=cap.Mn_tm,
        phiMn_tm=cap.phiMn_tm,
        ratio_As=sel.area_cm2 / As_req if As_req > 0 else 0.0,
        criterio=lim.criterio,
        advertencias=advertencias,
    )

    # ------------------------------------------------------------------
    # Fórmulas con valores sustituidos
    # ------------------------------------------------------------------
    res.formulas = _crear_formulas_base(Mu, b, h, d_final, mat, lim, As_min, lado)

    if simple:
        K = Mu * 100_000.0 / e060.PHI_FLEXION
        C = fy * fy / (2.0 * 0.85 * fc * b)
        B = fy * d_final
        disc = B * B - 4.0 * C * K
        res.formulas.append(Formula(
            "Ecuación de flexión simple",
            "Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)",
            (
                f"{Mu:.3f}·10⁵ = 0.90·As·{fy:.0f}·"
                f"({d_final:.2f} − As·{fy:.0f}/(2·0.85·{fc:.0f}·{b:.1f}))"
            ),
            f"As = {As_calc:.3f} cm²  (discriminante = {disc:.3e})",
            "E.060 10.3.1",
        ))
        if As_req > As_calc + 1e-9:
            res.formulas.append(Formula(
                "Gobierna el acero mínimo",
                "As,req = máx(As,calculado; As,min)",
                f"As,req = máx({As_calc:.3f}; {As_min:.3f})",
                f"As,req = {As_req:.3f} cm²",
                "E.060 10.5.1",
            ))
    else:
        c = e060.C_TENSION_CONTROLADA * d_final
        a = mat.beta1 * c
        dc_est = r + dst + 1.905 / 2.0
        fs_c = min(fy, max(0.0, es * e060.ECU * (c - dc_est) / c))
        Cc = 0.85 * fc * b * a
        M1 = Cc * (d_final - a / 2.0)
        M2 = Mu * 100_000.0 / e060.PHI_FLEXION - M1
        res.formulas.extend([
            Formula(
                "Profundidad del eje neutro para φ = 0.90",
                "c = 0.375·d;  a = β1·c",
                f"c = 0.375·{d_final:.2f} = {c:.2f} cm; a = {mat.beta1:.3f}·{c:.2f} = {a:.2f} cm",
                f"c = {c:.2f} cm; a = {a:.2f} cm",
                "E.060 9.3.2.1 / 10.2.7",
            ),
            Formula(
                "Fuerza y momento del bloque de concreto",
                "Cc = 0.85·f'c·b·a;  M1 = Cc·(d − a/2)",
                f"Cc = 0.85·{fc:.0f}·{b:.1f}·{a:.2f} = {Cc:.1f} kgf; M1 = {Cc:.1f}·({d_final:.2f} − {a:.2f}/2)",
                f"M1 = {M1/100_000:.3f} t·m",
                "E.060 10.2.7",
            ),
            Formula(
                "Acero de compresión requerido",
                "As' = [Mu/φ − Cc·(d − a/2)] / [f's·(d − d')]",
                (
                    f"As' = [{Mu:.3f}·10⁵/0.90 − {M1:.0f}] / "
                    f"[{fs_c:.0f}·({d_final:.2f} − {dc_est:.2f})]"
                ),
                f"As' = {As_c_req:.3f} cm²; f's = {fs_c:.1f} kgf/cm²",
                "E.060 10.3.4",
            ),
            Formula(
                "Acero de tracción requerido",
                "As = (Cc + As'·f's)/fy",
                f"As = ({Cc:.1f} + {As_c_req:.3f}·{fs_c:.0f})/{fy:.0f}",
                f"As = {As_t_req:.3f} cm²",
                "E.060 10.3.1",
            ),
        ])

    res.formulas.extend([
        Formula(
            "Profundidad real del bloque y eje neutro",
            "a = As·fy/(0.85·f'c·b);  c = a/β1",
            f"a = {sel.area_cm2:.3f}·{fy:.0f}/(0.85·{fc:.0f}·{b:.1f}) = {cap.a_cm:.3f} cm; c = {cap.c_cm:.3f} cm",
            f"a = {cap.a_cm:.3f} cm; c = {cap.c_cm:.3f} cm",
            "E.060 10.2.7",
        ),
        Formula(
            "Deformación y factor φ",
            "εt = 0.003·(d − c)/c;  φ = f(εt)",
            f"εt = 0.003·({d_final:.2f} − {cap.c_cm:.3f})/{cap.c_cm:.3f} = {cap.eps_t:.5f}",
            f"φ = {cap.phi:.3f}",
            "E.060 9.3.2",
        ),
        Formula(
            "Resistencia nominal y de diseño",
            "Mn = As·fy·(d − a/2);  φMn = φ·Mn",
            f"Mn = {sel.area_cm2:.3f}·{fy:.0f}·({d_final:.2f} − {cap.a_cm:.3f}/2)/10⁵",
            f"Mn = {cap.Mn_tm:.3f} t·m; φMn = {cap.phiMn_tm:.3f} t·m",
            "E.060 10.3.1 / 9.3.2.1",
        ),
        Formula(
            "Selección comercial",
            "As,prov ≥ As,req",
            f"{etiqueta_varillas(sel)} → As,prov = {sel.area_cm2:.3f} cm² ≥ {As_req:.3f} cm²",
            f"{etiqueta_varillas(sel)}  (d = {d_final:.2f} cm)",
            "E.060 7.6 / 21.5.2",
        ),
    ])

    res.verificaciones = _verificaciones_finales(res, lim, mat, sel, b, h)

    # Advertencias adicionales de coherencia
    if res.phiMn_tm + 1e-6 < Mu:
        advertencias.append(
            f"φMn = {res.phiMn_tm:.3f} t·m < Mu = {Mu:.3f} t·m. "
            "Aumente la sección o el refuerzo."
        )
    if res.eps_t < e060.DEF_MIN_DUCTIL:
        advertencias.append(
            f"εt = {res.eps_t:.5f} < 0.004 (E.060 10.3.5). Sección poco dúctil."
        )
    if res.As_prov_cm2 > e060.RHO_MAX_SISMICA * b * d_final:
        advertencias.append(
            "La cuantía de tracción supera 0.025 (E.060 21.5.2.2)."
        )
    return res
