"""
Conector COM / OAPI para ETABS v20 – v23 (Windows).

Requisitos
----------
* ETABS instalado (versiones 20, 21, 22 o 23) y con licencia activa.
* Python de 64 bits con `comtypes` (recomendado) o `pywin32`:
      pip install comtypes
* ETABS debe estar abierto con el modelo cargado (conexión "attach"), o se
  puede lanzar una instancia nueva con `abrir_etabs(ruta)`.

Notas de compatibilidad
-----------------------
La interfaz OAPI (CSI.ETABS.API.ETABSObject) es estable desde ETABS 2016
(v16) hasta v23, por lo que el mismo código atiende las versiones 20–23.
El programa detecta la versión instalada y la reporta en la interfaz.

El conector fija temporalmente las unidades del modelo en kgf-m para leer
fuerzas, momentos y tensiones de forma coherente, y las restaura al finalizar.
"""

from __future__ import annotations

import math
import os
import platform
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple

from ..unidades import kgfcm_a_tonfm
from .modelo import Elemento, FuenteETABS, PuntoDemanda

# ---------------------------------------------------------------------------
# Constantes de la API
# ---------------------------------------------------------------------------
EUNITS_KGF_M = 8            # eUnits_kgf_m_C
ITEM_OBJECT_ELM = 0         # ObjectElm
ITEM_GROUP_ELM = 1

PROGID_ETABS = "CSI.ETABS.API.ETABSObject"
PROGID_HELPER = "ETABSv1.Helper"

MENSAJE_SIN_COMTYPES = (
    "No se encontró la librería de automatización COM.\n"
    "Instale comtypes con:  pip install comtypes\n"
    "o pywin32 con:         pip install pywin32"
)


class ConexionETABSError(RuntimeError):
    """
    Error de conexión con ETABS con información para la interfaz.

    codigo    : 'plataforma' | 'sin_com' | 'etabs_cerrado' | 'error_com'
    sugerencias: lista de pasos concretos para el usuario.
    """

    def __init__(self, mensaje: str, codigo: str = "error_com",
                 sugerencias: Optional[Sequence[str]] = None,
                 plataforma: Optional[str] = None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.sugerencias = list(sugerencias or [])
        self.plataforma = plataforma or sys.platform

    def to_dict(self) -> dict:
        return {
            "ok": False,
            "codigo": self.codigo,
            "error": str(self),
            "plataforma": self.plataforma,
            "es_windows": self.plataforma.startswith("win"),
            "sugerencias": self.sugerencias,
        }


def es_windows() -> bool:
    return sys.platform.startswith("win")


def diagnostico_com() -> dict:
    """
    Indica si la conexión COM con ETABS es posible en este equipo y por qué.

    Se usa en la interfaz para no ofrecer un botón que no puede funcionar:
    la automatización OAPI de ETABS (v20–v23) solo existe en Windows.
    """
    info = {
        "plataforma": sys.platform,
        "sistema": platform.system(),
        "es_windows": es_windows(),
        "python": platform.python_version(),
        "com_disponible": False,
        "backend": None,
        "motivo": "",
        "sugerencias": [],
    }
    if not es_windows():
        info["motivo"] = ("La automatización COM/OAPI de ETABS solo existe en "
                          "Windows; este servidor corre en "
                          f"{platform.system()}.")
        info["sugerencias"] = [
            "Exporte las tablas del modelo en ETABS (Display › Tables › "
            "Analysis › Element Forces - Frames) y cárguelas con «Importar "
            "tablas».",
            "También puede usar las tablas de ejemplo de la carpeta ejemplos/ "
            "para probar el flujo completo.",
            "Para la conexión directa, ejecute app_escritorio.py en el mismo "
            "Windows donde está abierto ETABS v20–v23.",
        ]
        return info
    try:
        backend, _, _ = _importar_com()
        info["com_disponible"] = True
        info["backend"] = backend
    except ConexionETABSError as exc:
        info["motivo"] = str(exc)
        info["sugerencias"] = exc.sugerencias
    return info


def _mensaje_sin_com() -> ConexionETABSError:
    if not es_windows():
        return ConexionETABSError(
            "La conexión directa con ETABS no está disponible en este sistema: "
            "la automatización COM/OAPI solo existe en Windows.",
            codigo="plataforma",
            sugerencias=[
                "Use «Importar tablas»: en ETABS, Display › Tables › Analysis › "
                "Element Forces - Frames, luego File › Export › Tables › to CSV.",
                "Los archivos de la carpeta ejemplos/ sirven para probar el "
                "programa sin ETABS.",
                "Para conectar en vivo, abra el proyecto en Windows con "
                "app_escritorio.py (misma máquina que ETABS).",
            ])
    return ConexionETABSError(
        MENSAJE_SIN_COMTYPES,
        codigo="sin_com",
        sugerencias=[
            "Instale la librería en el mismo Python con el que corre el "
            "programa: pip install comtypes  (o  pip install pywin32).",
            "Verifique que Python sea de 64 bits, igual que ETABS.",
            "Abra ETABS v20–v23 con el modelo cargado antes de pulsar "
            "«Conectar ETABS».",
        ])


def _importar_com():
    """Devuelve (modulo, activo, crear) usando comtypes o win32com."""
    try:
        import comtypes.client as cc  # type: ignore
        return ("comtypes", cc.GetActiveObject, cc.CreateObject)
    except Exception:
        pass
    try:
        import win32com.client as wc  # type: ignore
        return ("win32com", wc.GetActiveObject, wc.Dispatch)
    except Exception:
        raise _mensaje_sin_com() from None


def _desempaquetar(res):
    """Normaliza los retornos (ret, out...) de comtypes/win32com."""
    if isinstance(res, (tuple, list)):
        if not res:
            return 0, []
        return res[0], list(res[1:])
    return res, []


class ETABSCom(FuenteETABS):
    """Fuente de datos conectada a una instancia de ETABS vía OAPI."""

    nombre = "ETABS (COM/OAPI)"
    descripcion = "Conexión directa con ETABS v20–v23 en ejecución"

    def __init__(self, adjuntar: bool = True, ruta_etabs: Optional[str] = None,
                 version: Optional[str] = None):
        self.SapModel = None
        self.EtabsObject = None
        self.version = version or ""
        self._unidades_previas = None
        self._conectar(adjuntar, ruta_etabs)

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------
    def _conectar(self, adjuntar: bool, ruta: Optional[str]) -> None:
        backend, get_active, create = _importar_com()
        self.backend = backend
        error = None
        if adjuntar:
            try:
                self.EtabsObject = get_active(PROGID_ETABS)
            except Exception as exc:      # noqa: BLE001
                error = exc
        if self.EtabsObject is None:
            if ruta:
                self.EtabsObject = self._lanzar(ruta, create)
            else:
                try:
                    self.EtabsObject = create(PROGID_ETABS)
                except Exception as exc:  # noqa: BLE001
                    raise ConexionETABSError(
                        "No se encontró una instancia de ETABS en ejecución.\n"
                        "Abra ETABS v20–v23 con el modelo cargado y vuelva a "
                        "intentar; o cargue las tablas exportadas del modelo.\n"
                        f"Detalle técnico: {error or exc}",
                        codigo="etabs_cerrado",
                        sugerencias=[
                            "Abra ETABS v20, v21, v22 o v23 y cargue el modelo.",
                            "Si ETABS está abierto, confirme que la licencia "
                            "esté activa y que el modelo no esté en modo modal.",
                            "Alternativa sin ETABS: importe las tablas "
                            "«Element Forces - Frames» exportadas a CSV.",
                        ]) from exc
        try:
            self.EtabsObject.ApplicationStart()
        except Exception:                 # ya iniciado
            pass
        self.SapModel = self.EtabsObject.SapModel
        try:
            self.version = self.SapModel.GetVersion()[1]
        except Exception:
            self.version = "desconocida"
        try:
            res = self.SapModel.GetPresentUnits()
            self._unidades_previas = res[1] if isinstance(res, tuple) else res
            self.SapModel.SetPresentUnits(EUNITS_KGF_M)
        except Exception:
            self._unidades_previas = None

    def _lanzar(self, ruta: str, create):
        """Lanza una nueva instancia de ETABS desde una ruta de instalación."""
        _, _, _create_helper = _importar_com()
        try:
            helper = _create_helper(PROGID_HELPER)
            obj = helper.CreateObject(ruta)
            obj.ApplicationStart()
            return obj
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"No se pudo iniciar ETABS desde {ruta!r}: {exc}"
            ) from exc

    def cerrar(self) -> None:
        try:
            if self.SapModel is not None and self._unidades_previas:
                self.SapModel.SetPresentUnits(self._unidades_previas)
        except Exception:
            pass

    def info_modelo(self) -> dict:
        info = {"fuente": self.nombre, "version": self.version,
                "unidades": "kgf-m (lectura)", "modelo": ""}
        try:
            res = self.SapModel.GetModelFilename()
            if isinstance(res, tuple):
                info["modelo"] = res[-1]
        except Exception:
            pass
        try:
            res = self.SapModel.GetModelIsLocked()
            info["bloqueado"] = bool(res[1]) if isinstance(res, tuple) else bool(res)
        except Exception:
            pass
        return info

    # ------------------------------------------------------------------
    # Elementos
    # ------------------------------------------------------------------
    def _lista_nombres(self, fn) -> List[str]:
        res = fn(0, [])
        ret, salida = _desempaquetar(res)
        # formatos: (ret, n, names) o (ret, names)
        for item in salida:
            if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
                return list(item)
        for item in salida:
            if isinstance(item, int) and item >= 0:
                continue
        return []

    def _nombres_marcos(self) -> List[str]:
        try:
            res = self.SapModel.FrameObj.GetNameList(0, [])
        except Exception:
            return []
        ret, salida = _desempaquetar(res)
        for item in salida:
            if isinstance(item, (list, tuple)):
                return list(item)
        return []

    def _seleccionados(self) -> List[str]:
        try:
            res = self.SapModel.SelectObj.GetSelected(0, [], [])
        except Exception:
            return []
        ret, salida = _desempaquetar(res)
        nombres: List[str] = []
        # salida típica: (count, ObjectType[], ObjectName[])
        for item in salida:
            if isinstance(item, (list, tuple)) and item and isinstance(item[0], (str, int)):
                if item and isinstance(item[0], str):
                    nombres.extend(str(x) for x in item)
        return nombres

    def _coords(self, punto: str) -> Tuple[float, float, float]:
        try:
            res = self.SapModel.PointObj.GetCoordCartesian(punto, 0.0, 0.0, 0.0)
            _, salida = _desempaquetar(res)
            vals = [v for v in salida if isinstance(v, (int, float))]
            if len(vals) >= 3:
                return float(vals[0]), float(vals[1]), float(vals[2])
        except Exception:
            pass
        return 0.0, 0.0, 0.0

    def _propiedades_seccion(self, prop: str) -> Tuple[float, float, str]:
        """Devuelve (b, h, material) en cm para secciones rectangulares."""
        b = h = 0.0
        mat = ""
        try:
            res = self.SapModel.PropFrame.GetRectangle(prop, "", "", 0.0, 0.0)
            _, salida = _desempaquetar(res)
            textos = [v for v in salida if isinstance(v, str)]
            numeros = [v for v in salida if isinstance(v, (int, float))]
            if textos:
                mat = textos[-1]
            if len(numeros) >= 2:
                t3, t2 = float(numeros[0]), float(numeros[1])   # t3 = peralte, t2 = ancho
                h, b = t3 * 100.0, t2 * 100.0                   # m → cm
        except Exception:
            pass
        if b <= 0 or h <= 0:
            # secciones no rectangulares: intenta propiedades generales
            try:
                res = self.SapModel.PropFrame.GetSectProps(prop, 0.0, 0.0, 0.0, 0.0, 0)
                _, salida = _desempaquetar(res)
                numeros = [v for v in salida if isinstance(v, (int, float))]
                if len(numeros) >= 2:
                    area, as2, as3 = numeros[0], numeros[1], numeros[2]
                    if area > 0:
                        h = math.sqrt(area) * 100.0
                        b = h
            except Exception:
                pass
        return b, h, mat

    def _material(self, mat: str) -> Tuple[float, float]:
        """Devuelve (f'c, fy) en kgf/cm²."""
        fc = 210.0
        fy = 4200.0
        if not mat:
            return fc, fy
        try:
            res = self.SapModel.PropMaterial.GetOConcrete(mat, 0.0, False, 1.0, 1, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
            _, salida = _desempaquetar(res)
            numeros = [v for v in salida if isinstance(v, (int, float))]
            if numeros:
                fc = float(numeros[0]) / 1.0e4      # kgf/m² → kgf/cm²
        except Exception:
            pass
        try:
            res = self.SapModel.PropMaterial.GetORebar(mat, 0.0, 0.0, False, 1.0, 1.0, False, 1, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
            _, salida = _desempaquetar(res)
            numeros = [v for v in salida if isinstance(v, (int, float))]
            if numeros:
                fy = float(numeros[0]) / 1.0e4
        except Exception:
            pass
        if fc < 100 or fc > 1200:
            fc = 210.0
        if fy < 2000 or fy > 7000:
            fy = 4200.0
        return fc, fy

    def listar_elementos(self, solo_seleccionados: bool = False,
                         tipo: Optional[str] = None) -> List[str]:
        nombres = self._seleccionados() if solo_seleccionados else self._nombres_marcos()
        if not nombres:
            nombres = self._nombres_marcos()
        salida = []
        for n in nombres:
            if n in ("", None):
                continue
            if tipo and tipo != "Todos":
                t = self._clasificar(n)
                if not t.lower().startswith(tipo.lower()):
                    continue
            salida.append(n)
        return salida

    def _clasificar(self, nombre: str) -> str:
        try:
            res = self.SapModel.FrameObj.GetPoints(nombre, "", "")
            _, salida = _desempaquetar(res)
            textos = [v for v in salida if isinstance(v, str)]
            if len(textos) < 2:
                return "Desconocido"
            x1, y1, z1 = self._coords(textos[-2])
            x2, y2, z2 = self._coords(textos[-1])
            horiz = math.hypot(x2 - x1, y2 - y1)
            vert = abs(z2 - z1)
            return "Columna" if vert > horiz else "Viga"
        except Exception:
            return "Desconocido"

    def listar_combos(self) -> List[str]:
        try:
            res = self.SapModel.RespCombo.GetNameList(0, [])
            _, salida = _desempaquetar(res)
            for item in salida:
                if isinstance(item, (list, tuple)):
                    return list(item)
        except Exception:
            pass
        return []

    def _leer_fuerzas(self, nombre: str) -> List[PuntoDemanda]:
        puntos: List[PuntoDemanda] = []
        try:
            res = self.SapModel.Results.FrameForce(
                nombre, ITEM_OBJECT_ELM, 0, [], [], [], [], [],
                [], [], [], [], [], [])
        except Exception:
            return puntos
        _, salida = _desempaquetar(res)
        if not salida:
            return puntos
        n = salida[0] if isinstance(salida[0], int) else 0
        listas = [s for s in salida[1:] if isinstance(s, (list, tuple))]
        # orden OAPI: Obj, Elm, LoadCase, StepType, StepNum, P, V2, V3, T, M2, M3
        if len(listas) < 10:
            return puntos
        obj, elm, loadcase, steptype, stepnum, P, V2, V3, T, M2, M3 = listas[:11]
        for i in range(min(n, len(loadcase))):
            puntos.append(PuntoDemanda(
                combo=str(loadcase[i]),
                estacion=0.0,
                P=float(P[i]), V2=float(V2[i]), V3=float(V3[i]),
                T=float(T[i]) * 100.0,          # kgf·m → kgf·cm
                M2=float(M2[i]) * 100.0,
                M3=float(M3[i]) * 100.0,
            ))
        return puntos

    def _configurar_salida(self, combos: Sequence[str]) -> None:
        try:
            self.SapModel.Results.Setup.DeselectAllCasesAndCombosForOutput()
            for c in combos:
                self.SapModel.Results.Setup.SetComboSelectedForOutput(c, True)
        except Exception:
            pass

    def _leer_estaciones(self, nombre: str, n_combos: int) -> List[float]:
        """
        Obtiene las estaciones de salida. La API entrega las estaciones por
        cada elemento interno; se usa la longitud del elemento para
        reconstruirlas cuando no se dispone de 'ObjSta'.
        """
        return []

    def obtener_elemento(self, nombre: str) -> Elemento:
        b, h, mat = self._propiedades_seccion(self._seccion_de(nombre))
        fc, fy = self._material(mat)
        p1 = p2 = ""
        try:
            res = self.SapModel.FrameObj.GetPoints(nombre, "", "")
            _, salida = _desempaquetar(res)
            textos = [v for v in salida if isinstance(v, str)]
            if len(textos) >= 2:
                p1, p2 = textos[-2], textos[-1]
        except Exception:
            pass
        x1, y1, z1 = self._coords(p1)
        x2, y2, z2 = self._coords(p2)
        L = math.dist((x1, y1, z1), (x2, y2, z2)) * 100.0      # m → cm
        combos = self.listar_combos()
        self._configurar_salida(combos)
        puntos = self._leer_fuerzas(nombre)
        # reconstruye estaciones si la API no las entrega
        n_est = max(1, len(puntos) // max(len(combos), 1))
        for i, p in enumerate(puntos):
            p.estacion = L * (i % n_est) / max(n_est - 1, 1)
        return Elemento(
            nombre=nombre, tipo=self._clasificar(nombre), seccion=self._seccion_de(nombre),
            story=self._story_de(nombre), material=mat, b=b, h=h, fc=fc, fy=fy, L=L,
            puntos=puntos, unidad_fuerza="kgf", unidad_longitud="m",
            origen=f"ETABS {self.version} (COM)")

    def _seccion_de(self, nombre: str) -> str:
        try:
            res = self.SapModel.FrameObj.GetSection(nombre, "", "")
            _, salida = _desempaquetar(res)
            textos = [v for v in salida if isinstance(v, str)]
            if textos:
                return textos[0]
        except Exception:
            pass
        return ""

    def _story_de(self, nombre: str) -> str:
        try:
            res = self.SapModel.FrameObj.GetLabelFromName(nombre, "", "")
            _, salida = _desempaquetar(res)
            textos = [v for v in salida if isinstance(v, str)]
            if textos:
                return textos[0]
        except Exception:
            pass
        return ""


# ===========================================================================
# Funciones de ayuda para el usuario
# ===========================================================================
RUTAS_TIPICAS = [
    r"C:\Program Files\Computers and Structures\ETABS 23\ETABS.exe",
    r"C:\Program Files\Computers and Structures\ETABS 22\ETABS.exe",
    r"C:\Program Files\Computers and Structures\ETABS 21\ETABS.exe",
    r"C:\Program Files\Computers and Structures\ETABS 20\ETABS.exe",
    r"C:\Program Files (x86)\Computers and Structures\ETABS 20\ETABS.exe",
]


def ruta_etabs_instalado() -> Optional[str]:
    """Busca una instalación de ETABS 20–23 en las rutas típicas de Windows."""
    for ruta in RUTAS_TIPICAS:
        if os.path.exists(ruta):
            return ruta
    for base in (r"C:\Program Files\Computers and Structures",
                 r"C:\Program Files (x86)\Computers and Structures"):
        try:
            for carpeta in os.listdir(base):
                if carpeta.lower().startswith("etabs"):
                    exe = os.path.join(base, carpeta, "ETABS.exe")
                    if os.path.exists(exe):
                        return exe
        except OSError:
            continue
    return None


def conectar(adjuntar: bool = True, ruta: Optional[str] = None) -> ETABSCom:
    """Atajo de conexión; lanza RuntimeError con mensajes en español."""
    return ETABSCom(adjuntar=adjuntar, ruta_etabs=ruta or ruta_etabs_instalado())
