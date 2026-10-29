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
import threading
import time
from typing import Dict, List, Optional, Sequence, Tuple

from ..unidades import kgfcm_a_tonfm, sistema_unidades
from .modelo import Elemento, FuenteETABS, PuntoDemanda
from .tablas import ETABSTablas, Tabla

# ---------------------------------------------------------------------------
# Constantes de la API
# ---------------------------------------------------------------------------
EUNITS_KGF_M = 8            # eUnits_kgf_m_C (kgf, m, °C)
ITEM_OBJECT_ELM = 0         # ObjectElm
ITEM_GROUP_ELM = 1

# eUnits de ETABS -> clave de sistema de unidades del motor
UNIDADES_POR_ENUM = {
    1: "lb_in_F", 2: "lb_ft_F", 3: "kip_in_F", 4: "kip_ft_F",
    5: "kN_mm_C", 6: "kN_m_C", 7: "kgf_mm_C", 8: "kgf_m_C",
    9: "N_mm_C", 10: "N_m_C", 11: "tonf_mm_C", 12: "tonf_m_C",
    13: "kN_cm_C", 14: "kgf_cm_C", 15: "N_cm_C", 16: "tonf_cm_C",
}

# Tablas de la base de datos de ETABS que necesita el motor
TABLA_FUERZAS = "Element Forces - Frames"
TABLAS_SECCIONES = ("Frame Assignments - Section Properties",
                    "Frame Section Properties - Rectangular",
                    "Frame Section Properties - Concrete Rectangular",
                    "Frame Properties - Rectangular")
TABLAS_MATERIALES = ("Material Properties - Concrete Data",
                     "Material Properties - Basic Mechanical Properties",
                     "Material List by Object Type")

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


def _asegurar_com_en_hilo() -> None:
    """
    Inicializa COM en el hilo actual.

    El servidor web atiende cada petición en un hilo nuevo
    (`ThreadingHTTPServer`) y COM exige `CoInitialize` por hilo; si se omite,
    la conexión falla con el error 0x800401F0 (CO_E_NOTINITIALIZED).
    """
    if not es_windows():
        return
    for modulo in ("comtypes", "pythoncom"):
        try:
            mod = __import__(modulo)
        except Exception:
            continue
        for funcion in ("CoInitialize", "CoInitializeEx"):
            inicializar = getattr(mod, funcion, None)
            if inicializar is None:
                continue
            try:
                inicializar()
                return
            except Exception:
                continue


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
                 version: Optional[str] = None, solo_seleccionados: bool = False):
        self.EtabsObject = None
        self.version = version or ""
        self._unidades_previas = None
        self._local = threading.local()
        self._modelo: Optional[ETABSTablas] = None
        self._solo_seleccionados = bool(solo_seleccionados)
        self.clave_unidades = "kgf_m_C"
        self._conectar(adjuntar, ruta_etabs)

    # ------------------------------------------------------------------
    # Acceso a COM desde varios hilos
    # ------------------------------------------------------------------
    @property
    def SapModel(self):
        """
        SapModel válido **para el hilo actual**.

        COM usa apartamentos por hilo: el servidor web atiende cada petición en
        un hilo distinto, por lo que un `SapModel` obtenido en otro hilo no debe
        reutilizarse. Si el hilo aún no tiene su propio objeto, se vuelve a
        enganchar a la misma instancia de ETABS (GetActiveObject) y se fijan las
        unidades de lectura.
        """
        sap = getattr(self._local, "sap", None)
        if sap is not None:
            return sap
        return self._sap_de_hilo()

    @SapModel.setter
    def SapModel(self, valor):
        self._local.sap = valor

    def _sap_de_hilo(self):
        """Engancha el hilo actual a la instancia de ETABS ya abierta."""
        _asegurar_com_en_hilo()
        try:
            obj = self.EtabsObject
            sap = obj.SapModel if obj is not None else None
        except Exception:
            sap = None
        if sap is None:
            _, get_active, _create = _importar_com()
            try:
                obj = get_active(PROGID_ETABS)
            except Exception as exc:                 # noqa: BLE001
                raise ConexionETABSError(
                    "Se perdió la conexión con ETABS (¿se cerró la aplicación?).\n"
                    f"Detalle técnico: {exc}",
                    codigo="etabs_cerrado", sugerencias=[
                        "Compruebe que ETABS siga abierto con el modelo cargado.",
                        "Vuelva a conectar desde la interfaz.",
                    ])
            self.EtabsObject = obj
            sap = obj.SapModel
        self._local.sap = sap
        try:                              # mismas unidades que en la conexión
            sap.SetPresentUnits(EUNITS_KGF_M)
        except Exception:
            pass
        return sap

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------
    def _conectar(self, adjuntar: bool, ruta: Optional[str]) -> None:
        _asegurar_com_en_hilo()
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
                # ruta explícita: se inicia ETABS a través del Helper de CSI
                self.EtabsObject = self._lanzar(ruta, create)
            else:
                # No se crea una instancia vacía: el usuario debe abrir el
                # modelo en ETABS (crear una instancia sin modelo solo abriría
                # la aplicación en blanco y confundiría el diagnóstico).
                raise ConexionETABSError(
                    "No se encontró una instancia de ETABS en ejecución.\n"
                    "Abra ETABS v20–v23, cargue el modelo y vuelva a intentar; "
                    "o importe las tablas exportadas del modelo.\n"
                    f"Detalle técnico: {error}",
                    codigo="etabs_cerrado",
                    sugerencias=[
                        "Abra ETABS v20, v21, v22 o v23 y cargue el modelo.",
                        "Verifique que la licencia esté activa y que el modelo "
                        "no esté bloqueado (Unlock Model).",
                        "Ejecute el análisis (Analyze > Run Analysis) para que "
                        "existan resultados que leer.",
                        "Alternativa sin ETABS: importe las tablas "
                        "«Element Forces - Frames» exportadas a CSV.",
                    ])
        try:
            self.EtabsObject.ApplicationStart()
        except Exception:                 # ya iniciado
            pass
        self.SapModel = self.EtabsObject.SapModel
        try:
            self.version = self.SapModel.GetVersion()[1]
        except Exception:
            self.version = "desconocida"
        # Unidades: se fija kgf-m para leer de forma coherente y se recuerda
        # el sistema previo para restituirlo al cerrar.
        try:
            res = self.SapModel.GetPresentUnits()
            valor = res[1] if isinstance(res, tuple) else res
            self._unidades_previas = int(valor)
        except Exception:
            self._unidades_previas = None
        try:
            self.SapModel.SetPresentUnits(EUNITS_KGF_M)
            self.clave_unidades = "kgf_m_C"
        except Exception:
            # si no se pudo fijar, se traduce el sistema en que esté el modelo
            self.clave_unidades = UNIDADES_POR_ENUM.get(
                self._unidades_previas or EUNITS_KGF_M, "kgf_m_C")

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
        """Restituye las unidades originales del modelo (no cierra ETABS)."""
        try:
            sap = getattr(self._local, "sap", None)
            if sap is not None and self._unidades_previas:
                self.SapModel.SetPresentUnits(self._unidades_previas)
        except Exception:
            pass

    @property
    def unidades(self):
        return sistema_unidades(self.clave_unidades)

    def info_modelo(self) -> dict:
        info = {"fuente": self.nombre, "version": self.version,
                "unidades": self.clave_unidades, "modelo": "",
                "backend": getattr(self, "backend", "")}
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
        if self._modelo is not None:
            info["elementos"] = len(self._modelo.listar_elementos())
            info["combos"] = len(self._modelo.listar_combos())
        return info

    # ------------------------------------------------------------------
    # Lectura de la base de datos del modelo
    # ------------------------------------------------------------------
    def _tablas_disponibles(self) -> List[str]:
        """Nombres de todas las tablas de la base de datos del modelo."""
        try:
            res = self.SapModel.DatabaseTables.GetAvailableTables(0, [], [])
        except Exception:
            return []
        _, salida = _desempaquetar(res)
        for item in salida:
            if isinstance(item, (list, tuple)):
                return [str(x) for x in item]
        return []

    def _tabla_como_datos(self, clave: str):
        """
        Devuelve (campos, filas) de una tabla de la base de datos.

        La firma del API ha sido estable desde ETABS v9, pero se prueban
        variantes por si la versión instalada espera otro número de argumentos.
        """
        intentos = (
            (clave, [], ""),
            (clave, [], "", "", ),
            (clave, [], "", True, True),
        )
        ultimo = None
        for extra in intentos:
            try:
                res = self.SapModel.DatabaseTables.GetTableForDisplayArray(*extra)
            except Exception as exc:          # noqa: BLE001
                ultimo = exc
                continue
            campos, filas = self._interpretar_tabla(res)
            if campos:
                return campos, filas
        if ultimo is not None:
            raise RuntimeError(f"No se pudo leer la tabla {clave!r}: {ultimo}")
        return [], []

    @staticmethod
    def _interpretar_tabla(res):
        """
        Normaliza la salida de GetTableForDisplayArray:

        (ret, TableVersion, FieldsKeysIncluded[], NumberRecords, TableData[])
        donde TableData es una lista plana de (NumberRecords × nCampos).
        """
        ret, salida = _desempaquetar(res)
        if ret not in (0, None) and not isinstance(ret, (tuple, list)):
            # algunos backends devuelven el código de error en el primer elemento
            pass
        campos: List[str] = []
        plano: List[str] = []
        n_registros = 0
        for item in salida:
            if isinstance(item, (list, tuple)):
                valores = [str(v) for v in item]
                if not campos and valores and all(not _a_numero(v) for v in valores):
                    campos = valores
                elif len(valores) > len(plano):
                    plano = valores
            elif isinstance(item, int) and item > 0:
                n_registros = max(n_registros, item)
        if not campos or not plano:
            return [], []
        ancho = len(campos)
        if n_registros and n_registros * ancho == len(plano):
            filas = [plano[i * ancho:(i + 1) * ancho]
                     for i in range(n_registros)]
        else:
            filas = [plano[i:i + ancho] for i in range(0, len(plano), ancho)]
            filas = [f for f in filas if len(f) == ancho]
        return campos, filas

    def _seleccion_actual(self) -> List[str]:
        """Nombres de las barras seleccionadas en ETABS (puede estar vacío)."""
        try:
            res = self.SapModel.SelectObj.GetSelected(0, [], [])
        except Exception:
            return []
        _, salida = _desempaquetar(res)
        listas = [list(x) for x in salida if isinstance(x, (list, tuple))]
        if len(listas) >= 2:
            nombres = [str(v) for v in listas[-1]]
        elif listas:
            nombres = [str(v) for v in listas[0]]
        else:
            nombres = []
        return [n for n in nombres if n and not _a_numero(n)]

    def obtener_modelo(self, solo_seleccionados: bool = False) -> ETABSTablas:
        """
        Construye el modelo importando las tablas de la base de datos de ETABS.

        Se emplea la base de datos (y no `Results.FrameForce`) porque incluye la
        **estación** de cada resultado: sin ella no se puede construir la
        envolvente de momentos a lo largo del elemento. Las tablas se procesan
        con el mismo código validado de la importación de CSV, de modo que la
        conexión en vivo y la importación de archivos dan resultados idénticos.
        """
        claves = self._tablas_disponibles()
        if not claves:
            raise ConexionETABSError(
                "ETABS no expone tablas de su base de datos. Verifique que el "
                "modelo esté abierto, desbloqueado y analizado.",
                codigo="sin_tablas", sugerencias=[
                    "Ejecute el análisis en ETABS (Analyze > Run Analysis).",
                    "Desbloquee el modelo (Unlock Model) si está bloqueado.",
                    "Alternativa: exporte las tablas a CSV e impórtelas.",
                ])

        def buscar(nombres_deseados):
            for deseo in nombres_deseados:
                d = deseo.lower()
                for clave in claves:
                    if clave.lower().startswith(d.lower()):
                        return clave
            return None

        clave_f = buscar([TABLA_FUERZAS, "Element Forces - Frames"])
        if clave_f is None:
            raise ConexionETABSError(
                "No se encontró la tabla «Element Forces - Frames» en ETABS. "
                "El modelo debe estar analizado.",
                codigo="sin_tablas", sugerencias=[
                    "Ejecute el análisis (Analyze > Run Analysis) y reintente.",
                    "Compruebe que el caso de carga tenga resultados.",
                ])
        campos, filas = self._tabla_como_datos(clave_f)
        if not campos:
            raise ConexionETABSError(
                "La tabla de fuerzas está vacía. Ejecute el análisis en ETABS.",
                codigo="sin_tablas")
        tablas_f = [Tabla(clave_f, [campos] + filas)]

        tablas_s: List[Tabla] = []
        for nombre in TABLAS_SECCIONES:
            clave = buscar([nombre])
            if clave:
                c, f = self._tabla_como_datos(clave)
                if c:
                    tablas_s.append(Tabla(clave, [c] + f))
        tablas_m: List[Tabla] = []
        for nombre in TABLAS_MATERIALES:
            clave = buscar([nombre])
            if clave:
                c, f = self._tabla_como_datos(clave)
                if c:
                    tablas_m.append(Tabla(clave, [c] + f))

        seleccion = self._seleccion_actual() if solo_seleccionados else None
        if solo_seleccionados and not seleccion:
            raise ConexionETABSError(
                "No hay barras seleccionadas en ETABS. Seleccione en el modelo "
                "las vigas y/o columnas que desea diseñar (o desmarque la "
                "opción «solo lo seleccionado» para usar todo el modelo).",
                codigo="sin_seleccion", sugerencias=[
                    "En ETABS, seleccione las barras con un clic o una ventana "
                    "de selección y luego pulse «Usar selección de ETABS».",
                    "Si prefiere todo el edificio, desmarque «solo lo seleccionado».",
                ])
        modelo = ETABSTablas.desde_tablas(
            tablas_f, tablas_s, tablas_m,
            unidades=self.clave_unidades,
            tipo_defecto="auto",
            origen=f"ETABS {self.version} (COM/OAPI)",
            seleccionados=seleccion)
        modelo.nombre = f"ETABS v{self.version} (en vivo)"
        return modelo

    # ------------------------------------------------------------------
    # Interfaz FuenteETABS
    # ------------------------------------------------------------------
    @property
    def modelo(self) -> ETABSTablas:
        """Modelo importado de ETABS; se refresca con `recargar()`."""
        if self._modelo is None:
            self._modelo = self.obtener_modelo(self._solo_seleccionados)
        return self._modelo

    def recargar(self, solo_seleccionados: Optional[bool] = None) -> ETABSTablas:
        """Vuelve a leer las tablas del modelo (tras cambiar la selección)."""
        if solo_seleccionados is not None:
            self._solo_seleccionados = bool(solo_seleccionados)
        self._modelo = self.obtener_modelo(self._solo_seleccionados)
        return self._modelo

    def listar_elementos(self, solo_seleccionados: bool = False,
                         tipo: Optional[str] = None) -> List[str]:
        if solo_seleccionados and not self._solo_seleccionados:
            self._solo_seleccionados = True
            self._modelo = None
        return self.modelo.listar_elementos(tipo=tipo)

    def obtener_elemento(self, nombre: str) -> Elemento:
        return self.modelo.obtener_elemento(nombre)

    def listar_combos(self) -> List[str]:
        return self.modelo.listar_combos()

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

    def _clasificar(self, nombre: str) -> str:
        """Clasifica una barra por la orientación de sus nudos (viga/columna)."""
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

    # ------------------------------------------------------------------
    # Lectura directa de resultados (respaldo, sin estaciones)
    # ------------------------------------------------------------------
    def _leer_fuerzas(self, nombre: str) -> List[PuntoDemanda]:
        puntos: List[PuntoDemanda] = []
        try:
            res = self.SapModel.Results.FrameForce(
                nombre, ITEM_OBJECT_ELM, 0, [], [], [], [], [], [],
                [], [], [], [], [])
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
        _, _, loadcase, _, _, P, V2, V3, T, M2, M3 = listas[:11]
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


def _a_numero(texto: str) -> bool:
    try:
        float(str(texto).replace(",", ""))
        return True
    except (TypeError, ValueError):
        return False


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


def conectar(adjuntar: bool = True, ruta: Optional[str] = None,
             solo_seleccionados: bool = False) -> ETABSCom:
    """
    Se engancha a la instancia de ETABS que ya está abierta.

    Solo se lanza una instancia nueva si se indica `ruta` (ruta del
    ejecutable de ETABS), nunca de forma implícita: abrir ETABS en blanco
    haría creer al usuario que el modelo se cargó. Lanza
    `ConexionETABSError` con mensajes y sugerencias en español.
    """
    return ETABSCom(adjuntar=adjuntar, ruta_etabs=ruta or None,
                    solo_seleccionados=solo_seleccionados)


def abrir_etabs(modelo: Optional[str] = None,
                ruta_etabs: Optional[str] = None) -> ETABSCom:
    """
    Abre ETABS (v20–v23) y opcionalmente carga un modelo `.edb`.

    `modelo`     : ruta del archivo .edb a abrir (opcional).
    `ruta_etabs` : ruta de ETABS.exe; si se omite se busca en las rutas típicas.
    """
    ruta = ruta_etabs or ruta_etabs_instalado()
    if not ruta:
        raise ConexionETABSError(
            "No se encontró la instalación de ETABS (ETABS.exe).",
            codigo="sin_com", sugerencias=[
                "Indique la ruta del ejecutable de ETABS.",
                "O abra ETABS manualmente con el modelo y use «Conectar».",
            ])
    fuente = ETABSCom(adjuntar=False, ruta_etabs=ruta)
    if modelo:
        try:
            fuente.SapModel.File.OpenFile(modelo)
        except Exception as exc:                     # noqa: BLE001
            raise RuntimeError(
                f"ETABS se abrió pero no se pudo cargar {modelo!r}: {exc}"
            ) from exc
    return fuente
