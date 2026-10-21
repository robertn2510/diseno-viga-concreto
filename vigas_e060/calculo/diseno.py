"""Orquestación del diseño completo de una viga."""

from __future__ import annotations

from ..config import ConfiguracionDiseno
from ..modelos import (
    FuerzasViga,
    ResultadoFlexion,
    ResultadoViga,
    Verificacion,
    VigaETABS,
)
from ..normativa import e060
from .cortante import disenar_cortante
from .flexion import disenar_flexion


def _ver(
    nombre: str,
    valor: str,
    limite: str,
    cumple: bool,
    ref: str,
    obs: str = "",
) -> Verificacion:
    return Verificacion(nombre, valor, limite, cumple, ref, obs)



def _reasignar_seccion(
    flexion: list[ResultadoFlexion],
    nuevo: ResultadoFlexion,
) -> None:
    """Sustituye la sección de igual ubicación y fibra."""
    for i, r in enumerate(flexion):
        if r.ubicacion == nuevo.ubicacion and r.lado == nuevo.lado:
            flexion[i] = nuevo
            return


def _ampliar_por_continuidad(
    flexion: list[ResultadoFlexion],
    geom,
    mat,
    config: ConfiguracionDiseno,
) -> list[str]:
    """
    Aumenta el acero donde la resistencia nominal no cumple los mínimos de
    continuidad del capítulo 21:

    * 21.5.2.3: en la cara del apoyo, Mn(+) ≥ Mn(−)/2.
    * 21.5.2.4: en toda la sección, Mn ≥ Mn,max/4.

    El proceso es iterativo porque al aumentar un Mn puede aumentar Mn,max y,
    con él, el objetivo de 21.5.2.4.  Se limita a cuatro pasadas.
    """
    notas: list[str] = []
    for _ in range(4):
        Mn_max = max((r.Mn_tm for r in flexion), default=0.0)
        objetivo = Mn_max / 4.0
        cambios = 0

        for r in list(flexion):
            req = objetivo
            if r.lado == "inferior" and r.ubicacion.startswith("Apoyo"):
                sup = next(
                    (x for x in flexion
                     if x.ubicacion == r.ubicacion and x.lado == "superior"),
                    None,
                )
                if sup is not None:
                    req = max(req, sup.Mn_tm / 2.0)

            if r.Mn_tm + 1e-6 >= req:
                continue

            mu_real = r.Mu_original_tm if r.motivo_ampliacion else r.Mu_tm
            mu_obj = max(req * e060.PHI_FLEXION * 1.03, mu_real)
            nuevo = disenar_flexion(
                mu_obj, geom, mat, r.lado, config, r.ubicacion
            )
            nuevo.Mu_original_tm = mu_real
            motivo = []
            if r.lado == "inferior" and r.ubicacion.startswith("Apoyo"):
                motivo.append("Mn+ ≥ Mn−/2 (E.060 21.5.2.3)")
            motivo.append("Mn ≥ Mn,max/4 (E.060 21.5.2.4)")
            nuevo.motivo_ampliacion = "; ".join(motivo)
            nuevo.advertencias.append(
                f"Se aumentó el acero para cumplir {' y '.join(motivo)}: "
                f"Mn pasó de {r.Mn_tm:.2f} a {nuevo.Mn_tm:.2f} t·m."
            )
            _reasignar_seccion(flexion, nuevo)
            cambios += 1

        if cambios == 0:
            break
    else:
        notas.append(
            "La ampliación por continuidad (E.060 21.5.2.3/21.5.2.4) no "
            "convergió en cuatro pasadas."
        )
    if any(r.motivo_ampliacion for r in flexion):
        notas.append(
            "Algunas secciones se diseñaron con un momento mayor que el de la "
            "envolvente para cumplir los mínimos de continuidad del capítulo 21."
        )
    return notas


def disenar_viga(
    viga: VigaETABS,
    fuerzas: FuerzasViga,
    config: ConfiguracionDiseno,
) -> ResultadoViga:
    """
    Diseña una viga en las secciones críticas y consolida el armado.

    Se diseñan:
    * apoyo izquierdo (cara): fibra superior e inferior;
    * centro: fibra inferior y superior;
    * apoyo derecho (cara): fibra superior e inferior;
    * estación de momento positivo máximo y estación de momento negativo
      máximo, si no coinciden con las anteriores.
    """
    geom, mat = viga.geometria, viga.materiales
    clave = fuerzas.estaciones_clave
    if "Cara-I" not in clave or "Cara-J" not in clave or "Centro" not in clave:
        raise ValueError("Faltan estaciones clave para el diseño.")
    ci, cj, cc = clave["Cara-I"], clave["Cara-J"], clave["Centro"]

    flexion: list[ResultadoFlexion] = [
        disenar_flexion(ci.M_neg_tm, geom, mat, "superior", config,
                        "Apoyo izquierdo (cara)"),
        disenar_flexion(ci.M_pos_tm, geom, mat, "inferior", config,
                        "Apoyo izquierdo (cara)"),
        disenar_flexion(cc.M_pos_tm, geom, mat, "inferior", config, "Centro"),
        disenar_flexion(cc.M_neg_tm, geom, mat, "superior", config, "Centro"),
        disenar_flexion(cj.M_neg_tm, geom, mat, "superior", config,
                        "Apoyo derecho (cara)"),
        disenar_flexion(cj.M_pos_tm, geom, mat, "inferior", config,
                        "Apoyo derecho (cara)"),
    ]

    # Secciones adicionales donde la envolvente global alcanza su máximo,
    # siempre que el máximo ocurra dentro de la luz libre.  Los valores en
    # I-End/J-End corresponden al eje de la columna y no son secciones de
    # diseño de la viga: en la cara del apoyo ya se diseñó con "Cara-I"/"Cara-J".
    x_i = max(viga.offset_i_m, 0.0) + 0.01
    x_j = geom.L - max(viga.offset_j_m, 0.0) - 0.01
    x_pos = fuerzas.estacion_M_pos_m
    x_neg = fuerzas.estacion_M_neg_m
    if x_i < x_pos < x_j and fuerzas.M_pos_max_tm > cc.M_pos_tm * 1.02 + 0.1:
        flexion.append(disenar_flexion(
            fuerzas.M_pos_max_tm, geom, mat, "inferior", config,
            f"M+ máximo (x = {x_pos:.2f} m)",
        ))
    if x_i < x_neg < x_j and fuerzas.M_neg_max_tm > max(ci.M_neg_tm, cj.M_neg_tm) * 1.02 + 0.1:
        flexion.append(disenar_flexion(
            fuerzas.M_neg_max_tm, geom, mat, "superior", config,
            f"M− máximo (x = {x_neg:.2f} m)",
        ))

    # Mínimos de continuidad del capítulo 21: se aumenta el acero antes de
    # dimensionar los estribos, porque Mpr depende del acero colocado.
    notas_continuidad = _ampliar_por_continuidad(flexion, geom, mat, config)

    cortante = disenar_cortante(viga, fuerzas, flexion, config)

    # ------------------------------------------------------------------
    # Verificaciones globales de la viga (Capítulo 21)
    # ------------------------------------------------------------------
    verificaciones: list[Verificacion] = []
    for nombre, valor, limite, cumple, ref in e060.chequeos_geometricos_viga(
        geom.b, geom.h, geom.ln
    ):
        verificaciones.append(_ver(nombre, valor, limite, cumple, ref))

    # 21.5.2.3: en cada cara del nudo, Mn(+) ≥ Mn(−)/2
    izq_sup = next((r for r in flexion if r.ubicacion.startswith("Apoyo izquierdo") and r.lado == "superior"), None)
    izq_inf = next((r for r in flexion if r.ubicacion.startswith("Apoyo izquierdo") and r.lado == "inferior"), None)
    der_sup = next((r for r in flexion if r.ubicacion.startswith("Apoyo derecho") and r.lado == "superior"), None)
    der_inf = next((r for r in flexion if r.ubicacion.startswith("Apoyo derecho") and r.lado == "inferior"), None)

    if izq_sup and izq_inf:
        limite = izq_sup.Mn_tm / 2.0
        verificaciones.append(_ver(
            "Relación de momentos en apoyo izquierdo",
            f"Mn+ = {izq_inf.Mn_tm:.2f} t·m",
            f"Mn+ ≥ Mn−/2 = {limite:.2f} t·m",
            izq_inf.Mn_tm + 1e-6 >= limite,
            "E.060 21.5.2.3",
        ))
    if der_sup and der_inf:
        limite = der_sup.Mn_tm / 2.0
        verificaciones.append(_ver(
            "Relación de momentos en apoyo derecho",
            f"Mn+ = {der_inf.Mn_tm:.2f} t·m",
            f"Mn+ ≥ Mn−/2 = {limite:.2f} t·m",
            der_inf.Mn_tm + 1e-6 >= limite,
            "E.060 21.5.2.3",
        ))

    # 21.5.2.4: en toda la viga Mn ≥ Mn,max/4
    Mn_max = max((r.Mn_tm for r in flexion), default=0.0)
    for r in flexion:
        if r.Mn_tm + 1e-6 < Mn_max / 4.0:
            verificaciones.append(_ver(
                f"Momento mínimo en {r.ubicacion} ({r.lado})",
                f"Mn = {r.Mn_tm:.2f} t·m",
                f"Mn ≥ Mn,max/4 = {Mn_max/4:.2f} t·m",
                False,
                "E.060 21.5.2.4",
            ))
            break
    else:
        verificaciones.append(_ver(
            "Momento mínimo a lo largo de la viga",
            f"Mn,mín = {min((r.Mn_tm for r in flexion), default=0):.2f} t·m",
            f"Mn ≥ Mn,max/4 = {Mn_max/4:.2f} t·m",
            True,
            "E.060 21.5.2.4",
        ))

    # Refuerzo continuo mínimo: 2 barras superior e inferior (21.5.2.1)
    n_sup = min((r.seleccion.cantidad for r in flexion
                 if r.lado == "superior" and r.seleccion), default=0)
    n_inf = min((r.seleccion.cantidad for r in flexion
                 if r.lado == "inferior" and r.seleccion), default=0)
    verificaciones.append(_ver(
        "Refuerzo continuo mínimo",
        f"superior: {n_sup} barras; inferior: {n_inf} barras",
        "≥ 2 barras en cada cara",
        n_sup >= 2 and n_inf >= 2,
        "E.060 21.5.2.1",
    ))

    advertencias = (
        list(viga.advertencias) + list(fuerzas.advertencias) + notas_continuidad
    )
    for r in flexion:
        advertencias.extend(r.advertencias)
    advertencias.extend(cortante.advertencias)
    # El mismo mensaje puede repetirse en las dos caras del apoyo; se informa
    # una sola vez conservando el orden.
    advertencias = list(dict.fromkeys(advertencias))

    return ResultadoViga(
        viga=viga,
        fuerzas=fuerzas,
        flexion=flexion,
        cortante=cortante,
        verificaciones=verificaciones,
        advertencias=advertencias,
    )


def resumen_armado(resultado: ResultadoViga) -> list[dict[str, str]]:
    """Resumen de armado por zona, para tablas y consola."""
    filas: list[dict[str, str]] = []

    def buscar(ubicacion: str, lado: str) -> ResultadoFlexion | None:
        return next(
            (r for r in resultado.flexion
             if r.ubicacion == ubicacion and r.lado == lado),
            None,
        )

    for ubicacion in ("Apoyo izquierdo (cara)", "Centro", "Apoyo derecho (cara)"):
        sup = buscar(ubicacion, "superior")
        inf = buscar(ubicacion, "inferior")
        filas.append({
            "Zona": ubicacion,
            "Superior": sup.seleccion.etiqueta if sup and sup.seleccion else "—",
            "Inferior": inf.seleccion.etiqueta if inf and inf.seleccion else "—",
            "Mu− (t·m)": f"{sup.Mu_tm:.2f}" if sup else "—",
            "Mu+ (t·m)": f"{inf.Mu_tm:.2f}" if inf else "—",
        })
    if resultado.cortante:
        c = resultado.cortante
        filas.append({
            "Zona": "Estribos (izq.)",
            "Superior": c.distribucion_i,
            "Inferior": "",
            "Mu− (t·m)": "",
            "Mu+ (t·m)": "",
        })
        filas.append({
            "Zona": "Estribos (centro / der.)",
            "Superior": c.distribucion_central,
            "Inferior": c.distribucion_j,
            "Mu− (t·m)": "",
            "Mu+ (t·m)": "",
        })
    return filas
