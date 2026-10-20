"""
Catálogo de varillas comerciales y selección de armadura.

Los diámetros y áreas corresponden a las barras corrugadas ASTM A615 grado 60
usadas en el Perú.  El área es la nominal: 3/8" = 0.71 cm², 1/2" = 1.27 cm²,
5/8" = 1.98 cm², 3/4" = 2.85 cm², 1" = 5.07 cm².

La selección verifica la colocación física: separación libre mínima
``max(db, 2.5 cm)`` (E.060 7.6.1), número máximo de capas y ancho útil entre
estribos.  El peralte efectivo se recalcula con el centroide real de la
armadura, no con un valor supuesto.
"""

from __future__ import annotations

from math import ceil, floor, isclose

from ..modelos import CapaVarillas, SeleccionVarillas, Varilla

# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------
VARILLAS_LONGITUDINALES: tuple[Varilla, ...] = (
    Varilla('3/8"', 0.9525, 0.71),
    Varilla('1/2"', 1.2700, 1.27),
    Varilla('5/8"', 1.5875, 1.98),
    Varilla('3/4"', 1.9050, 2.85),
    Varilla('1"', 2.5400, 5.07),
    Varilla('1 3/8"', 3.4925, 10.06),
)

VARILLAS_ESTRIBO: tuple[Varilla, ...] = (
    Varilla("6 mm", 0.60, 0.28),
    Varilla("8 mm", 0.80, 0.50),
    Varilla('3/8"', 0.9525, 0.71),
    Varilla('1/2"', 1.2700, 1.27),
)

POR_NOMBRE: dict[str, Varilla] = {
    v.nombre.upper().replace(" ", ""): v
    for v in (*VARILLAS_LONGITUDINALES, *VARILLAS_ESTRIBO)
}

SEPARACION_LIBRE_MINIMA_CM = 2.5  # E.060 7.6.1


class ErrorVarillas(ValueError):
    pass


def buscar_varilla(nombre: str, estribo: bool = False) -> Varilla:
    """Busca una varilla por nombre comercial, p. ej. ``3/4"`` o ``8 mm``."""
    clave = str(nombre).upper().replace(" ", "").replace("Φ", "").replace("Ø", "")
    if clave in POR_NOMBRE:
        return POR_NOMBRE[clave]
    catalogo = VARILLAS_ESTRIBO if estribo else VARILLAS_LONGITUDINALES
    for v in catalogo:
        if isclose(v.diametro_cm, float(str(nombre).replace(",", ".")), rel_tol=0.02):
            return v
    raise ErrorVarillas(
        f"Varilla no reconocida: {nombre!r}. Use: "
        + ", ".join(v.nombre for v in catalogo)
    )


def diametros_disponibles(
    minimo_cm: float = 1.27,
    maximo_cm: float = 2.54,
) -> list[Varilla]:
    """Varillas longitudinales dentro del rango práctico configurado."""
    return [
        v for v in VARILLAS_LONGITUDINALES
        if minimo_cm - 1e-9 <= v.diametro_cm <= maximo_cm + 1e-9
    ]


# ---------------------------------------------------------------------------
# Colocación física
# ---------------------------------------------------------------------------
def _n_por_capa(b: float, r: float, dst: float, db: float, s_libre: float) -> int:
    ancho_util = b - 2.0 * (r + dst)
    if ancho_util < db:
        return 0
    return max(0, floor((ancho_util + s_libre) / (db + s_libre) + 1e-9))


def construir_seleccion(
    varilla: Varilla,
    cantidad: int,
    b: float,
    h: float,
    r: float,
    dst: float,
    max_capas: int = 2,
) -> SeleccionVarillas:
    """
    Construye una distribución con barras del mismo diámetro y calcula su
    centroide.  Si no cabe, devuelve ``cabe=False`` con el motivo.
    """
    db = varilla.diametro_cm
    s_libre = max(SEPARACION_LIBRE_MINIMA_CM, db)
    n_per = _n_por_capa(b, r, dst, db, s_libre)
    ancho_util = b - 2.0 * (r + dst)

    if cantidad < 2:
        cantidad = 2
    if n_per < 2:
        return SeleccionVarillas(
            capas=[],
            area_cm2=varilla.area_cm2 * cantidad,
            y_cm=0.0,
            ancho_requerido_cm=2.0 * (r + dst) + db,
            separacion_libre_cm=0.0,
            cabe=False,
            mensaje=f"No caben 2 Φ {varilla.nombre} en b = {b:.1f} cm.",
        )

    if cantidad <= n_per:
        capas = [CapaVarillas(varilla, cantidad)]
        y = r + dst + db / 2.0
        n_max_capa = cantidad
    elif max_capas >= 2 and cantidad <= 2 * n_per:
        # Reparto equilibrado entre dos capas, cada una con ≥ 2 barras.
        n1 = max(2, ceil(cantidad / 2))
        n2 = cantidad - n1
        if n2 < 2:
            n1 -= 1
            n2 += 1
        if n1 > n_per or n2 > n_per:
            return SeleccionVarillas(
                capas=[],
                area_cm2=varilla.area_cm2 * cantidad,
                y_cm=0.0,
                ancho_requerido_cm=0.0,
                separacion_libre_cm=0.0,
                cabe=False,
                mensaje=f"{cantidad} Φ {varilla.nombre} no caben en {max_capas} capas.",
            )
        s_v = max(SEPARACION_LIBRE_MINIMA_CM, db)
        y1 = r + dst + db / 2.0
        y2 = r + dst + db + s_v + db / 2.0
        y = (n1 * y1 + n2 * y2) / cantidad
        capas = [CapaVarillas(varilla, n1), CapaVarillas(varilla, n2)]
        n_max_capa = max(n1, n2)
    else:
        return SeleccionVarillas(
            capas=[],
            area_cm2=varilla.area_cm2 * cantidad,
            y_cm=0.0,
            ancho_requerido_cm=0.0,
            separacion_libre_cm=0.0,
            cabe=False,
            mensaje=(
                f"{cantidad} Φ {varilla.nombre} requieren más de {max_capas} "
                f"capas (máx. {n_per} por capa)."
            ),
        )

    ancho_req = 2.0 * (r + dst) + n_max_capa * db + (n_max_capa - 1) * s_libre
    s_real = (
        (ancho_util - n_max_capa * db) / (n_max_capa - 1)
        if n_max_capa > 1 else ancho_util - db
    )
    cabe = ancho_req <= b + 1e-6 and y <= h / 2.0
    mensaje = ""
    if y > h / 2.0:
        mensaje = "El centroide de la armadura supera el medio peralte."

    return SeleccionVarillas(
        capas=capas,
        area_cm2=varilla.area_cm2 * cantidad,
        y_cm=y,
        ancho_requerido_cm=ancho_req,
        separacion_libre_cm=s_real,
        cabe=cabe,
        mensaje=mensaje,
    )


def opciones_seleccion(
    As_req_cm2: float,
    b: float,
    h: float,
    r: float,
    dst: float,
    varillas: list[Varilla] | None = None,
    max_capas: int = 2,
    n_max: int = 14,
) -> list[SeleccionVarillas]:
    """Todas las distribuciones factibles con área ≥ As requerido."""
    varillas = varillas or diametros_disponibles()
    opciones: list[SeleccionVarillas] = []
    for v in varillas:
        n_min = max(2, ceil(max(As_req_cm2, 0.0) / v.area_cm2 - 1e-9))
        for n in range(n_min, n_max + 1):
            sel = construir_seleccion(v, n, b, h, r, dst, max_capas=max_capas)
            if sel.cabe and sel.area_cm2 + 1e-9 >= As_req_cm2:
                opciones.append(sel)
    opciones.sort(key=lambda s: (round(s.area_cm2, 2), s.cantidad, s.diametro_max))
    return opciones


def seleccionar_varillas(
    As_req_cm2: float,
    b: float,
    h: float,
    r: float,
    dst: float,
    varillas: list[Varilla] | None = None,
    max_capas: int = 2,
    n_max: int = 14,
) -> SeleccionVarillas | None:
    """
    Selecciona la distribución comercial de menor área que cumple As requerido.

    El criterio es: menor área colocada, luego menor número de barras y luego
    menor diámetro.  Devuelve ``None`` si ninguna distribución cabe.
    """
    opciones = opciones_seleccion(
        As_req_cm2, b, h, r, dst, varillas=varillas,
        max_capas=max_capas, n_max=n_max,
    )
    return opciones[0] if opciones else None


def seleccionar_estribo(
    nombre: str,
    db_long_max: float,
    b: float,
    r: float,
    max_sep_ramas: float = 30.0,
) -> tuple[Varilla, int]:
    """
    Selecciona el diámetro de estribo y el número de ramas.

    * E.060 21.5.3.2: diámetro mínimo 3/8" para barras longitudinales ≤ 1" y
      1/2" para barras mayores.
    * E.060 21.5.3.6: separación horizontal entre ramas ≤ 30 cm.
    """
    from ..normativa.e060 import diametro_minimo_estribo

    v = buscar_varilla(nombre, estribo=True)
    dmin = diametro_minimo_estribo(db_long_max)
    if v.diametro_cm < dmin - 1e-9:
        v = buscar_varilla('1/2"' if dmin > 1.0 else '3/8"', estribo=True)

    ancho_nucleo = b - 2.0 * (r + v.diametro_cm)
    ramas = 2
    while ramas < 8 and ancho_nucleo / (ramas - 1) > max_sep_ramas + 1e-9:
        ramas += 1
    return v, ramas


def longitud_estribo_cm(b: float, h: float, r: float, db_estribo: float) -> float:
    """
    Longitud aproximada de una pieza de estribo cerrado, incluyendo ganchos
    sísmicos a 135° (E.060 7.1.3): perímetro al eje del estribo + 2×10db.
    """
    perimetro = 2.0 * ((b - 2.0 * r - db_estribo) + (h - 2.0 * r - db_estribo))
    ganchos = 2.0 * 10.0 * db_estribo
    return perimetro + ganchos


def peso_estribos_kg(
    n_estribos: int,
    b: float,
    h: float,
    r: float,
    db_estribo: float,
    varilla: Varilla,
) -> float:
    longitud_m = longitud_estribo_cm(b, h, r, db_estribo) / 100.0
    return n_estribos * longitud_m * varilla.peso_kg_m


def etiqueta_varillas(seleccion: SeleccionVarillas | None) -> str:
    return seleccion.etiqueta if seleccion else "—"
