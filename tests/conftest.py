"""
Objetos simulados de la API ETABS para probar el flujo completo sin Windows.

La estructura de las tuplas reproduce la documentación de ETABSv1:
``(..., código_de_retorno)``.  Las unidades presentes son ``kgf_m``
(eUnits = 8), de modo que las conversiones de :class:`ConexionETABS` se
ejercitan realmente.
"""

from __future__ import annotations

import pytest

from vigas_e060.etabs.conexion import ConexionETABS, InfoConexion
from vigas_e060.unidades import UNIDADES_ETABS


# ---------------------------------------------------------------------------
# Datos del modelo simulado
# ---------------------------------------------------------------------------
B, H = 0.25, 0.50          # m
L = 6.0                    # m
Z = 3.0                    # m
COMBOS = {
    "E060-1.4D+1.7L": (
        (0, "DEAD", 1.4), (0, "LIVE", 1.7),
    ),
    "E060-1.25(D+L)+1.25SISMO": (
        (0, "DEAD", 1.25), (0, "LIVE", 1.25), (0, "SISMO", 1.25),
    ),
    "E060-1.25(D+L)-1.25SISMO": (
        (0, "DEAD", 1.25), (0, "LIVE", 1.25), (0, "SISMO", -1.25),
    ),
    "E060-0.9D+1.25SISMO": (
        (0, "DEAD", 0.9), (0, "SISMO", 1.25),
    ),
    "E060-0.9D-1.25SISMO": (
        (0, "DEAD", 0.9), (0, "SISMO", -1.25),
    ),
}

# Estaciones (m) y fuerzas por combinación: (M3 kgf·m, V2 kgf, P kgf)
ESTACIONES = [0.0, 0.3, 3.0, 5.7, 6.0]
FUERZAS = {
    "E060-1.4D+1.7L": [
        (-12_000, 14_000, -2_000),
        (-8_000, 12_000, -2_000),
        (8_500, 0, -2_000),
        (-9_000, -12_000, -2_000),
        (-13_000, -14_000, -2_000),
    ],
    "E060-1.25(D+L)+1.25SISMO": [
        (-18_000, 20_000, -2_800),
        (-13_000, 18_000, -2_800),
        (10_000, 0, -2_800),
        (-14_000, -18_000, -2_800),
        (-19_000, -20_000, -2_800),
    ],
    "E060-1.25(D+L)-1.25SISMO": [
        (-6_000, 8_000, -1_500),
        (-4_000, 7_000, -1_500),
        (6_000, 0, -1_500),
        (-5_000, -7_000, -1_500),
        (-7_000, -8_000, -1_500),
    ],
    "E060-0.9D+1.25SISMO": [
        (-15_000, 17_000, -2_400),
        (-11_000, 15_000, -2_400),
        (9_000, 0, -2_400),
        (-12_000, -15_000, -2_400),
        (-16_000, -17_000, -2_400),
    ],
    "E060-0.9D-1.25SISMO": [
        (-5_000, 6_000, -1_000),
        (-3_000, 5_000, -1_000),
        (4_000, 0, -1_000),
        (-4_000, -5_000, -1_000),
        (-6_000, -6_000, -1_000),
    ],
}


# ---------------------------------------------------------------------------
# Subobjetos de la API
# ---------------------------------------------------------------------------
class _FrameObj:
    def GetAllFrames(self):
        nombres = ["V-101", "C-1", "C-2"]
        props = ["VP-25x50", "COL-30x60", "COL-30x60"]
        pisos = ["Piso 2", "Piso 2", "Piso 2"]
        pto1 = ["1", "1", "2"]
        pto2 = ["2", "3", "4"]
        x1 = [0.0, 0.0, L]
        y1 = [0.0, 0.0, 0.0]
        z1 = [Z, 0.0, 0.0]
        x2 = [L, 0.0, L]
        y2 = [0.0, 0.0, 0.0]
        z2 = [Z, Z, Z]
        return (
            len(nombres), nombres, props, pisos, pto1, pto2,
            x1, y1, z1, x2, y2, z2,
            [0.0] * 3, [0.0] * 6, "", 0,
        )

    def GetLabelFromName(self, nombre):
        if nombre == "V-101":
            return ("V-101", "Piso 2", 0)
        return (nombre, "Piso 2", 0)


class _PropFrame:
    def GetTypeOAPI(self, seccion):
        return (8, 0)

    def GetRectangle(self, seccion):
        if seccion == "VP-25x50":
            t3, t2 = H, B
        else:
            t3, t2 = 0.60, 0.30
        return ("", "CONC", t3, t2, 0, "", "guid", 0)

    def GetRebarBeam(self, seccion):
        return ("LONG", "CONF", 0.06, 0.06, 0, 0, 0, 0, 0)


class _PropMaterial:
    def GetMaterial(self, material):
        return (2, 0)

    def GetOConcrete(self, material):
        # kgf/m² (unidad presente kgf_m)
        return (2_100_000.0, 0)


class _RespCombo:
    def GetNameList(self):
        nombres = list(COMBOS)
        return (len(nombres), nombres, 0)

    def GetCaseList(self, nombre):
        casos = COMBOS[nombre]
        tipos = [c[0] for c in casos]
        nombres = [c[1] for c in casos]
        factores = [c[2] for c in casos]
        return (len(casos), tipos, nombres, factores, 0)

    def GetTypeOAPI(self, nombre):
        return (0, 0)

    def Add(self, nombre, tipo):
        return 0

    def SetCaseList(self, nombre, tipo, caso, factor):
        return 0


class _LoadPatterns:
    def GetNameList(self):
        nombres = ["DEAD", "LIVE", "SISMO"]
        return (len(nombres), nombres, 0)


class _Setup:
    def SetComboSelectedForOutput(self, nombre, valor=True):
        return 0


class _Results:
    def __init__(self):
        self.Setup = _Setup()

    def FrameForce(self, nombre_viga, item_type=0):
        if nombre_viga != "V-101":
            return (0, [], [], [], [], [], [], [], [], [], [], [], [], [], 0)
        n = len(COMBOS) * len(ESTACIONES)
        obj = []
        sta = []
        elm = []
        elmsta = []
        casos = []
        steptype = []
        stepnum = []
        P, V2, V3, T, M2, M3 = [], [], [], [], [], []
        for combo, valores in FUERZAS.items():
            for x, (m3, v2, p) in zip(ESTACIONES, valores):
                obj.append(nombre_viga)
                sta.append(x)
                elm.append(nombre_viga)
                elmsta.append(x)
                casos.append(combo)
                steptype.append("Max")
                stepnum.append(1)
                P.append(p)
                V2.append(v2)
                V3.append(0.0)
                T.append(0.0)
                M2.append(0.0)
                M3.append(m3)
        return (
            n, obj, sta, elm, elmsta, casos, steptype, stepnum,
            P, V2, V3, T, M2, M3, 0,
        )


class _Analyze:
    def RunAnalysis(self):
        return 0


class _DesignConcrete:
    def GetComboStrength(self):
        return (list(COMBOS), 0)


class FakeSapModel:
    """SapModel mínimo con las firmas usadas por :mod:`vigas_e060`."""

    def __init__(self):
        self.FrameObj = _FrameObj()
        self.PropFrame = _PropFrame()
        self.PropMaterial = _PropMaterial()
        self.RespCombo = _RespCombo()
        self.LoadPatterns = _LoadPatterns()
        self.Results = _Results()
        self.Analyze = _Analyze()
        self.DesignConcrete = _DesignConcrete()
        self.unidades = 8

    def GetPresentUnits(self):
        return (self.unidades, 0)

    def SetPresentUnits(self, codigo):
        self.unidades = codigo
        return 0

    def GetModelIsLocked(self):
        return False

    def SetModelIsLocked(self, valor):
        return 0


def hacer_conexion(sap: FakeSapModel | None = None) -> ConexionETABS:
    sap = sap or FakeSapModel()
    info = InfoConexion(
        version="23.0.0",
        version_mayor=23,
        modelo="demo.edb",
        ruta_modelo=r"C:\demo.edb",
        unidad_trabajo=UNIDADES_ETABS[8],
        api="ETABSv1 (simulado)",
        bloqueado=False,
    )
    return ConexionETABS(etabs_object=None, sap_model=sap, info=info)


@pytest.fixture()
def conexion():
    return hacer_conexion()


@pytest.fixture()
def sap():
    return FakeSapModel()
