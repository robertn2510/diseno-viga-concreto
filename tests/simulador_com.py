"""
Simulador de la interfaz COM/OAPI de ETABS v20 – v23.

Permite **probar en cualquier sistema operativo** el mismo código que se usa en
Windows, sin ETABS ni `comtypes`: se inyecta un módulo `comtypes.client` falso
que devuelve un objeto ETABS con la API OAPI (SapModel, FrameObj, DatabaseTables,
Results, SelectObj, ...) implementada sobre el modelo demo.

Las firmas y convenciones de retorno imitan al API real:
  * cada método devuelve una tupla `(retval, out1, out2, ...)`,
  * las listas de salida se devuelven como arrays de longitud `n`,
  * los índices `eUnits` siguen la enumeración de ETABS.

Uso en pruebas
--------------
    from simulador_com import instalar
    with instalar():                    # parchea sys.modules
        from e060.etabs import conectar
        fuente = conectar()
        fuente.listar_elementos()

Uso manual (demostración)
-------------------------
    python tests/simulador_com.py
"""

from __future__ import annotations

import math
import os
import sys
import types
from typing import Dict, List, Optional, Sequence, Tuple

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from e060.etabs import ETABSDemo          # noqa: E402


# ===========================================================================
# Sub-objetos de la API
# ===========================================================================
class _FrameObj:
    def __init__(self, sap: "SapModelFalso"):
        self._sap = sap

    def GetNameList(self, numero, nombres):
        nombres = list(self._sap.nombres)
        return (0, len(nombres), nombres)

    def GetPoints(self, nombre, p1, p2):
        el = self._sap.elemento(nombre)
        return (0, f"J_{nombre}_i", f"J_{nombre}_j")

    def GetSection(self, nombre, seccion, autoselect):
        el = self._sap.elemento(nombre)
        return (0, el.seccion, "")

    def GetLabelFromName(self, nombre, etiqueta, story):
        el = self._sap.elemento(nombre)
        return (0, el.nombre, el.story)


class _PointObj:
    def __init__(self, sap: "SapModelFalso"):
        self._sap = sap

    def GetCoordCartesian(self, nombre, x, y, z):
        coord = self._sap.coordenadas.get(nombre, (0.0, 0.0, 0.0))
        return (0, float(coord[0]), float(coord[1]), float(coord[2]))


class _PropFrame:
    def __init__(self, sap: "SapModelFalso"):
        self._sap = sap

    def GetRectangle(self, prop, nombre, material, t3, t2):
        for sec, (b, h, mat) in self._sap.secciones.items():
            if sec == prop:
                return (0, sec, mat, h / 100.0, b / 100.0)
        return (-1, "", "", 0.0, 0.0)

    def GetSectProps(self, prop, area, as2, as3, torsion, tipo):
        return (0, 0.0, 0.0, 0.0, 0.0)


class _PropMaterial:
    def __init__(self, sap: "SapModelFalso"):
        self._sap = sap

    def GetOConcrete(self, mat, fc, *args):
        # f'c en kgf/m² (ETABS guarda tensiones en fuerza/longitud²)
        return (0, self._sap.materiales.get(mat, 210.0) * 1.0e4)

    def GetORebar(self, mat, fy, fu, *args):
        return (0, 4200.0 * 1.0e4, 6300.0 * 1.0e4)


class _RespCombo:
    def __init__(self, sap: "SapModelFalso"):
        self._sap = sap

    def GetNameList(self, numero, nombres):
        combos = list(self._sap.combos)
        return (0, len(combos), combos)


class _ResultsSetup:
    def __init__(self):
        self.seleccionados: List[str] = []

    def DeselectAllCasesAndCombosForOutput(self):
        self.seleccionados.clear()
        return 0

    def SetComboSelectedForOutput(self, combo, seleccionado=True):
        if seleccionado:
            self.seleccionados.append(combo)
        return 0


class _Results:
    def __init__(self, sap: "SapModelFalso"):
        self._sap = sap
        self.Setup = _ResultsSetup()

    def FrameForce(self, nombre, item_type, numero, obj, elm, caso, step,
                   stepnum, p, v2, v3, t, m2, m3):
        """Devuelve las fuerzas SIN estación (limitación real del API)."""
        el = self._sap.elemento(nombre)
        puntos = el.puntos
        n = len(puntos)
        nombres = [nombre] * n
        elems = [f"{nombre}-1"] * n
        casos = [p_.combo for p_ in puntos]
        tipos = ["Max"] * n
        pasos = [0] * n
        return (0, n, nombres, elems, casos, tipos, pasos,
                [p_.P / 1.0 for p_ in puntos],          # kgf
                [p_.V2 for p_ in puntos],
                [p_.V3 for p_ in puntos],
                [p_.T / 100.0 for p_ in puntos],        # kgf·m
                [p_.M2 / 100.0 for p_ in puntos],
                [p_.M3 / 100.0 for p_ in puntos])


class _SelectObj:
    def __init__(self, sap: "SapModelFalso"):
        self._sap = sap

    def GetSelected(self, numero, tipos, nombres):
        seleccion = list(self._sap.seleccionados)
        return (0, len(seleccion), [2] * len(seleccion), seleccion)


class _DatabaseTables:
    """Tablas de la base de datos del modelo, como las entrega ETABS."""

    def __init__(self, sap: "SapModelFalso"):
        self._sap = sap

    # -- tablas disponibles -------------------------------------------------
    def GetAvailableTables(self, numero, claves, tipos):
        claves = list(self._sap.tablas())
        return (0, len(claves), claves, [0] * len(claves))

    def GetTableForDisplayArray(self, clave, campos, grupo, *extra):
        tabla = self._sap.tablas().get(clave)
        if tabla is None:
            return (-1, 0, [], 0, [])
        cabecera, filas = tabla
        plano: List[str] = []
        for fila in filas:
            plano.extend(str(v) for v in fila)
        return (0, 1, list(cabecera), len(filas), plano)


class SapModelFalso:
    """SapModel de ETABS simulado sobre el modelo demo."""

    def __init__(self, demo: Optional[ETABSDemo] = None, version: str = "23.0.0"):
        self.demo = demo or ETABSDemo()
        self.version = version
        self.eUnits = 8                      # kgf, m, °C
        self.nombres = self.demo.listar_elementos()
        self.combos = self.demo.listar_combos()
        self.seleccionados: List[str] = list(self.nombres)
        self.bloqueado = False
        self.tabla_personalizada: Dict[str, tuple] = {}
        self.frame = _FrameObj(self)
        self.point = _PointObj(self)
        self.prop_frame = _PropFrame(self)
        self.prop_material = _PropMaterial(self)
        self.resp_combo = _RespCombo(self)
        self.results = _Results(self)
        self.select = _SelectObj(self)
        self.database_tables = _DatabaseTables(self)
        self.coordenadas = self._coordenadas()

    # -- utilidades ---------------------------------------------------------
    def elemento(self, nombre: str):
        return self.demo.obtener_elemento(nombre)

    def _coordenadas(self) -> Dict[str, Tuple[float, float, float]]:
        """Genera nudos coherentes con la orientación viga/columna."""
        coords: Dict[str, Tuple[float, float, float]] = {}
        for i, nombre in enumerate(self.nombres):
            el = self.elemento(nombre)
            if el.tipo == "Columna":
                coords[f"J_{nombre}_i"] = (i * 6.0, 0.0, 0.0)
                coords[f"J_{nombre}_j"] = (i * 6.0, 0.0, el.L / 100.0)
            else:
                coords[f"J_{nombre}_i"] = (0.0, i * 6.0, 3.2)
                coords[f"J_{nombre}_j"] = (el.L / 100.0, i * 6.0, 3.2)
        return coords

    @property
    def secciones(self) -> Dict[str, Tuple[float, float, str]]:
        salida: Dict[str, Tuple[float, float, str]] = {}
        for nombre in self.nombres:
            el = self.elemento(nombre)
            salida[el.seccion] = (el.b, el.h, f"CONC{el.fc:.0f}")
        return salida

    @property
    def materiales(self) -> Dict[str, float]:
        return {f"CONC{el.fc:.0f}": el.fc for el in
                (self.elemento(n) for n in self.nombres)}

    # -- tablas -------------------------------------------------------------
    def tablas(self) -> Dict[str, Tuple[List[str], List[List[str]]]]:
        if self.tabla_personalizada:
            return self.tabla_personalizada
        return self._tablas_por_defecto()

    def _num(self, v: float) -> str:
        return f"{v:.5f}".rstrip("0").rstrip(".") or "0"

    def _tablas_por_defecto(self):
        filas_f: List[List[str]] = []
        filas_asig: List[List[str]] = []
        for nombre in self.nombres:
            el = self.elemento(nombre)
            filas_asig.append([el.story, nombre, nombre, el.seccion, el.seccion])
            for p in sorted(el.puntos, key=lambda q: (q.estacion, q.combo)):
                filas_f.append([
                    el.story, nombre, self._num(p.estacion / 100.0), p.combo,
                    "Combination", self._num(p.P), self._num(p.V2),
                    self._num(p.V3), self._num(p.T / 100.0),
                    self._num(p.M2 / 100.0), self._num(p.M3 / 100.0)])
        cab_f = ["Story", "Frame", "Station", "Output Case", "Case Type",
                 "P", "V2", "V3", "T", "M2", "M3"]
        cab_asig = ["Story", "Line", "Frame", "DesignSect", "AnalysisSect"]
        cab_sec = ["PropName", "Material", "t3", "t2"]
        filas_sec = [[sec, mat, f"{h/100:.4f}", f"{b/100:.4f}"]
                     for sec, (b, h, mat) in self.secciones.items()]
        cab_mat = ["Material", "f'c"]
        filas_mat = [[mat, f"{fc * 1.0e4:.1f}"]
                     for mat, fc in self.materiales.items()]
        return {
            "Element Forces - Frames": (cab_f, filas_f),
            "Frame Assignments - Section Properties": (cab_asig, filas_asig),
            "Frame Section Properties - Rectangular": (cab_sec, filas_sec),
            "Material Properties - Concrete Data": (cab_mat, filas_mat),
            "Load Combination Definitions": (["Name"], [[c] for c in self.combos]),
        }

    # -- métodos del SapModel ----------------------------------------------
    def GetVersion(self, *args):
        return (0, self.version)

    def GetPresentUnits(self):
        return (0, self.eUnits)

    def SetPresentUnits(self, unidades):
        self.eUnits = int(unidades)
        return 0

    def GetModelFilename(self):
        return (0, r"C:\Proyectos\Edificio_Cusco.EDB")

    def GetModelIsLocked(self):
        return (0, self.bloqueado)


class _ProxyAttr:
    """Traduce los nombres de la API (FrameObj, PropFrame...) a los del simulador."""

    _MAPA = {
        "FrameObj": "frame",
        "PointObj": "point",
        "PropFrame": "prop_frame",
        "PropMaterial": "prop_material",
        "RespCombo": "resp_combo",
        "Results": "results",
        "SelectObj": "select",
        "DatabaseTables": "database_tables",
    }

    def __init__(self, sap: SapModelFalso):
        object.__setattr__(self, "_sap", sap)

    def __getattr__(self, nombre):
        if nombre in self._MAPA:
            return getattr(object.__getattribute__(self, "_sap"), self._MAPA[nombre])
        return getattr(object.__getattribute__(self, "_sap"), nombre)

    def __setattr__(self, nombre, valor):
        # permite que las pruebas modifiquen el SapModel simulado a través del
        # proxy (p. ej. seleccionar barras o cambiar las tablas)
        setattr(object.__getattribute__(self, "_sap"), nombre, valor)


class EtabsObjectFalso:
    """Equivalente a CSI.ETABS.API.ETABSObject."""

    def __init__(self, demo: Optional[ETABSDemo] = None, version: str = "23.0.0"):
        self.SapModel = _ProxyAttr(SapModelFalso(demo, version))
        self.iniciada = False

    def ApplicationStart(self):
        self.iniciada = True
        return 0

    def ApplicationExit(self):
        return 0


# ===========================================================================
# Simulación del backend COM
# ===========================================================================
class _ClientFalso:
    """Imita `comtypes.client` / `win32com.client`."""

    def __init__(self):
        self.objetos: Dict[str, EtabsObjectFalso] = {}
        self.demora_conexion: Optional[Exception] = None

    def registrar(self, progid: str, objeto: EtabsObjectFalso) -> None:
        self.objetos[progid] = objeto

    def GetActiveObject(self, progid):
        if self.demora_conexion is not None:
            raise self.demora_conexion
        if progid not in self.objetos:
            raise OSError(f"No hay ningún objeto activo con ProgID {progid!r}")
        return self.objetos[progid]

    def CreateObject(self, progid, *args):
        if progid not in self.objetos:
            raise OSError(f"No se puede crear el objeto {progid!r}")
        return self.objetos[progid]

    Dispatch = CreateObject


class _NamedAttr(types.ModuleType):
    def __init__(self, nombre):
        super().__init__(nombre)
        self.client = _ClientFalso()


class _Contexto:
    """Context manager: inyecta el backend COM falso durante la prueba."""

    def __init__(self, demo: Optional[ETABSDemo] = None, version: str = "23.0.0",
                 backend: str = "comtypes", sin_etabs: bool = False):
        self.demo = demo
        self.version = version
        self.backend = backend
        self.sin_etabs = sin_etabs
        self._previos: Dict[str, object] = {}
        self.cliente = _ClientFalso()
        self.etabs = EtabsObjectFalso(demo, version)

    def __enter__(self):
        for nombre in ("comtypes", "comtypes.client", "win32com", "win32com.client"):
            self._previos[nombre] = sys.modules.get(nombre)
        if self.backend == "comtypes":
            self.cliente.registrar("CSI.ETABS.API.ETABSObject", self.etabs)
            self.cliente.registrar("ETABSv1.Helper", self.etabs)
            modulo = _NamedAttr("comtypes")
            modulo.client = self.cliente
            sys.modules["comtypes"] = modulo
            sys.modules["comtypes.client"] = modulo.client  # type: ignore[assignment]
            sys.modules.pop("win32com", None)
            sys.modules.pop("win32com.client", None)
        else:
            self.cliente.registrar("CSI.ETABS.API.ETABSObject", self.etabs)
            self.cliente.registrar("ETABSv1.Helper", self.etabs)
            paquete = types.ModuleType("win32com")
            cliente = types.ModuleType("win32com.client")
            cliente.GetActiveObject = self.cliente.GetActiveObject
            cliente.Dispatch = self.cliente.Dispatch
            paquete.client = cliente
            sys.modules["win32com"] = paquete
            sys.modules["win32com.client"] = cliente
            sys.modules.pop("comtypes", None)
            sys.modules.pop("comtypes.client", None)
        if self.sin_etabs:
            self.cliente.demora_conexion = OSError("No hay ETABS en ejecución")
            self.cliente.objetos.clear()
        return self

    def __exit__(self, *exc):
        for nombre, previo in self._previos.items():
            if previo is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = previo
        return False


def instalar(demo: Optional[ETABSDemo] = None, version: str = "23.0.0",
             backend: str = "comtypes", sin_etabs: bool = False) -> _Contexto:
    """
    Devuelve un context manager que simula ETABS vía COM.

    backend   : "comtypes" (recomendado en Windows) o "win32com".
    sin_etabs : simula que ETABS no está abierto (para probar el diagnóstico).
    """
    return _Contexto(demo, version, backend, sin_etabs)


# ===========================================================================
# Demostración manual
# ===========================================================================
def _demo():
    from e060 import memoria, servicio
    with instalar() as ctx:
        from e060.etabs import conectar
        fuente = conectar(solo_seleccionados=False)
        print("Versión:", fuente.version, "| unidades:", fuente.clave_unidades)
        print("Backend:", fuente.backend)
        print("Info:", fuente.info_modelo())
        nombres = fuente.listar_elementos()
        print(f"Elementos leídos de la 'base de datos' de ETABS: {len(nombres)}")
        for nombre in ("V1-2", "C1-1"):
            el = fuente.obtener_elemento(nombre)
            print(f"  {nombre}: {el.tipo} {el.b:.0f}x{el.h:.0f} cm, "
                  f"L={el.L:.0f} cm, f'c={el.fc:.0f}, {len(el.combos)} combos, "
                  f"{len(el.puntos)} puntos, estaciones={el.estaciones}")
            out = servicio.disenar_elemento(el, servicio.OpcionesDiseno())
            res = out["resumen"]
            if out["tipo"] == "Viga":
                print("    ", res["filas"][0]["ref_neg"], "| estribos",
                      res["corte_gobernante"]["estribo"],
                      f"@{res['corte_gobernante']['s_conf']:g}/"
                      f"{res['corte_gobernante']['s_resto']:g} cm")
            else:
                print("    ", res["refuerzo"], f"D/C={res['dcr']:.3f}")
            print("     verificaciones:",
                  "todas OK" if all(v["cumple"] for v in servicio.verificar_resultado(out))
                  else "revisar")
        fuente.cerrar()


if __name__ == "__main__":
    _demo()
    print("\n--- backend win32com ---")
    with instalar(backend="win32com") as ctx:
        from e060.etabs import conectar
        fuente = conectar()
        print("Backend:", fuente.backend, "| elementos:", len(fuente.listar_elementos()))
    print("\n--- diagnóstico sin ETABS ---")
    with instalar(sin_etabs=True):
        from e060.etabs import ConexionETABSError, conectar
        try:
            conectar()
        except ConexionETABSError as exc:
            print("OK, error controlado:", exc.codigo)
