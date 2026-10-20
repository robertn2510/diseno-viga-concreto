"""
Modo demostración: datos sintéticos con la misma estructura que ETABS.

Permite ejecutar todo el flujo (diseño + memoria) en Linux, macOS o Windows
sin ETABS instalado, y sirve como caso de validación de la memoria.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .calculo.diseno import disenar_viga
from .config import ConfiguracionDiseno
from .etabs.combos import generar_combos_requeridas
from .etabs.extraccion import _envolvente, _interpolar
from .modelos import (
    FuerzaEstacion,
    FuerzasViga,
    GeometriaViga,
    Materiales,
    MetadatosProyecto,
    ResultadoViga,
    VerificacionCombo,
    VigaETABS,
)
from .reporte import generar_reporte


def _combo(
    L: float,
    M_i: float,
    M_j: float,
    M_c: float,
    V: float,
    P: float,
    nombre: str,
    n_estaciones: int = 9,
) -> list[FuerzaEstacion]:
    """Genera una curva de momentos parabólica compatible con las estaciones."""
    puntos: list[FuerzaEstacion] = []
    for k in range(n_estaciones):
        x = L * k / (n_estaciones - 1)
        t = x / L
        # Parábola que pasa por M_i, M_j y M_c
        M = M_i * (1 - t) + M_j * t + 4.0 * (M_c - (M_i + M_j) / 2.0) * t * (1 - t)
        # Cortante lineal de +V a -V (equilibrio aproximado para el demo)
        Vx = V * (1 - 2 * t)
        puntos.append(FuerzaEstacion(
            estacion_m=x, M3_tm=M, V2_t=Vx, P_t=P, T_tm=0.0, combo=nombre,
        ))
    return puntos


def _fuerzas_demo(
    viga: VigaETABS,
    casos: dict[str, tuple[float, float, float, float, float]],
    gravedad: str,
) -> FuerzasViga:
    L = viga.geometria.L
    por_combo: dict[str, list[FuerzaEstacion]] = {}
    for nombre, (Mi, Mj, Mc, V, P) in casos.items():
        por_combo[nombre] = _combo(L, Mi, Mj, Mc, V, P, nombre)

    estaciones = {
        "I-End": 0.0,
        "Centro": L / 2.0,
        "J-End": L,
        "Cara-I": max(viga.offset_i_m, 0.0),
        "Cara-J": min(L - viga.offset_j_m, L),
    }
    env = {}
    for nombre, x in estaciones.items():
        e = _envolvente(por_combo, x, nombre, True)
        if e:
            env[nombre] = e

    M_pos = (-1e30, 0.0, "")
    M_neg = (0.0, 0.0, "")
    Vmax = (0.0, 0.0, "")
    Tmax = (0.0, 0.0, "")
    Pcomp = 0.0
    for nombre, pts in por_combo.items():
        for p in pts:
            if p.M3_tm > M_pos[0]:
                M_pos = (p.M3_tm, p.estacion_m, nombre)
            if p.M3_tm < M_neg[0]:
                M_neg = (p.M3_tm, p.estacion_m, nombre)
            if abs(p.V2_t) > Vmax[0]:
                Vmax = (abs(p.V2_t), p.estacion_m, nombre)
            if abs(p.T_tm) > Tmax[0]:
                Tmax = (abs(p.T_tm), p.estacion_m, nombre)
            Pcomp = max(Pcomp, -p.P_t)

    gi = _interpolar(por_combo[gravedad], estaciones["Cara-I"])
    gj = _interpolar(por_combo[gravedad], estaciones["Cara-J"])
    gc = _interpolar(por_combo[gravedad], L / 2)

    return FuerzasViga(
        combos=list(por_combo),
        por_combo=por_combo,
        estaciones_clave=env,
        M_pos_max_tm=max(0.0, M_pos[0]),
        M_neg_max_tm=max(0.0, -M_neg[0]),
        V_max_t=Vmax[0],
        P_compresion_max_t=Pcomp,
        T_max_tm=Tmax[0],
        estacion_M_pos_m=M_pos[1],
        estacion_M_neg_m=M_neg[1],
        estacion_V_max_m=Vmax[1],
        combo_M_pos=M_pos[2],
        combo_M_neg=M_neg[2],
        combo_V_max=Vmax[2],
        combo_T_max=Tmax[2],
        V_gravedad_caras=(abs(gi.V2_t) if gi else 0.0, abs(gj.V2_t) if gj else 0.0),
        V_gravedad_centro=abs(gc.V2_t) if gc else 0.0,
        combo_gravedad=gravedad,
    )


def _viga(
    nombre: str,
    etiqueta: str,
    piso: str,
    b: float,
    h: float,
    L: float,
    ln: float,
    fc: float,
    eje: str,
) -> VigaETABS:
    return VigaETABS(
        nombre=nombre,
        etiqueta=etiqueta,
        piso=piso,
        eje=eje,
        seccion=f"VP-{b:.0f}x{h:.0f}",
        materiales=Materiales(fc=fc, fy=4200.0, fyt=4200.0),
        geometria=GeometriaViga(
            b=b, h=h, L=L, ln=ln, r=4.0,
            diametro_estribo=0.9525, diametro_long_estimado=1.905,
        ),
        punto_i=f"{etiqueta}-I",
        punto_j=f"{etiqueta}-J",
        coord_i=(0.0, 0.0, 3.0),
        coord_j=(L, 0.0, 3.0),
        recubrimiento_etabs_cm=6.0,
        soportes="COL-1 / COL-2",
        offset_i_m=(L - ln) / 2.0,
        offset_j_m=(L - ln) / 2.0,
        advertencias=[],
    )


def datos_demo(
    factor_sismo: float = 1.25,
) -> tuple[list[VigaETABS], dict[str, FuerzasViga], list[str]]:
    """Devuelve tres vigas con envolventes representativas."""
    combos = generar_combos_requeridas("DEAD", "LIVE", ["SISMO X"], factor_sismo)
    nombres = [c.nombre for c in combos]
    g = nombres[0]
    s_mas = nombres[1]
    s_menos = nombres[2]
    # Nombres de las 4 combinaciones sísmicas restantes
    s3 = nombres[3] if len(nombres) > 3 else s_mas
    s4 = nombres[4] if len(nombres) > 4 else s_menos

    v1 = _viga("V-101", "V-101", "Piso 2", 25, 50, 6.0, 5.4, 210, "Eje A-A / B")
    v2 = _viga("V-201", "V-201", "Piso 3", 30, 60, 7.5, 6.9, 280, "Eje B-B / C")
    v3 = _viga("V-301", "V-301", "Piso 1", 25, 50, 5.0, 4.4, 210, "Eje C-C / D")

    casos1 = {
        g: (-12.0, -13.0, 8.5, 14.0, -2.0),
        s_mas: (-18.0, -19.0, 10.0, 20.0, -1.5),
        s_menos: (-6.0, -7.0, 5.0, 8.0, -2.5),
        s3: (-15.0, -16.0, 8.0, 17.0, -1.8),
        s4: (-5.0, -6.0, 4.0, 6.0, -2.8),
    }
    casos2 = {
        g: (-22.0, -23.0, 14.0, 20.0, -3.0),
        s_mas: (-35.0, -36.0, 22.0, 28.0, -2.0),
        s_menos: (-12.0, -13.0, 9.0, 12.0, -4.0),
        s3: (-28.0, -29.0, 17.0, 24.0, -2.5),
        s4: (-9.0, -10.0, 7.0, 8.0, -3.5),
    }
    casos3 = {
        g: (-20.0, -21.0, 9.0, 22.0, -2.0),
        s_mas: (-30.0, -31.0, 12.0, 30.0, -1.0),
        s_menos: (-10.0, -11.0, 6.0, 12.0, -3.0),
        s3: (-25.0, -26.0, 10.0, 26.0, -1.5),
        s4: (-7.0, -8.0, 4.0, 8.0, -2.5),
    }
    return [v1, v2, v3], {
        v1.nombre: _fuerzas_demo(v1, casos1, g),
        v2.nombre: _fuerzas_demo(v2, casos2, g),
        v3.nombre: _fuerzas_demo(v3, casos3, g),
    }, nombres


def _verificaciones_demo(
    nombres: list[str], factor_sismo: float = 1.25,
) -> list[VerificacionCombo]:
    combos = generar_combos_requeridas("DEAD", "LIVE", ["SISMO X"], factor_sismo)
    return [
        VerificacionCombo(
            requerida=c,
            encontrada=nombres[i] if i < len(nombres) else c.nombre,
            estado="coincide",
            detalle="Caso demostrativo: combinación declarada en el modelo sintético.",
            factores_encontrados={k: v for k, v in c.factores},
        )
        for i, c in enumerate(combos)
    ]


def ejecutar_demo(
    salida: str | Path = "salidas",
    formatos: tuple[str, ...] = ("md", "docx"),
    config: ConfiguracionDiseno | None = None,
) -> tuple[list[ResultadoViga], dict]:
    """Ejecuta el flujo completo con datos sintéticos."""
    config = config or ConfiguracionDiseno(proyecto="Edificio demostración — Cusco")
    vigas, fuerzas, nombres = datos_demo(config.factor_sismo)
    resultados = [disenar_viga(v, fuerzas[v.nombre], config) for v in vigas]

    proyecto = (
        config.proyecto if config.proyecto != "Proyecto estructural"
        else "Edificio demostración — Cusco"
    )
    ubicacion = (
        config.ubicacion if config.ubicacion != "Perú" else "Cusco, Perú"
    )
    metadatos = MetadatosProyecto(
        proyecto=proyecto,
        ubicacion=ubicacion,
        ingeniero=config.ingeniero if config.ingeniero != "Ingeniero estructural"
        else "Ing. Estructural",
        cliente=config.cliente or "Cliente demostración",
        fecha=date.today().strftime("%d/%m/%Y"),
        etabs_version="v23 (datos sintéticos)",
        modelo="demo_vigas.edb",
        ruta_modelo="—",
        revision=config.revision,
        observaciones="Caso demostrativo generado por vigas_e060.",
    )
    salidas = generar_reporte(
        resultados,
        metadatos,
        _verificaciones_demo(nombres, config.factor_sismo),
        nombres,
        config,
        ruta_salida=salida,
        formatos=formatos,
    )
    return resultados, salidas
