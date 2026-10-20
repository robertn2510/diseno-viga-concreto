"""
Extracción de geometría, materiales y fuerzas internas desde ETABS.

Se usan funciones estables de la API ETABSv1 (v18–v23):

* ``FrameObj.GetAllFrames``
* ``PropFrame.GetTypeOAPI`` / ``PropFrame.GetRectangle``
* ``PropMaterial.GetMaterial`` / ``PropMaterial.GetOConcrete``
* ``FrameObj.GetLabelFromName``
* ``Results.FrameForce``

La extracción no modifica el modelo.  Las unidades se convierten con la
:class:`ConexionETABS`, de modo que el núcleo siempre recibe cm, kgf y t·m.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any

from ..config import ConfiguracionDiseno
from ..modelos import (
    EnvolventeEstacion,
    FuerzaEstacion,
    FuerzasViga,
    GeometriaViga,
    Materiales,
    VigaETABS,
)
from ..unidades import normalizar_esfuerzo
from .api import ETABSError, ETABSSinResultados, normalizar, sin_ret

TIPO_SECCION_RECTANGULAR = 8
TIPO_MATERIAL_CONCRETO = 2

# Índices de GetAllFrames (API ETABSv1)
_IF_NOMBRE = 1
_IF_SECCION = 2
_IF_PISO = 3
_IF_PTO_I = 4
_IF_PTO_J = 5
_IF_XI, _IF_YI, _IF_ZI = 6, 7, 8
_IF_XJ, _IF_YJ, _IF_ZJ = 9, 10, 11


@dataclass
class _Frame:
    nombre: str
    seccion: str
    piso: str
    pto_i: str
    pto_j: str
    xi: float
    yi: float
    zi: float
    xj: float
    yj: float
    zj: float
    L: float
    dz: float
    Lh: float


# ---------------------------------------------------------------------------
# Lectura de frames
# ---------------------------------------------------------------------------
def _leer_frames(conexion) -> list[_Frame]:
    sap = conexion.sap_model
    try:
        datos = sin_ret(sap.FrameObj.GetAllFrames())
    except Exception as exc:
        raise ETABSError(f"No se pudieron leer los elementos frame: {exc}") from exc

    if len(datos) < 12:
        return []

    n = int(datos[0])
    nombres = list(datos[_IF_NOMBRE])
    secciones = list(datos[_IF_SECCION])
    pisos = list(datos[_IF_PISO])
    ptos_i = list(datos[_IF_PTO_I])
    ptos_j = list(datos[_IF_PTO_J])

    def val(arr, idx):
        return float(arr[idx]) if idx < len(arr) else 0.0

    frames: list[_Frame] = []
    for i in range(min(n, len(nombres))):
        xi = conexion.a_m(val(datos[_IF_XI], i))
        yi = conexion.a_m(val(datos[_IF_YI], i))
        zi = conexion.a_m(val(datos[_IF_ZI], i))
        xj = conexion.a_m(val(datos[_IF_XJ], i))
        yj = conexion.a_m(val(datos[_IF_YJ], i))
        zj = conexion.a_m(val(datos[_IF_ZJ], i))
        L = hypot(hypot(xj - xi, yj - yi), zj - zi)
        Lh = hypot(xj - xi, yj - yi)
        frames.append(_Frame(
            nombre=str(nombres[i]),
            seccion=str(secciones[i]) if i < len(secciones) else "",
            piso=str(pisos[i]) if i < len(pisos) else "",
            pto_i=str(ptos_i[i]) if i < len(ptos_i) else "",
            pto_j=str(ptos_j[i]) if i < len(ptos_j) else "",
            xi=xi, yi=yi, zi=zi, xj=xj, yj=yj, zj=zj,
            L=L, dz=abs(zj - zi), Lh=Lh,
        ))
    return frames


def _es_viga(f: _Frame) -> bool:
    """Criterio geométrico: elemento casi horizontal y de longitud útil."""
    if f.L < 0.5:
        return False
    if f.Lh < 0.5:
        return False
    return f.dz <= max(0.03, 0.05 * f.L)


def _es_columna(f: _Frame) -> bool:
    return f.L > 0.3 and f.dz >= 0.8 * f.L


# ---------------------------------------------------------------------------
# Propiedades de sección y materiales
# ---------------------------------------------------------------------------
def _tipo_seccion(sap, seccion: str) -> int | None:
    try:
        res = sap.PropFrame.GetTypeOAPI(seccion)
        datos = sin_ret(res)
        if datos:
            return int(datos[0])
    except Exception:
        pass
    return None


def _dimensiones_rectangulo(conexion, seccion: str) -> tuple[float, float, str] | None:
    """Devuelve (b_cm, h_cm, material) de una sección rectangular."""
    sap = conexion.sap_model
    try:
        datos = sin_ret(sap.PropFrame.GetRectangle(seccion))
    except Exception:
        return None
    # (FileName, MatProp, T3, T2, Color, Notes, GUID)
    if len(datos) < 4:
        return None
    mat = str(datos[1])
    t3 = float(datos[2])  # peralte h
    t2 = float(datos[3])  # ancho b
    b_cm = conexion.a_m(t2) * 100.0
    h_cm = conexion.a_m(t3) * 100.0
    return b_cm, h_cm, mat


def _tipo_material(sap, material: str) -> int | None:
    try:
        datos = sin_ret(sap.PropMaterial.GetMaterial(material))
        if datos:
            return int(datos[0])
    except Exception:
        pass
    return None


def _fc_material(conexion, material: str) -> tuple[float | None, str | None]:
    sap = conexion.sap_model
    try:
        datos = sin_ret(sap.PropMaterial.GetOConcrete(material))
        if not datos:
            return None, None
        fc_raw = float(datos[0])
        fc = conexion.a_kgcm2(fc_raw)
        if not (100.0 < fc < 900.0):
            fc = normalizar_esfuerzo(fc_raw)
        if 100.0 < fc < 900.0:
            return fc, None
        return None, f"f'c leído fuera de rango ({fc:.1f} kgf/cm²)."
    except Exception as exc:
        return None, f"No se pudo leer f'c del material {material!r}: {exc}"


def _recubrimiento_etabs(conexion, seccion: str) -> float | None:
    """Recubrimiento al centroide de la armadura, en cm, si está definido."""
    sap = conexion.sap_model
    try:
        datos = sin_ret(sap.PropFrame.GetRebarBeam(seccion))
    except Exception:
        return None
    # (MatPropLong, MatPropConfine, CoverTop, CoverBot, áreas...)
    if len(datos) < 4:
        return None
    try:
        cubiertas = [conexion.a_m(float(datos[2])) * 100.0,
                     conexion.a_m(float(datos[3])) * 100.0]
        validas = [c for c in cubiertas if 2.0 < c < 20.0]
        return min(validas) if validas else None
    except Exception:
        return None


def _etiqueta_y_piso(sap, nombre: str, piso_frame: str) -> tuple[str, str]:
    try:
        datos = sin_ret(sap.FrameObj.GetLabelFromName(nombre))
        if len(datos) >= 2:
            etiqueta = str(datos[0]) or nombre
            piso = str(datos[1]) or piso_frame
            return etiqueta, piso
    except Exception:
        pass
    return nombre, piso_frame


# ---------------------------------------------------------------------------
# Luz libre y apoyos
# ---------------------------------------------------------------------------
def _estimar_luz_libre(
    conexion,
    viga: _Frame,
    frames: list[_Frame],
    cache_secciones: dict[str, tuple[float, float, str] | None],
) -> tuple[float, float, float, str]:
    """
    Estima ln y los offsets a la cara de apoyo a partir de las columnas
    conectadas en los extremos.  Si no se encuentran, usa L entre ejes.
    """
    por_punto: dict[str, list[_Frame]] = {}
    for f in frames:
        por_punto.setdefault(f.pto_i, []).append(f)
        por_punto.setdefault(f.pto_j, []).append(f)

    def dimension_columna(punto: str) -> tuple[float, str]:
        for f in por_punto.get(punto, []):
            if f.nombre == viga.nombre or not _es_columna(f):
                continue
            if f.seccion not in cache_secciones:
                cache_secciones[f.seccion] = _dimensiones_rectangulo(conexion, f.seccion)
            dims = cache_secciones[f.seccion]
            if dims:
                b, h, _ = dims
                return max(b, h) / 100.0, f.nombre  # m, conservador
        return 0.0, ""

    di, col_i = dimension_columna(viga.pto_i)
    dj, col_j = dimension_columna(viga.pto_j)
    offset_i = di / 2.0
    offset_j = dj / 2.0
    ln = max(0.1, viga.L - offset_i - offset_j)
    soportes = " / ".join(x for x in (col_i, col_j) if x)
    return ln, offset_i, offset_j, soportes


# ---------------------------------------------------------------------------
# Extracción principal de vigas
# ---------------------------------------------------------------------------
def extraer_vigas(conexion, config: ConfiguracionDiseno) -> list[VigaETABS]:
    """Extrae las vigas de concreto rectangulares del modelo."""
    sap = conexion.sap_model
    frames = _leer_frames(conexion)
    cache_secciones: dict[str, tuple[float, float, str] | None] = {}
    vigas: list[VigaETABS] = []
    advertencias_globales: list[str] = []

    solicitadas = {normalizar(v) for v in config.vigas if v}

    for f in frames:
        if not _es_viga(f):
            continue

        tipo = _tipo_seccion(sap, f.seccion)
        if tipo is not None and tipo != TIPO_SECCION_RECTANGULAR:
            if solicitadas and normalizar(f.nombre) in solicitadas:
                advertencias_globales.append(
                    f"{f.nombre}: la sección {f.seccion!r} no es rectangular "
                    f"(tipo {tipo}); se omite."
                )
            continue

        if f.seccion not in cache_secciones:
            cache_secciones[f.seccion] = _dimensiones_rectangulo(conexion, f.seccion)
        dims = cache_secciones[f.seccion]
        if dims is None:
            continue
        b, h, material = dims

        tipo_mat = _tipo_material(sap, material)
        if tipo_mat is not None and tipo_mat != TIPO_MATERIAL_CONCRETO:
            if solicitadas and normalizar(f.nombre) in solicitadas:
                advertencias_globales.append(
                    f"{f.nombre}: material {material!r} no es concreto; se omite."
                )
            continue

        fc, adv_fc = _fc_material(conexion, material)
        advertencias: list[str] = []
        if fc is None:
            fc = config.fc_default
            advertencias.append(
                adv_fc or f"No se pudo leer f'c; se usa {config.fc_default:.0f} kgf/cm²."
            )
        elif abs(fc - 210.0) > 1.0 and abs(fc - 280.0) > 1.0:
            advertencias.append(
                f"f'c = {fc:.1f} kgf/cm² no es 210 ni 280; se respeta el valor del modelo."
            )
        if config.forzar_fc:
            if abs(fc - config.fc_default) > 1.0:
                advertencias.append(
                    f"Se fuerza f'c = {config.fc_default:.0f} kgf/cm² por configuración "
                    f"(ETABS reportaba {fc:.1f})."
                )
            fc = config.fc_default

        r = config.recubrimiento_libre_cm
        cover_etabs = _recubrimiento_etabs(conexion, f.seccion)
        if config.usar_recubrimiento_etabs and cover_etabs is not None:
            r_estimado = cover_etabs - 1.905 / 2.0 - 0.9525
            if 1.5 <= r_estimado <= 8.0:
                r = r_estimado
            else:
                advertencias.append(
                    f"Recubrimiento de ETABS ({cover_etabs:.2f} cm al centroide) "
                    "no es coherente; se usa el valor de configuración."
                )

        if b > h:
            advertencias.append(
                f"b = {b:.1f} cm > h = {h:.1f} cm. Verifique los ejes locales "
                "de la sección (posible viga chata o eje rotado)."
            )
        if b < 25.0:
            advertencias.append("b < 25 cm: no cumple E.060 21.5.1.3 para pórticos especiales.")
        if b < 0.25 * h:
            advertencias.append("b < 0.25h: no cumple E.060 21.5.1.3.")
        if r < 3.0:
            advertencias.append("Recubrimiento libre < 3 cm; revise E.060 7.7.1.")

        ln, off_i, off_j, soportes = _estimar_luz_libre(
            conexion, f, frames, cache_secciones
        )
        if ln < 4.0 * h / 100.0:
            advertencias.append(
                f"ln = {ln:.2f} m < 4h = {4*h/100:.2f} m (E.060 21.5.1.1)."
            )

        etiqueta, piso = _etiqueta_y_piso(sap, f.nombre, f.piso)
        eje = (
            f"X = {f.xi:.2f} m / Y = {f.yi:.2f} m"
            if abs(f.xi - f.xj) + abs(f.yi - f.yj) > 1e-6
            else f"X = {f.xi:.2f} m / Y = {f.yi:.2f} m"
        )

        geom = GeometriaViga(
            b=b, h=h, L=f.L, ln=ln, r=r,
            diametro_estribo=0.9525,
            diametro_long_estimado=1.905,
        )
        vigas.append(VigaETABS(
            nombre=f.nombre,
            etiqueta=etiqueta,
            piso=piso,
            eje=eje,
            seccion=f.seccion,
            materiales=Materiales(fc=fc, fy=config.fy_default, fyt=config.fyt_default),
            geometria=geom,
            punto_i=f.pto_i,
            punto_j=f.pto_j,
            coord_i=(f.xi, f.yi, f.zi),
            coord_j=(f.xj, f.yj, f.zj),
            recubrimiento_etabs_cm=cover_etabs,
            soportes=soportes,
            offset_i_m=off_i,
            offset_j_m=off_j,
            advertencias=advertencias,
        ))

    # Filtros posteriores
    if config.secciones:
        patrones = [normalizar(s) for s in config.secciones]
        vigas = [v for v in vigas if any(p in normalizar(v.seccion) for p in patrones)]
    if config.pisos:
        patrones = [normalizar(s) for s in config.pisos]
        vigas = [v for v in vigas if any(p in normalizar(v.piso) for p in patrones)]
    if config.vigas:
        patrones = {normalizar(v) for v in config.vigas}
        filtradas = [
            v for v in vigas
            if normalizar(v.nombre) in patrones or normalizar(v.etiqueta) in patrones
        ]
        faltantes = patrones - {normalizar(v.nombre) for v in filtradas} - {
            normalizar(v.etiqueta) for v in filtradas
        }
        for f in sorted(faltantes):
            advertencias_globales.append(f"No se encontró la viga solicitada {f!r}.")
        vigas = filtradas
    if config.max_vigas:
        vigas = vigas[: config.max_vigas]

    for v in vigas:
        v.advertencias.extend(advertencias_globales)
    return vigas


# ---------------------------------------------------------------------------
# Fuerzas internas
# ---------------------------------------------------------------------------
def _interpolar(puntos: list[FuerzaEstacion], x: float) -> FuerzaEstacion | None:
    """Interpola linealmente M3, V2, P y T en la estación x (m)."""
    if not puntos:
        return None
    pts = sorted(puntos, key=lambda p: p.estacion_m)
    if x <= pts[0].estacion_m + 1e-9:
        return pts[0]
    if x >= pts[-1].estacion_m - 1e-9:
        return pts[-1]

    for a, b in zip(pts, pts[1:]):
        if a.estacion_m - 1e-9 <= x <= b.estacion_m + 1e-9:
            dx = b.estacion_m - a.estacion_m
            if abs(dx) < 1e-9:
                return a
            t = (x - a.estacion_m) / dx
            return FuerzaEstacion(
                estacion_m=x,
                M3_tm=a.M3_tm + t * (b.M3_tm - a.M3_tm),
                V2_t=a.V2_t + t * (b.V2_t - a.V2_t),
                P_t=a.P_t + t * (b.P_t - a.P_t),
                T_tm=a.T_tm + t * (b.T_tm - a.T_tm),
                combo=a.combo,
            )
    return pts[-1]


def _promediar_estaciones(puntos: list[FuerzaEstacion]) -> list[FuerzaEstacion]:
    """Agrupa estaciones repetidas (extremos de elementos internos) promediando."""
    grupos: dict[float, list[FuerzaEstacion]] = {}
    for p in puntos:
        grupos.setdefault(round(p.estacion_m, 5), []).append(p)
    res: list[FuerzaEstacion] = []
    for x, g in sorted(grupos.items()):
        n = len(g)
        res.append(FuerzaEstacion(
            estacion_m=x,
            M3_tm=sum(p.M3_tm for p in g) / n,
            V2_t=sum(p.V2_t for p in g) / n,
            P_t=sum(p.P_t for p in g) / n,
            T_tm=sum(p.T_tm for p in g) / n,
            combo=g[0].combo,
        ))
    return res


def leer_fuerzas_combo(conexion, nombre_viga: str, combo: str) -> list[FuerzaEstacion]:
    """Lee ``Results.FrameForce`` y devuelve las estaciones del combo."""
    sap = conexion.sap_model
    try:
        datos = sin_ret(sap.Results.FrameForce(nombre_viga, 0))
    except Exception as exc:
        raise ETABSError(
            f"FrameForce falló para la viga {nombre_viga!r}: {exc}"
        ) from exc
    if len(datos) < 14:
        return []

    n = int(datos[0])
    obj_sta = list(datos[2])
    casos = list(datos[5])
    P = list(datos[8])
    V2 = list(datos[9])
    T = list(datos[11])
    M3 = list(datos[13])

    puntos: list[FuerzaEstacion] = []
    combo_norm = normalizar(combo)
    for i in range(min(n, len(casos))):
        if normalizar(str(casos[i])) != combo_norm:
            continue
        x = conexion.a_m(float(obj_sta[i]))
        puntos.append(FuerzaEstacion(
            estacion_m=x,
            M3_tm=conexion.a_tm(float(M3[i])),
            V2_t=conexion.a_t(float(V2[i])),
            P_t=conexion.a_t(float(P[i])),
            T_tm=conexion.a_tm(float(T[i])),
            combo=str(casos[i]),
        ))
    return sorted(puntos, key=lambda p: p.estacion_m)


def _envolvente(
    por_combo: dict[str, list[FuerzaEstacion]],
    estacion_m: float,
    nombre_estacion: str,
    p_compresion_negativa: bool,
) -> EnvolventeEstacion | None:
    valores: list[FuerzaEstacion] = []
    for combo, pts in por_combo.items():
        exactos = [p for p in pts if abs(p.estacion_m - estacion_m) <= 1e-4]
        if exactos:
            for p in exactos:
                valores.append(FuerzaEstacion(
                    estacion_m=estacion_m, M3_tm=p.M3_tm, V2_t=p.V2_t,
                    P_t=p.P_t, T_tm=p.T_tm, combo=combo,
                ))
            continue
        p = _interpolar(pts, estacion_m)
        if p is not None:
            valores.append(FuerzaEstacion(
                estacion_m=estacion_m, M3_tm=p.M3_tm, V2_t=p.V2_t,
                P_t=p.P_t, T_tm=p.T_tm, combo=combo,
            ))
    if not valores:
        return None

    m_max = max(valores, key=lambda p: p.M3_tm)
    m_min = min(valores, key=lambda p: p.M3_tm)
    v_max = max(valores, key=lambda p: abs(p.V2_t))
    t_max = max(valores, key=lambda p: abs(p.T_tm))
    p_max = max(valores, key=lambda p: p.P_t)
    p_min = min(valores, key=lambda p: p.P_t)
    return EnvolventeEstacion(
        estacion_m=estacion_m,
        M3_max_tm=m_max.M3_tm,
        M3_min_tm=m_min.M3_tm,
        V2_max_t=abs(v_max.V2_t),
        P_min_t=p_min.P_t,
        P_max_t=p_max.P_t,
        T_max_tm=abs(t_max.T_tm),
        combo_M3_max=m_max.combo,
        combo_M3_min=m_min.combo,
        combo_V2_max=v_max.combo,
        combo_T_max=t_max.combo,
    )


def extraer_fuerzas(
    conexion,
    viga: VigaETABS,
    combos: list[str],
    combo_gravedad: str | None = None,
    p_compresion_negativa: bool = True,
) -> FuerzasViga:
    """Extrae la envolvente de M3, V2, P y T en las estaciones clave."""
    if not combos:
        raise ETABSSinResultados(
            "No hay combinaciones de diseño disponibles para extraer fuerzas."
        )

    por_combo: dict[str, list[FuerzaEstacion]] = {}
    advertencias: list[str] = []
    for combo in combos:
        pts = leer_fuerzas_combo(conexion, viga.nombre, combo)
        if not pts:
            advertencias.append(
                f"No hay resultados de FrameForce para el combo {combo!r}; "
                "verifique que el análisis esté ejecutado y el combo seleccionado."
            )
            continue
        por_combo[combo] = pts

    if not por_combo:
        raise ETABSSinResultados(
            f"No se obtuvieron fuerzas para la viga {viga.nombre!r}. "
            "Ejecute el análisis en ETABS y verifique las combinaciones."
        )

    L_etabs = max(p.estacion_m for pts in por_combo.values() for p in pts)
    if abs(L_etabs - viga.geometria.L) > 0.02:
        advertencias.append(
            f"La longitud de resultados ({L_etabs:.3f} m) difiere de la geometría "
            f"({viga.geometria.L:.3f} m); se usa la de resultados."
        )
    L = L_etabs if L_etabs > 0 else viga.geometria.L

    estaciones = {
        "I-End": 0.0,
        "Centro": L / 2.0,
        "J-End": L,
        "Cara-I": min(max(viga.offset_i_m, 0.0), L / 2.0),
        "Cara-J": max(min(L - viga.offset_j_m, L), L / 2.0),
    }

    env: dict[str, EnvolventeEstacion] = {}
    for nombre, x in estaciones.items():
        e = _envolvente(por_combo, x, nombre, p_compresion_negativa)
        if e is not None:
            env[nombre] = e
    if "Centro" not in env:
        raise ETABSSinResultados(f"No se pudo interpolar el centro de la viga {viga.nombre!r}.")

    # Envolvente global en todas las estaciones
    M_pos = (-1e30, 0.0, "")
    M_neg = (0.0, 0.0, "")
    V_max = (0.0, 0.0, "")
    T_max = (0.0, 0.0, "")
    P_comp = 0.0
    for combo, pts in por_combo.items():
        for p in pts:
            if p.M3_tm > M_pos[0]:
                M_pos = (p.M3_tm, p.estacion_m, combo)
            if p.M3_tm < M_neg[0]:
                M_neg = (p.M3_tm, p.estacion_m, combo)
            if abs(p.V2_t) > V_max[0]:
                V_max = (abs(p.V2_t), p.estacion_m, combo)
            if abs(p.T_tm) > T_max[0]:
                T_max = (abs(p.T_tm), p.estacion_m, combo)
            comp = -p.P_t if p_compresion_negativa else p.P_t
            P_comp = max(P_comp, comp)

    # Cortante gravitacional
    Vg_i = Vg_j = Vg_c = 0.0
    if combo_gravedad and combo_gravedad in por_combo:
        gi = _interpolar(por_combo[combo_gravedad], estaciones["Cara-I"])
        gj = _interpolar(por_combo[combo_gravedad], estaciones["Cara-J"])
        gc = _interpolar(por_combo[combo_gravedad], estaciones["Centro"])
        Vg_i = abs(gi.V2_t) if gi else 0.0
        Vg_j = abs(gj.V2_t) if gj else 0.0
        Vg_c = abs(gc.V2_t) if gc else 0.0
    else:
        advertencias.append(
            "No se identificó el combo de gravedad 1.4D+1.7L; el cortante "
            "gravitacional se toma como cero en el diseño por capacidad."
        )

    return FuerzasViga(
        combos=list(por_combo),
        por_combo=por_combo,
        estaciones_clave=env,
        M_pos_max_tm=max(0.0, M_pos[0]),
        M_neg_max_tm=max(0.0, -M_neg[0]),
        V_max_t=V_max[0],
        P_compresion_max_t=P_comp,
        T_max_tm=T_max[0],
        estacion_M_pos_m=M_pos[1],
        estacion_M_neg_m=M_neg[1],
        estacion_V_max_m=V_max[1],
        combo_M_pos=M_pos[2],
        combo_M_neg=M_neg[2],
        combo_V_max=V_max[2],
        combo_T_max=T_max[2],
        V_gravedad_caras=(Vg_i, Vg_j),
        V_gravedad_centro=Vg_c,
        combo_gravedad=combo_gravedad or "",
        advertencias=advertencias,
    )


def listar_resumen_vigas(vigas: list[VigaETABS]) -> list[dict[str, Any]]:
    """Resumen tabular para la consola / modo --listar."""
    filas: list[dict[str, Any]] = []
    for v in vigas:
        filas.append({
            "Nombre": v.nombre,
            "Etiqueta": v.etiqueta,
            "Piso": v.piso,
            "Sección": v.seccion,
            "b (cm)": round(v.geometria.b, 1),
            "h (cm)": round(v.geometria.h, 1),
            "L (m)": round(v.geometria.L, 3),
            "ln (m)": round(v.geometria.ln, 3),
            "f'c": round(v.materiales.fc, 1),
            "Eje/ubicación": v.eje,
        })
    return filas
