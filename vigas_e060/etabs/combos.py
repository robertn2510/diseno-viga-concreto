"""
Combinaciones de carga de la E.060 y verificación contra ETABS.

La E.060, artículo 9.2, exige como mínimo:

    U = 1.4·CM + 1.7·CV                                  (9-1)
    U = 1.25·(CM + CV) ± CS                              (9-4)
    U = 0.9·CM ± CS                                      (9-5)

El usuario solicitó explícitamente la variante con factor 1.25 sobre la acción
sísmica (práctica ACI y edición 2006):

    U = 1.25·(D + L) ± 1.25·S
    U = 0.9·D ± 1.25·S

El programa adopta esa variante por defecto (``norma_combinaciones='usuario'``)
y permite cambiarla a la variante 9.2.3 con factor 1.0
(``norma_combinaciones='e060-2009'``).  En la memoria se documenta la variante
seleccionada y se comparan las combinaciones requeridas con las definidas en
ETABS, incluyendo las combinaciones de diseño de concreto del programa.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..modelos import ComboRequerida, VerificacionCombo
from .api import (
    ETABSError,
    lista,
    normalizar,
    primer_coincidente,
    ret_de,
    sin_ret,
)

TOL_FACTOR = 1e-3


@dataclass
class DefinicionCombo:
    nombre: str
    tipo: int
    factores: dict[str, float]
    anidado: bool = False


@dataclass
class CasosDetectados:
    muerta: str | None = None
    viva: str | None = None
    sismo: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Generación de combinaciones
# ---------------------------------------------------------------------------
def _sanitizar(nombre: str) -> str:
    return "".join(c for c in nombre if c.isalnum())[:12] or "S"


def generar_combos_requeridas(
    caso_muerta: str,
    caso_viva: str,
    casos_sismo: list[str] | tuple[str, ...] = (),
    factor_sismo: float = 1.25,
) -> list[ComboRequerida]:
    """Genera las combinaciones requeridas, sin duplicados."""
    combos: list[ComboRequerida] = [
        ComboRequerida(
            "E060-1.4D+1.7L",
            ((caso_muerta, 1.4), (caso_viva, 1.7)),
            "E.060 9.2.1 (9-1)",
        )
    ]

    for s in casos_sismo:
        if not s:
            continue
        sfx = _sanitizar(s)
        definiciones = [
            (
                f"E060-1.25(D+L)+{factor_sismo:g}{sfx}",
                ((caso_muerta, 1.25), (caso_viva, 1.25), (s, factor_sismo)),
                f"E.060 9.2.3 (9-4) — variante {factor_sismo:g}·CS",
            ),
            (
                f"E060-1.25(D+L)-{factor_sismo:g}{sfx}",
                ((caso_muerta, 1.25), (caso_viva, 1.25), (s, -factor_sismo)),
                f"E.060 9.2.3 (9-4) — variante {factor_sismo:g}·CS",
            ),
            (
                f"E060-0.9D+{factor_sismo:g}{sfx}",
                ((caso_muerta, 0.9), (s, factor_sismo)),
                f"E.060 9.2.3 (9-5) — variante {factor_sismo:g}·CS",
            ),
            (
                f"E060-0.9D-{factor_sismo:g}{sfx}",
                ((caso_muerta, 0.9), (s, -factor_sismo)),
                f"E.060 9.2.3 (9-5) — variante {factor_sismo:g}·CS",
            ),
        ]
        for nombre, factores, ref in definiciones:
            combos.append(ComboRequerida(nombre, factores, ref))

    # Deduplicar por firma de factores
    vistos: set[tuple[tuple[str, float], ...]] = set()
    unicos: list[ComboRequerida] = []
    for c in combos:
        firma = tuple(sorted((normalizar(k), round(v, 6)) for k, v in c.factores))
        if firma not in vistos:
            vistos.add(firma)
            unicos.append(c)
    return unicos


# ---------------------------------------------------------------------------
# Lectura de ETABS
# ---------------------------------------------------------------------------
def _tipo_combo(sap, nombre: str) -> int:
    for metodo in ("GetTypeOAPI", "GetTypeCombo", "GetComboType"):
        fn = getattr(getattr(sap, "RespCombo", None), metodo, None)
        if fn is None:
            continue
        try:
            res = fn(nombre)
            datos = sin_ret(res)
            if datos and isinstance(datos[0], int):
                return int(datos[0])
            if type(res) is int:
                return int(res)
        except Exception:
            continue
    return 0


def leer_combos_existentes(sap) -> dict[str, DefinicionCombo]:
    """Lee todas las combinaciones y sus factores desde ETABS."""
    try:
        nombres = lista(sap.RespCombo.GetNameList(), 1)
    except Exception as exc:  # pragma: no cover - depende de ETABS
        raise ETABSError(f"No se pudieron leer las combinaciones: {exc}") from exc

    existentes: dict[str, DefinicionCombo] = {}
    for nombre in nombres:
        factores: dict[str, float] = {}
        anidado = False
        try:
            datos = sin_ret(sap.RespCombo.GetCaseList(nombre))
            # (NumberItems, CNameType[], CName[], SF[])
            tipos = list(datos[1]) if len(datos) > 1 else []
            casos = list(datos[2]) if len(datos) > 2 else []
            sfs = list(datos[3]) if len(datos) > 3 else []
            for i, caso in enumerate(casos):
                if i < len(tipos) and int(tipos[i]) == 1:
                    anidado = True
                factores[str(caso)] = float(sfs[i]) if i < len(sfs) else 1.0
        except Exception:
            # Una combinación de envolvente puede no exponer GetCaseList.
            factores = {}
        existentes[nombre] = DefinicionCombo(
            nombre=nombre,
            tipo=_tipo_combo(sap, nombre),
            factores=factores,
            anidado=anidado,
        )
    return existentes


def _comparar(req: ComboRequerida, existente: DefinicionCombo) -> tuple[str, str, dict[str, float]]:
    req_norm = {normalizar(k): round(v, 6) for k, v in req.factores if abs(v) > 1e-9}
    ex_norm = {normalizar(k): round(v, 6) for k, v in existente.factores.items() if abs(v) > 1e-9}

    if existente.anidado:
        return "no_verificable", "La combinación contiene combinaciones anidadas.", existente.factores
    if not ex_norm:
        return "no_verificable", "No se pudo leer la lista de casos.", existente.factores

    faltan = set(req_norm) - set(ex_norm)
    sobran = set(ex_norm) - set(req_norm)
    if faltan:
        return "parcial", f"Faltan casos: {', '.join(sorted(faltan))}.", existente.factores
    if sobran:
        return "parcial", f"Contiene casos adicionales: {', '.join(sorted(sobran))}.", existente.factores
    diferencias = [
        f"{k}: requerido {req_norm[k]:g}, ETABS {ex_norm[k]:g}"
        for k in req_norm if abs(req_norm[k] - ex_norm[k]) > TOL_FACTOR
    ]
    if diferencias:
        return "parcial", "; ".join(diferencias) + ".", existente.factores
    return "coincide", "Factores y casos coinciden.", existente.factores


def verificar_combinaciones(
    sap,
    requeridas: list[ComboRequerida],
) -> list[VerificacionCombo]:
    """Compara cada combinación requerida con las definidas en ETABS."""
    existentes = leer_combos_existentes(sap)
    resultados: list[VerificacionCombo] = []

    for req in requeridas:
        mejor: tuple[str, str, DefinicionCombo] | None = None
        for ex in existentes.values():
            estado, detalle, _ = _comparar(req, ex)
            if estado == "coincide":
                mejor = (estado, detalle, ex)
                break
            if mejor is None or (mejor[0] == "no_verificable" and estado == "parcial"):
                mejor = (estado, detalle, ex)

        if mejor is None:
            resultados.append(VerificacionCombo(
                requerida=req,
                encontrada=None,
                estado="ausente",
                detalle="No existe ninguna combinación en ETABS.",
            ))
        else:
            estado, detalle, ex = mejor
            if estado != "coincide" and not ex.factores and estado != "no_verificable":
                estado = "ausente"
            resultados.append(VerificacionCombo(
                requerida=req,
                encontrada=ex.nombre if estado != "ausente" else None,
                estado=estado,
                detalle=detalle,
                factores_encontrados=ex.factores,
            ))
    return resultados


def leer_combos_diseno_concreto(sap) -> list[str]:
    """
    Lee las combinaciones usadas por el diseño de concreto de ETABS.

    La API expone ``DesignConcrete.GetComboStrength`` en las versiones
    modernas; si no está disponible se devuelve una lista vacía.
    """
    dc = getattr(sap, "DesignConcrete", None)
    if dc is None:
        return []
    for metodo in ("GetComboStrength", "GetComboStrength_1"):
        fn = getattr(dc, metodo, None)
        if fn is None:
            continue
        try:
            datos = sin_ret(fn())
            if not datos:
                continue
            if isinstance(datos[0], (list, tuple)):
                return [str(x) for x in datos[0]]
            if len(datos) > 1 and isinstance(datos[1], (list, tuple)):
                return [str(x) for x in datos[1]]
        except Exception:
            continue
    return []


# ---------------------------------------------------------------------------
# Creación de combinaciones faltantes
# ---------------------------------------------------------------------------
def crear_combinaciones(
    sap,
    requeridas: list[ComboRequerida],
    verificaciones: list[VerificacionCombo],
) -> dict[str, str]:
    """
    Crea en ETABS las combinaciones ausentes o parciales.

    Devuelve un diccionario ``{nombre_requerido: nombre_creado}``.  No borra ni
    modifica combinaciones existentes: si el nombre ya existe se agrega un
    sufijo.
    """
    try:
        bloqueado = bool(sap.GetModelIsLocked())
    except Exception:
        bloqueado = False
    if bloqueado:
        raise ETABSError(
            "El modelo está bloqueado (analysis locked). Desbloquéelo antes de "
            "crear combinaciones: SapModel.SetModelIsLocked(False)."
        )

    existentes = set(leer_combos_existentes(sap))
    creadas: dict[str, str] = {}

    for req, ver in zip(requeridas, verificaciones):
        if ver.estado == "coincide":
            continue
        nombre = req.nombre
        sufijo = 1
        while nombre in existentes:
            nombre = f"{req.nombre}_E060{sufijo if sufijo > 1 else ''}"
            sufijo += 1
        try:
            ret = ret_de(sap.RespCombo.Add(nombre, 0))
            if ret != 0:
                continue
            for caso, factor in req.factores:
                ret = ret_de(sap.RespCombo.SetCaseList(nombre, 0, caso, float(factor)))
                if ret != 0:
                    raise ETABSError(
                        f"No se pudo agregar el caso {caso!r} a {nombre!r} "
                        f"(código {ret}). Verifique que el caso exista."
                    )
            existentes.add(nombre)
            creadas[req.nombre] = nombre
        except ETABSError:
            raise
        except Exception as exc:
            raise ETABSError(f"Error creando {nombre!r}: {exc}") from exc

    return creadas


def mapas_combo_extraccion(
    requeridas: list[ComboRequerida],
    verificaciones: list[VerificacionCombo],
    creadas: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Devuelve ``{nombre_requerido: nombre_real_en_ETABS}`` para extraer fuerzas.

    Si una combinación no existe y no se creó, se omite y se informará en la
    memoria.
    """
    creadas = creadas or {}
    mapa: dict[str, str] = {}
    for req, ver in zip(requeridas, verificaciones):
        if ver.estado == "coincide" and ver.encontrada:
            mapa[req.nombre] = ver.encontrada
        elif req.nombre in creadas:
            mapa[req.nombre] = creadas[req.nombre]
        # Las combinaciones parciales NO se usan para extraer fuerzas: sus
        # casos o factores no coinciden con la E.060 y producirían resultados
        # de diseño incorrectos.
    return mapa


def combo_gravedad(requeridas: list[ComboRequerida]) -> ComboRequerida | None:
    for c in requeridas:
        if len([1 for _, f in c.factores if abs(f) > 1e-9]) == 2:
            return c
    return None


# ---------------------------------------------------------------------------
# Detección de casos de carga
# ---------------------------------------------------------------------------
def detectar_casos_carga(sap) -> CasosDetectados:
    """Detecta los casos D, L y S por nombre, permitiendo override por CLI."""
    try:
        nombres = [str(n) for n in lista(sap.LoadPatterns.GetNameList(), 1)]
    except Exception:
        nombres = []

    d = primer_coincidente(
        nombres, ("DEAD", "MUERTA", "PESO PROPIO", "PESOPROPIO", "CM", "D")
    )
    l = primer_coincidente(
        nombres, ("LIVE", "VIVA", "SOBRECARGA", "CV", "L")
    )
    s = [
        n for n in nombres
        if any(p in normalizar(n) for p in ("SISMO", "SISM", "SEISM", "ESPECTRO", "EQ", "SX", "SY", "CS"))
    ]
    advertencias: list[str] = []
    if not d:
        advertencias.append("No se detectó el caso de carga muerta.")
    if not l:
        advertencias.append("No se detectó el caso de carga viva.")
    if not s:
        advertencias.append(
            "No se detectó un caso sísmico; se generará solo la combinación "
            "de gravedad 1.4D + 1.7L."
        )
    return CasosDetectados(muerta=d, viva=l, sismo=s, todos=nombres, advertencias=advertencias)


def resumen_verificacion(verificaciones: list[VerificacionCombo]) -> dict[str, int]:
    resumen = {"coincide": 0, "parcial": 0, "ausente": 0, "no_verificable": 0}
    for v in verificaciones:
        resumen[v.estado] = resumen.get(v.estado, 0) + 1
    return resumen
