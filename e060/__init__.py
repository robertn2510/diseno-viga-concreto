"""
e060 — Motor de diseño de concreto armado según la Norma Técnica Peruana
E.060 "Concreto Armado" (RNE), con integración a ETABS v20 – v23.

Módulos
-------
unidades    : conversión de unidades y sistemas de unidades de ETABS.
normas      : constantes, factores φ, β1, acero mínimo, catálogo de varillas.
seccion     : análisis de sección por compatibilidad de deformaciones
              (flexo-compresión uniaxial y biaxial).
viga        : diseño de vigas (flexión, corte, torsión, sismorresistente).
columna     : diseño de columnas (P-M biaxial, esbeltez, confinamiento).
combinaciones : combinaciones de carga E.060 y envolventes.
etabs       : conectores (COM/OAPI, tablas exportadas y modelo demo).
figuras     : figuras SVG (sección, diagrama de interacción, envolventes).
memoria     : memoria de cálculo (documento, HTML, PDF, Markdown).
servicio    : orquestador de alto nivel usado por las interfaces.
cli         : consola (python -m e060.cli).
"""

__version__ = "4.1.0"
__norma__ = "NTP E.060 Concreto Armado (RNE) — ACI 318 adaptado"

from . import unidades, normas, seccion, viga, columna, combinaciones  # noqa: F401
