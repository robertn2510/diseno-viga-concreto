"""
Conexión a ETABS v18–v23 mediante COM (comtypes o pywin32).

La API de ETABS es la misma familia ``ETABSv1`` desde ETABS 2016 (v16).  Las
versiones v18 a v23 comparten:

* ProgID del objeto: ``CSI.ETABS.API.ETABSObject``
* Helper: ``ETABSv1.Helper``
* Interfaz de modelo: ``EtabsObject.SapModel`` (cSapModel)

El método ``get_oapi()`` de esta clase encapsula las estrategias oficiales de
obtención del objeto OAPI, equivalentes a la llamada VBA:

    Set myETABSObject = GetObject(, "CSI.ETABS.API.ETABSObject")

o, con el helper:

    Set myETABSObject = myHelper.GetObject("CSI.ETABS.API.ETABSObject")

No se fuerza la creación de una instancia nueva salvo que se solicite
explícitamente (``modo='crear'``), para no abrir ETABS por accidente ni
bloquear licencias.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from ..unidades import UNIDADES_ETABS, UnidadesETABS
from .api import ETABSError, escalar, ret_de, sin_ret

PROGIDS_ETABS = (
    "CSI.ETABS.API.ETABSObject",
    "ETABSv1.ETABSObject",
    "ETABS2016.ETABSObject",
    "ETABS2015.ETABSObject",
    "ETABS2013.ETABSObject",
    "ETABSv9.ETABSObject",
)
HELPER_PROGID = "ETABSv1.Helper"
UNIDAD_TRABAJO = 8  # kgf_m


@dataclass
class InfoConexion:
    version: str = "desconocida"
    version_mayor: int | None = None
    modelo: str = ""
    ruta_modelo: str = ""
    unidades_originales: int | None = None
    unidad_trabajo: UnidadesETABS = UNIDADES_ETABS[UNIDAD_TRABAJO]
    api: str = ""
    bloqueado: bool | None = None
    propia_instancia: bool = False
    advertencias: list[str] = field(default_factory=list)


class ConexionETABS:
    """Envoltorio de una sesión COM de ETABS."""

    def __init__(
        self,
        etabs_object: Any,
        sap_model: Any,
        info: InfoConexion,
        cerrar_al_salir: bool = False,
    ) -> None:
        self.etabs_object = etabs_object
        self.sap_model = sap_model
        self.info = info
        self.cerrar_al_salir = cerrar_al_salir
        self._unidades_restauradas = False

    # ------------------------------------------------------------------
    # Objeto OAPI
    # ------------------------------------------------------------------
    def get_oapi(self) -> Any:
        """
        Devuelve el objeto OAPI de ETABS (``cOAPI``).

        Es el equivalente de ``GetObject(, "CSI.ETABS.API.ETABSObject")`` o
        ``helper.GetObject(...)``.  Se conserva el nombre ``get_oapi`` porque
        es el utilizado en la práctica para referirse a la obtención del
        objeto de automatización.
        """
        return self.etabs_object

    @property
    def unidades(self) -> UnidadesETABS:
        return self.info.unidad_trabajo

    # ------------------------------------------------------------------
    # Conversión de unidades
    # ------------------------------------------------------------------
    def a_m(self, valor: float) -> float:
        return self.unidades.a_metros(valor)

    def a_kgf(self, valor: float) -> float:
        return self.unidades.a_kgf(valor)

    def a_t(self, valor: float) -> float:
        return self.unidades.a_kgf(valor) / 1_000.0

    def a_tm(self, valor: float) -> float:
        return self.unidades.a_tonfm(valor)

    def a_kgcm2(self, valor: float) -> float:
        """Convierte un esfuerzo de las unidades presentes a kgf/cm²."""
        u = self.unidades
        return float(valor) * u.fuerza_kgf / ((u.longitud_m * 100.0) ** 2)

    # ------------------------------------------------------------------
    # Unidades y cierre
    # ------------------------------------------------------------------
    def fijar_unidades_trabajo(self) -> None:
        """Fija kgf_m y conserva el código original para restaurarlo."""
        sap = self.sap_model
        try:
            original = escalar(sap.GetPresentUnits())
            self.info.unidades_originales = int(original)
        except Exception:
            self.info.unidades_originales = None
        try:
            codigo = ret_de(sap.SetPresentUnits(UNIDAD_TRABAJO))
            if codigo != 0:
                raise ETABSError(f"SetPresentUnits devolvió el código {codigo}.")
            self.info.unidad_trabajo = UNIDADES_ETABS[UNIDAD_TRABAJO]
        except Exception as exc:
            # Si no se puede cambiar, se trabaja con la unidad actual, pero
            # solo si se conoce con certeza; de lo contrario se aborta para no
            # entregar fuerzas con unidades equivocadas.
            codigo = self.info.unidades_originales
            if codigo is None or codigo not in UNIDADES_ETABS:
                raise ETABSError(
                    "No se pudo fijar kgf_m en ETABS y tampoco se pudo leer la "
                    f"unidad presente ({exc}). Verifique la conexión y las "
                    "unidades del modelo antes de continuar."
                ) from exc
            self.info.unidad_trabajo = UNIDADES_ETABS[codigo]
            self.info.advertencias.append(
                f"No se pudo fijar kgf_m en ETABS ({exc}); se usan las unidades "
                f"presentes ({self.info.unidad_trabajo.nombre}) y se convierten "
                "los resultados."
            )

    def restaurar_unidades(self) -> None:
        if self._unidades_restauradas:
            return
        codigo = self.info.unidades_originales
        if codigo is not None:
            try:
                self.sap_model.SetPresentUnits(int(codigo))
            except Exception:
                pass
        self._unidades_restauradas = True

    def cerrar(self) -> None:
        self.restaurar_unidades()
        if self.cerrar_al_salir and self.info.propia_instancia:
            try:
                self.etabs_object.ApplicationExit(False)
            except Exception:
                pass

    def __enter__(self) -> "ConexionETABS":
        return self

    def __exit__(self, *args: Any) -> None:
        self.cerrar()

    # ------------------------------------------------------------------
    # Información del modelo
    # ------------------------------------------------------------------
    def leer_info(self) -> None:
        sap = self.sap_model
        for metodo in ("GetVersion", "GetProgramVersion"):
            fn = getattr(sap, metodo, None)
            if fn is None:
                continue
            try:
                datos = sin_ret(fn())
                if datos:
                    self.info.version = str(datos[0])
                    m = re.search(r"(\d+)", self.info.version)
                    if m:
                        self.info.version_mayor = int(m.group(1))
                    break
            except Exception:
                continue

        try:
            self.info.modelo = str(escalar(sap.GetModelFilename()) or "")
        except Exception:
            pass
        try:
            self.info.ruta_modelo = str(escalar(sap.GetModelFilepath()) or "")
        except Exception:
            pass
        try:
            self.info.bloqueado = bool(sap.GetModelIsLocked())
        except Exception:
            self.info.bloqueado = None

        if self.info.version_mayor is not None and not (18 <= self.info.version_mayor <= 23):
            self.info.advertencias.append(
                f"ETABS {self.info.version} está fuera del rango declarado v18–v23; "
                "se intentará usar la API ETABSv1 compatible."
            )


# ---------------------------------------------------------------------------
# Estrategias de conexión
# ---------------------------------------------------------------------------
def _importar_comtypes():
    try:
        import comtypes.client  # type: ignore
        return comtypes.client
    except Exception as exc:  # pragma: no cover - sólo Windows
        raise ETABSError(
            "No se pudo importar comtypes. En Windows ejecute: "
            "pip install comtypes. Si está en Linux/macOS use --demo."
        ) from exc


def _importar_pywin32():
    try:
        import win32com.client  # type: ignore
        return win32com.client
    except Exception as exc:  # pragma: no cover - sólo Windows
        raise ETABSError(
            "No se pudo importar pywin32. En Windows ejecute: "
            "pip install pywin32. Si está en Linux/macOS use --demo."
        ) from exc


def _progids() -> list[str]:
    personalizado = os.environ.get("ETABS_PROGID", "").strip()
    return ([personalizado] if personalizado else []) + list(PROGIDS_ETABS)


def _query_oapi(obj):
    """Intenta convertir el objeto COM a la interfaz cOAPI de ETABSv1."""
    try:
        import comtypes.gen.ETABSv1 as etabs_gen  # type: ignore

        return obj.QueryInterface(etabs_gen.cOAPI)
    except Exception:
        return obj


def _conectar_comtypes(modo: str, ruta_etabs: str | None):
    cc = _importar_comtypes()
    errores: list[str] = []

    # 1. Instancia activa (equivalente a GetObject).
    if modo != "crear":
        for progid in _progids():
            try:
                obj = _query_oapi(cc.GetActiveObject(progid))
                return obj, "comtypes.GetActiveObject"
            except Exception as exc:
                errores.append(f"GetActiveObject({progid}): {exc}")

    # 2. Helper ETABSv1 (recomendado por CSI desde v16).
    try:
        helper = cc.CreateObject(HELPER_PROGID)
        try:
            import comtypes.gen.ETABSv1 as etabs_gen  # type: ignore
            helper = helper.QueryInterface(etabs_gen.cHelper)
        except Exception:
            pass
        if modo != "crear":
            for progid in _progids():
                try:
                    obj = _query_oapi(helper.GetObject(progid))
                    return obj, "comtypes.helper.GetObject"
                except Exception as exc:
                    errores.append(f"helper.GetObject({progid}): {exc}")
        if modo == "crear":
            try:
                if ruta_etabs:
                    obj = helper.CreateObject(ruta_etabs)
                else:
                    obj = helper.CreateObjectProgID("CSI.ETABS.API.ETABSObject")
                obj.ApplicationStart()
                return _query_oapi(obj), "comtypes.helper.CreateObject"
            except Exception as exc:
                errores.append(f"helper.CreateObject: {exc}")
    except Exception as exc:
        errores.append(f"CreateObject({HELPER_PROGID}): {exc}")

    # 3. Creación directa del ProgID.
    if modo == "crear":
        for progid in _progids():
            try:
                obj = cc.CreateObject(progid)
                obj.ApplicationStart()
                return _query_oapi(obj), "comtypes.CreateObject"
            except Exception as exc:
                errores.append(f"CreateObject({progid}): {exc}")

    detalle = "\n".join(f"  - {e}" for e in errores[-8:])
    raise ETABSError(
        "No se pudo conectar con una instancia de ETABS.\n"
        "Verifique que ETABS esté abierto, con un modelo cargado y la licencia activa.\n"
        f"Intentos:\n{detalle}"
    )


def _conectar_pywin32(modo: str, ruta_etabs: str | None):
    wc = _importar_pywin32()
    errores: list[str] = []

    if modo != "crear":
        for progid in _progids():
            try:
                obj = wc.GetActiveObject(progid)
                return obj, "pywin32.GetActiveObject"
            except Exception as exc:
                errores.append(f"GetActiveObject({progid}): {exc}")

    try:
        helper = wc.Dispatch(HELPER_PROGID)
        if modo != "crear":
            for progid in _progids():
                try:
                    obj = helper.GetObject(progid)
                    return obj, "pywin32.helper.GetObject"
                except Exception as exc:
                    errores.append(f"helper.GetObject({progid}): {exc}")
        if modo == "crear":
            try:
                obj = (
                    helper.CreateObject(ruta_etabs)
                    if ruta_etabs
                    else helper.CreateObjectProgID("CSI.ETABS.API.ETABSObject")
                )
                obj.ApplicationStart()
                return obj, "pywin32.helper.CreateObject"
            except Exception as exc:
                errores.append(f"helper.CreateObject: {exc}")
    except Exception as exc:
        errores.append(f"Dispatch({HELPER_PROGID}): {exc}")

    if modo == "crear":
        for progid in _progids():
            try:
                obj = wc.Dispatch(progid)
                obj.ApplicationStart()
                return obj, "pywin32.Dispatch"
            except Exception as exc:
                errores.append(f"Dispatch({progid}): {exc}")

    detalle = "\n".join(f"  - {e}" for e in errores[-8:])
    raise ETABSError(
        "No se pudo conectar con ETABS mediante pywin32.\n"
        f"Intentos:\n{detalle}"
    )


def conectar_etabs(
    modo: str = "adjuntar",
    ruta_etabs: str | None = None,
    usar_pywin32: bool = False,
    abrir_modelo: str | None = None,
    cerrar_al_salir: bool = False,
    fijar_unidades: bool = True,
) -> ConexionETABS:
    """
    Conecta con ETABS v18–v23 y devuelve una :class:`ConexionETABS`.

    Parámetros
    ----------
    modo:
        ``"adjuntar"`` (instancia abierta) o ``"crear"`` (nueva instancia).
    ruta_etabs:
        Ruta del ejecutable ``ETABS.exe`` cuando ``modo='crear'``.
    usar_pywin32:
        Fuerza el uso de pywin32 en lugar de comtypes.
    abrir_modelo:
        Ruta del archivo ``.edb`` a abrir después de conectar.
    cerrar_al_salir:
        Si se creó una instancia propia, cerrarla al salir del contexto.
    """
    if modo not in {"adjuntar", "crear"}:
        raise ValueError("modo debe ser 'adjuntar' o 'crear'.")

    propia = modo == "crear"
    if usar_pywin32:
        obj, api = _conectar_pywin32(modo, ruta_etabs)
    else:
        obj, api = _conectar_comtypes(modo, ruta_etabs)

    try:
        sap = obj.SapModel
    except Exception as exc:
        raise ETABSError(
            "El objeto ETABS no expone SapModel. Verifique la versión y el "
            "registro COM de ETABS."
        ) from exc

    info = InfoConexion(api=api, propia_instancia=propia)
    conexion = ConexionETABS(obj, sap, info, cerrar_al_salir=cerrar_al_salir)
    conexion.leer_info()

    if abrir_modelo:
        try:
            ret = sap.File.OpenFile(os.path.abspath(abrir_modelo))
            codigo = ret_de(ret)
            if codigo != 0:
                raise ETABSError(f"File.OpenFile devolvió el código {codigo}.")
        except Exception as exc:
            raise ETABSError(f"No se pudo abrir el modelo {abrir_modelo!r}: {exc}") from exc
        conexion.leer_info()

    if fijar_unidades:
        conexion.fijar_unidades_trabajo()

    return conexion
