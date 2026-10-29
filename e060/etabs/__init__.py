"""
Conectores con ETABS v20 – v23.

Fuentes disponibles
-------------------
ETABSCom      : conexión COM/OAPI con ETABS en ejecución (Windows).
ETABSTablas   : importación de tablas exportadas (CSV/TXT/XLSX).
ETABSDemo     : modelo de ejemplo analizado por rigidez (sin ETABS).
"""

from .modelo import Elemento, FuenteETABS, PuntoDemanda  # noqa: F401
from .tablas import ETABSTablas, Tabla, leer_tablas      # noqa: F401
from .exportar import exportar_tablas, subir_tablas      # noqa: F401
from .demo import ETABSDemo                              # noqa: F401
from .com import (ConexionETABSError, diagnostico_com)    # noqa: F401

try:  # COM solo existe en Windows; se importa de forma diferida y tolerante
    from .com import ETABSCom, conectar, ruta_etabs_instalado  # noqa: F401
except Exception:  # pragma: no cover
    ETABSCom = None                 # type: ignore

    def conectar(*_a, **_k):        # type: ignore
        raise RuntimeError(
            "La conexión COM con ETABS solo está disponible en Windows con "
            "ETABS instalado (v20–v23). Use la importación de tablas o el "
            "modelo demo en este sistema.")

    def ruta_etabs_instalado():     # type: ignore
        return None


__all__ = [
    "Elemento", "FuenteETABS", "PuntoDemanda", "Tabla",
    "ETABSCom", "ETABSTablas", "ETABSDemo",
    "ConexionETABSError", "diagnostico_com",
    "conectar", "ruta_etabs_instalado", "leer_tablas",
    "exportar_tablas", "subir_tablas",
]
