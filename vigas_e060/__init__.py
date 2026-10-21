"""
vigas_e060 — Diseño de vigas de concreto armado según la NTE E.060 (Perú).

Flujo típico::

    from vigas_e060 import conectar_etabs, extraer_fuerzas, diseno_flexion, \
        diseno_cortante, generar_reporte

    conexion = conectar_etabs()
    vigas = extraer_vigas(conexion, config)
    fuerzas = extraer_fuerzas(conexion, vigas[0], combos)
    ...
    generar_reporte(resultados, metadatos, verificaciones, combos)

Las cinco funciones requeridas por la especificación son:

* :func:`conectar_etabs`  — conexión COM con ETABS v18–v23.
* :func:`extraer_fuerzas` — fuerzas internas M3/V2 por combinación.
* :func:`diseno_flexion`  — diseño a flexión (E.060 Cap. 10).
* :func:`diseno_cortante` — diseño a cortante (E.060 Cap. 11 y 21.5).
* :func:`generar_reporte` — memoria de cálculo (.md / .docx).
"""

from __future__ import annotations

__version__ = "4.0.0"
__author__ = "Ingeniería estructural"

from .calculo.cortante import disenar_cortante as diseno_cortante
from .calculo.diseno import disenar_viga, resumen_armado
from .calculo.flexion import disenar_flexion as diseno_flexion
from .config import ConfiguracionDiseno
from .etabs.conexion import conectar_etabs
from .etabs.extraccion import (
    extraer_fuerzas,
    extraer_vigas,
    leer_fuerzas_combo,
    listar_resumen_vigas,
)
from .modelos import (
    FuerzasViga,
    Materiales,
    MetadatosProyecto,
    ResultadoViga,
    VigaETABS,
)
from .reporte import generar_reporte

__all__ = [
    "ConfiguracionDiseno",
    "FuerzasViga",
    "Materiales",
    "MetadatosProyecto",
    "ResultadoViga",
    "VigaETABS",
    "__version__",
    "conectar_etabs",
    "disenar_viga",
    "diseno_cortante",
    "diseno_flexion",
    "extraer_fuerzas",
    "extraer_vigas",
    "generar_reporte",
    "leer_fuerzas_combo",
    "listar_resumen_vigas",
    "resumen_armado",
]
