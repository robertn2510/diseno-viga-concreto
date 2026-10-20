#!/usr/bin/env python3
"""
Punto de entrada del programa de diseño de vigas E.060 a partir de ETABS.

Uso rápido::

    python main.py --demo          # caso sintético, no requiere ETABS
    python main.py --listar        # lista las vigas del modelo abierto
    python main.py --seccion VP-25x50 --piso "Piso 2"

Requiere Windows para la conexión COM con ETABS (comtypes o pywin32).
"""

from __future__ import annotations

import sys

from vigas_e060.cli import main

if __name__ == "__main__":
    sys.exit(main())
