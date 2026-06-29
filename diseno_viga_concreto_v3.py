"""
=============================================================================
  DISEÑO DE VIGAS DE CONCRETO REFORZADO - NTP E.060 (Normativa Peruana)
  Versión: 3.0 — MEJORADA con Corte, PDF y Gráficos
  Basado en: ACI 318 adaptado a la norma peruana E.060
=============================================================================

INSTRUCCIONES DE EJECUCIÓN:
  1. Asegúrate de tener Python 3.8+ instalado.
  2. Instala las dependencias necesarias:
       pip install -r requirements.txt
  3. Ejecuta el programa desde la terminal:
       python diseno_viga_concreto_v3.py

DEPENDENCIAS: 
  - tkinter (incluida en Python)
  - math, os
  - reportlab (para PDF)
  - matplotlib (para gráficos)
  - pillow (para manejo de imágenes)
=============================================================================
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
import math
import os
from io import BytesIO
from datetime import datetime

# Importes opcionales con manejo de error
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


# ===========================================================================
# MÓDULO DE CÁLCULO ESTRUCTURAL - FLEXIÓN
# ===========================================================================

class DisenoViga:
    """
    Clase principal que encapsula todo el cálculo estructural
    para el diseño de vigas de concreto reforzado según NTP E.060.
    """

    # Tabla de varillas comerciales (diámetro en pulgadas → área en cm², diámetro en cm)
    VARILLAS = {
        '3/8"': {'area': 0.713, 'diametro': 0.953},
        '1/2"': {'area': 1.267, 'diametro': 1.270},
        '5/8"': {'area': 1.979, 'diametro': 1.588},
        '3/4"': {'area': 2.850, 'diametro': 1.905},
        '1"':   {'area': 5.070, 'diametro': 2.540},
    }

    def __init__(self, b, h, L, fc, fy, Md, Ml, r=4.0):
        """
        Inicializa los datos de entrada de la viga.

        Parámetros:
            b  (float): Base de la viga [cm]
            h  (float): Altura total de la viga [cm]
            L  (float): Luz libre de la viga [m]
            fc (float): Resistencia a compresión del concreto f'c [kg/cm²]
            fy (float): Fluencia del acero fy [kg/cm²]
            Md (float): Momento por carga muerta [ton·m]
            Ml (float): Momento por carga viva [ton·m]
            r  (float): Recubrimiento libre [cm] (defecto: 4 cm)
        """
        self.b = b
        self.h = h
        self.L = L
        self.fc = fc
        self.fy = fy
        self.Md = Md
        self.Ml = Ml
        self.r = r

        # Diámetro de estribo asumido (varilla 3/8") en cm
        self.d_estribo = 0.953

        # Diámetro de barra longitudinal asumida inicialmente (5/8") en cm
        self.d_barra_asumida = 1.588

        # Peralte efectivo (una capa de acero) [cm]
        self.d = h - r - self.d_estribo - (self.d_barra_asumida / 2)

        # Resultados (se llenan en calcular())
        self.resultados = {}

    # -----------------------------------------------------------------------
    # 1. FACTOR β1 (bloque de Whitney) según NTP E.060 Art. 10.2.7.3
    # -----------------------------------------------------------------------
    def _beta1(self):
        """
        Calcula el factor β1 para el bloque rectangular de esfuerzos.
        - Si f'c ≤ 280 kg/cm²  → β1 = 0.85
        - Por cada 70 kg/cm² adicionales, se reduce 0.05 (mín. 0.65)
        """
        if self.fc <= 280:
            return 0.85
        else:
            b1 = 0.85 - 0.05 * ((self.fc - 280) / 70)
            return max(b1, 0.65)

    # -----------------------------------------------------------------------
    # 2. MOMENTO ÚLTIMO AMPLIFICADO según NTP E.060 / RNE
    # -----------------------------------------------------------------------
    def _momento_ultimo(self):
        """
        Calcula el momento último mayorado [ton·m].
        Combinación de carga: Mu = 1.4·Md + 1.7·Ml
        """
        Mu = 1.4 * self.Md + 1.7 * self.Ml
        return Mu

    # -----------------------------------------------------------------------
    # 3. ÁREA DE ACERO REQUERIDA (método del bloque rectangular)
    # -----------------------------------------------------------------------
    def _area_acero_requerida(self, Mu_ton_m):
        """
        Calcula el área de acero As requerida para resistir Mu.
        """
        phi_b = 0.90
        Mu_cm = Mu_ton_m * 1e5  # ton·m → kg·cm

        d = self.d
        b = self.b
        fc = self.fc
        fy = self.fy

        Ku = Mu_cm / (phi_b * b * d**2)
        discriminante = 1 - (2 * Ku) / (0.85 * fc)
        
        if discriminante < 0:
            raise ValueError(
                "La sección b×h es INSUFICIENTE para el momento último.\n"
                "Incremente las dimensiones de la viga o reduzca las cargas."
            )

        rho = (0.85 * fc / fy) * (1 - math.sqrt(discriminante))
        As = rho * b * d
        return As, rho

    # -----------------------------------------------------------------------
    # 4. ACERO MÍNIMO Y MÁXIMO
    # -----------------------------------------------------------------------
    def _acero_minimo(self):
        """Acero mínimo por flexión (NTP E.060 Art. 10.5)"""
        As_min1 = (0.7 * math.sqrt(self.fc) / self.fy) * self.b * self.d
        As_min2 = (14 / self.fy) * self.b * self.d
        return max(As_min1, As_min2), As_min1, As_min2

    def _acero_maximo(self):
        """Acero máximo (cuantía balanceada reducida al 75%)"""
        beta1 = self._beta1()
        rho_bal = (0.85 * beta1 * self.fc / self.fy) * (6120 / (6120 + self.fy))
        rho_max = 0.75 * rho_bal
        As_max = rho_max * self.b * self.d
        return As_max, rho_max, rho_bal

    # -----------------------------------------------------------------------
    # 5. PROFUNDIDAD DEL BLOQUE A COMPRESIÓN
    # -----------------------------------------------------------------------
    def _profundidad_bloque(self, As):
        """Calcula la profundidad a del bloque rectangular [cm]."""
        return (As * self.fy) / (0.85 * self.fc * self.b)

    def _deformacion_acero(self, a):
        """Verifica la deformación del acero en tracción."""
        beta1 = self._beta1()
        c = a / beta1
        epsilon_u = 0.003
        epsilon_t = epsilon_u * (self.d - c) / c
        return epsilon_t, c

    # -----------------------------------------------------------------------
    # 6. SUGERENCIA DE VARILLAS COMERCIALES
    # -----------------------------------------------------------------------
    def _sugerir_varillas(self, As_diseno):
        """
        Para cada tipo de varilla comercial, calcula cuántas unidades
        se necesitan para alcanzar o superar As_diseño [cm²].
        """
        sugerencias = []
        for nombre, datos in self.VARILLAS.items():
            area_barra = datos['area']
            d_barra = datos['diametro']
            n_barras = math.ceil(As_diseno / area_barra)
            As_provisto = n_barras * area_barra

            sep_min = max(2.5, d_barra)
            ancho_ocupado = (
                2 * (self.r + self.d_estribo)
                + n_barras * d_barra
                + (n_barras - 1) * sep_min
            )
            cabe_en_base = ancho_ocupado <= self.b

            sugerencias.append({
                'varilla': nombre,
                'n_barras': n_barras,
                'As_provisto': As_provisto,
                'diferencia': As_provisto - As_diseno,
                'cabe_en_base': cabe_en_base,
                'ancho_ocupado': ancho_ocupado,
                'd_barra': d_barra,
            })
        return sugerencias

    # -----------------------------------------------------------------------
    # 7. VERIFICACIONES DIMENSIONALES
    # -----------------------------------------------------------------------
    def _verificaciones_dimensionales(self):
        """Requisitos dimensionales para vigas en sistemas de pórticos."""
        checks = {}
        checks['ancho_min'] = {
            'descripcion': 'Ancho mínimo ≥ 25 cm',
            'valor': self.b,
            'limite': 25,
            'cumple': self.b >= 25
        }
        L_cm = self.L * 100
        checks['luz_peralte'] = {
            'descripcion': 'Luz libre ≥ 4·h',
            'valor': L_cm,
            'limite': 4 * self.h,
            'cumple': L_cm >= 4 * self.h
        }
        checks['relacion_aspecto'] = {
            'descripcion': 'Base ≥ h/4',
            'valor': self.b,
            'limite': self.h / 4,
            'cumple': self.b >= self.h / 4
        }
        return checks

    # -----------------------------------------------------------------------
    # 8. MÉTODO PRINCIPAL DE CÁLCULO - FLEXIÓN
    # -----------------------------------------------------------------------
    def calcular(self):
        """Ejecuta el flujo completo de diseño de flexión."""
        r = {}

        r['b'] = self.b
        r['h'] = self.h
        r['L'] = self.L
        r['fc'] = self.fc
        r['fy'] = self.fy
        r['Md'] = self.Md
        r['Ml'] = self.Ml
        r['r'] = self.r
        r['d'] = self.d
        r['beta1'] = self._beta1()

        Mu = self._momento_ultimo()
        r['Mu'] = Mu
        r['Mu_kg_cm'] = Mu * 1e5

        As_req, rho_req = self._area_acero_requerida(Mu)
        r['As_req'] = As_req
        r['rho_req'] = rho_req

        As_min, As_min1, As_min2 = self._acero_minimo()
        r['As_min'] = As_min
        r['As_min1'] = As_min1
        r['As_min2'] = As_min2

        As_max, rho_max, rho_bal = self._acero_maximo()
        r['As_max'] = As_max
        r['rho_max'] = rho_max
        r['rho_bal'] = rho_bal

        As_diseno = max(As_req, As_min)
        r['As_diseno'] = As_diseno
        r['cumple_cuantia_maxima'] = As_diseno <= As_max

        a = self._profundidad_bloque(As_diseno)
        epsilon_t, c = self._deformacion_acero(a)
        r['a'] = a
        r['c'] = c
        r['epsilon_t'] = epsilon_t
        r['cumple_ductilidad'] = epsilon_t >= 0.004

        r['verificaciones'] = self._verificaciones_dimensionales()
        r['varillas'] = self._sugerir_varillas(As_diseno)

        self.resultados = r
        return r


# ===========================================================================
# MÓDULO DE CÁLCULO ESTRUCTURAL - CORTE (NTP E.060)
# ===========================================================================

class DisenoCorte:
    """
    Clase para el diseño de acero de corte en vigas según NTP E.060.
    """

    ESTRIBOS = {
        '3/8"': {'area': 0.713, 'diametro': 0.953},
        '1/2"': {'area': 1.267, 'diametro': 1.270},
        '5/8"': {'area': 1.979, 'diametro': 1.588},
    }

    def __init__(self, b, d, fc, fy, Vd, Vl, f_corte_permite_concreto=True):
        """
        Parámetros:
            b, d: base y peralte efectivo [cm]
            fc, fy: resistencias [kg/cm²]
            Vd, Vl: cortantes por carga muerta y viva [ton]
            f_corte_permite_concreto: si es True, el concreto contribuye
        """
        self.b = b
        self.d = d
        self.fc = fc
        self.fy = fy
        self.Vd = Vd
        self.Vl = Vl
        self.f_corte_permite_concreto = f_corte_permite_concreto
        self.resultados = {}

    def _cortante_ultimo(self):
        """Vu = 1.4·Vd + 1.7·Vl [ton]"""
        return 1.4 * self.Vd + 1.7 * self.Vl

    def _cortante_concreto(self):
        """
        NTP E.060 Art. 11.3.1.1
        Vc = 0.53·√f'c·b·d [kg]
        """
        Vc_kg = 0.53 * math.sqrt(self.fc) * self.b * self.d
        return Vc_kg / 1000  # Convertir a toneladas

    def _cortante_acero_requerido(self, Vu):
        """
        NTP E.060 Art. 11.2.1.1
        Vs = (Vu/φ - Vc)

        donde φ = 0.85 (factor de reducción a cortante)
        Si Vs < 0 → solo se necesita acero mínimo
        """
        phi_v = 0.85
        Vc = self._cortante_concreto()

        Vs = (Vu / phi_v) - Vc

        return max(Vs, 0)

    def _espaciamiento_estribo(self, Av, Vs):
        """
        NTP E.060 Art. 11.5.6.2
        s = Av·fy·d / Vs [cm]
        
        Limitaciones:
          - s_max = d/2 si Vs ≤ √f'c·b·d / 8
          - s_max = d/4 si Vs > √f'c·b·d / 8
          - s_max ≥ 15 cm
        """
        if Vs <= 0:
            return 30.0  # Acero mínimo a 30 cm

        s = (Av * self.fy * self.d) / (Vs * 1000)

        # Límites por norma
        umbral = math.sqrt(self.fc) * self.b * self.d / 8 / 1000  # en ton
        
        if Vs <= umbral:
            s_max = self.d / 2
        else:
            s_max = self.d / 4

        s = min(s, s_max)
        s = max(s, 15.0)  # Mínimo 15 cm

        return s

    def _acero_minimo_corte(self):
        """
        NTP E.060 Art. 11.5.5.1
        Av_min = 0.2·√f'c·b·s / fy  (para s > d/4)
        Av_min = 0.35·b·s / fy      (siempre)
        
        Se retorna Av para s = 30 cm (acero mínimo típico)
        """
        s_min = 30.0
        Av1 = (0.2 * math.sqrt(self.fc) * self.b * s_min) / self.fy
        Av2 = (0.35 * self.b * s_min) / self.fy
        return max(Av1, Av2)

    def calcular(self, Vd=None, Vl=None):
        """Calcula el diseño de corte."""
        if Vd is not None:
            self.Vd = Vd
        if Vl is not None:
            self.Vl = Vl

        r = {}

        r['b'] = self.b
        r['d'] = self.d
        r['fc'] = self.fc
        r['fy'] = self.fy
        r['Vd'] = self.Vd
        r['Vl'] = self.Vl

        # Cortante
        Vu = self._cortante_ultimo()
        r['Vu'] = Vu
        r['Vu_kg'] = Vu * 1000

        Vc = self._cortante_concreto()
        r['Vc'] = Vc
        r['Vc_kg'] = Vc * 1000

        # Cortante en acero
        Vs = self._cortante_acero_requerido(Vu)
        r['Vs'] = Vs
        r['Vs_kg'] = Vs * 1000

        # Acero mínimo
        Av_min = self._acero_minimo_corte()
        r['Av_min'] = Av_min
        r['s_acero_minimo'] = 30.0

        # Sugerencia de estribos
        r['estribos'] = []
        for nombre, datos in self.ESTRIBOS.items():
            Av = 2 * datos['area']  # 2 ramas (estribo cerrado)
            s = self._espaciamiento_estribo(Av, Vs)
            r['estribos'].append({
                'estribo': nombre,
                'Av': Av,
                's': s,
            })

        # Verificación
        r['necesita_acero'] = Vs > 0

        self.resultados = r
        return r


# ===========================================================================
# MÓDULO DE GENERACIÓN DE GRÁFICOS
# ===========================================================================

class GraficosViga:
    """Genera visualizaciones de la viga y sus aceros."""

    def __init__(self, b, h, d, r, varillas_info=None, estribos_info=None):
        """
        b, h: base y altura de la sección [cm]
        d: peralte efectivo [cm]
        r: recubrimiento [cm]
        varillas_info: list de dicts con 'n_barras', 'd_barra', 'varilla'
        estribos_info: dict con 'estribo', 's'
        """
        self.b = b
        self.h = h
        self.d = d
        self.r = r
        self.varillas_info = varillas_info or {}
        self.estribos_info = estribos_info or {}

    def dibujar_seccion_transversal(self):
        """Dibuja la sección transversal de la viga con refuerzo longitudinal."""
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(1, 1, figsize=(8, 6))

        # Concreto
        concreto = patches.Rectangle((0, 0), self.b, self.h,
                                     linewidth=2, edgecolor='black',
                                     facecolor='#D3D3D3', alpha=0.3)
        ax.add_patch(concreto)

        # Recubrimiento (zona punteada)
        recub_top = patches.Rectangle((0, self.h - self.r), self.b, self.r,
                                      linewidth=1, edgecolor='gray',
                                      facecolor='none', linestyle='--', alpha=0.5)
        ax.add_patch(recub_top)

        recub_bot = patches.Rectangle((0, 0), self.b, self.r,
                                      linewidth=1, edgecolor='gray',
                                      facecolor='none', linestyle='--', alpha=0.5)
        ax.add_patch(recub_bot)

        # Barras longitudinales inferiores
        if self.varillas_info:
            var_info = self.varillas_info
            n_barras = var_info.get('n_barras', 3)
            d_barra = var_info.get('d_barra', 1.588)

            # Espaciado uniforme
            x_positions = [self.b * (i + 1) / (n_barras + 1) for i in range(n_barras)]
            y_pos = self.r + d_barra / 2

            for x in x_positions:
                circle = patches.Circle((x, y_pos), d_barra / 2,
                                       linewidth=1.5, edgecolor='red',
                                       facecolor='#FF6B6B', alpha=0.8)
                ax.add_patch(circle)

            # Barras superiores (la mitad del refuerzo)
            n_superior = max(2, n_barras // 2)
            x_sup = [self.b * (i + 1) / (n_superior + 1) for i in range(n_superior)]
            y_sup = self.h - self.r - d_barra / 2

            for x in x_sup:
                circle = patches.Circle((x, y_sup), d_barra / 2,
                                       linewidth=1.5, edgecolor='blue',
                                       facecolor='#4169E1', alpha=0.6)
                ax.add_patch(circle)

        # Eje neutro estimado
        c_estim = self.h * 0.3  # Aproximación
        ax.plot([0, self.b], [c_estim, c_estim], 'k--', linewidth=1, alpha=0.3)
        ax.text(self.b + 1, c_estim, f'E.N. ≈ {c_estim:.1f} cm', fontsize=8)

        # Dimensiones
        ax.annotate('', xy=(self.b + 2, 0), xytext=(self.b + 2, self.h),
                   arrowprops=dict(arrowstyle='<->', color='black', lw=1))
        ax.text(self.b + 3, self.h / 2, f'h = {self.h:.0f} cm', fontsize=9, va='center')

        ax.annotate('', xy=(0, -2), xytext=(self.b, -2),
                   arrowprops=dict(arrowstyle='<->', color='black', lw=1))
        ax.text(self.b / 2, -3.5, f'b = {self.b:.0f} cm', fontsize=9, ha='center')

        # Leyenda
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#FF6B6B', edgecolor='red', label='Acero inferior (tracción)'),
            Patch(facecolor='#4169E1', edgecolor='blue', label='Acero superior (compresión)'),
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=8)

        ax.set_xlim(-5, self.b + 8)
        ax.set_ylim(-5, self.h + 3)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.2)
        ax.set_xlabel('Base [cm]', fontsize=9)
        ax.set_ylabel('Altura [cm]', fontsize=9)
        ax.set_title('Sección Transversal - Refuerzo Longitudinal', fontsize=11, fontweight='bold')

        plt.tight_layout()
        return fig

    def dibujar_vista_lateral_corte(self, L=500):
        """Dibuja la vista lateral con distribución de estribos."""
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(1, 1, figsize=(10, 4))

        # Viga
        viga = patches.Rectangle((0, 0), L, self.h,
                                 linewidth=2, edgecolor='black',
                                 facecolor='#D3D3D3', alpha=0.3)
        ax.add_patch(viga)

        # Distribución de estribos
        if self.estribos_info:
            s = self.estribos_info.get('s', 30)
            estribo_name = self.estribos_info.get('estribo', '3/8"')

            x_pos = 0
            estribos_dibujados = 0
            while x_pos < L and estribos_dibujados < 12:
                # Línea vertical para estribo
                ax.plot([x_pos, x_pos], [0, self.h], 'b-', linewidth=2)
                estribos_dibujados += 1
                x_pos += s

        # Dimensiones
        ax.annotate('', xy=(0, -20), xytext=(L, -20),
                   arrowprops=dict(arrowstyle='<->', color='black', lw=1))
        ax.text(L / 2, -35, f'L ≈ {L} cm', fontsize=10, ha='center', fontweight='bold')

        ax.annotate('', xy=(L + 10, 0), xytext=(L + 10, self.h),
                   arrowprops=dict(arrowstyle='<->', color='black', lw=1))
        ax.text(L + 30, self.h / 2, f'h = {self.h:.0f} cm', fontsize=9, va='center')

        # Leyenda
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#D3D3D3', edgecolor='black', label='Concreto'),
            plt.Line2D([0], [0], color='b', linewidth=2, label=f'Estribos ϕ{self.estribos_info.get("estribo", "3/8")} @ {self.estribos_info.get("s", 30):.0f} cm'),
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=8)

        ax.set_xlim(-50, L + 50)
        ax.set_ylim(-50, self.h + 10)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.2, axis='x')
        ax.set_xlabel('Longitud [cm]', fontsize=9)
        ax.set_title('Vista Lateral - Distribución de Estribos', fontsize=11, fontweight='bold')
        ax.set_yticks([])

        plt.tight_layout()
        return fig


# ===========================================================================
# MÓDULO DE GENERACIÓN DE REPORTES PDF
# ===========================================================================

class GeneradorPDF:
    """Genera reportes PDF con resultados de diseño."""

    def __init__(self, filename="reporte_viga.pdf"):
        self.filename = filename
        self.doc = None
        self.story = []

    def crear_reporte(self, resultados_flexion, resultados_corte=None, 
                     figuras=None):
        """
        Crea un PDF con todos los resultados.

        resultados_flexion: dict con resultados de DisenoViga.calcular()
        resultados_corte: dict con resultados de DisenoCorte.calcular()
        figuras: dict con matplotlib figures {'seccion': fig1, 'lateral': fig2}
        """
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError(
                "reportlab no está instalado. "
                "Instala con: pip install reportlab"
            )

        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage

        # Crear documento
        self.doc = SimpleDocTemplate(
            self.filename,
            pagesize=letter,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
        )

        self.story = []

        # Encabezado
        self._agregar_encabezado()

        # Datos de entrada
        self._agregar_datos_entrada(resultados_flexion)

        # Diseño de flexión
        self._agregar_diseno_flexion(resultados_flexion)

        # Diseño de corte
        if resultados_corte:
            self.story.append(PageBreak())
            self._agregar_diseno_corte(resultados_corte)

        # Gráficos
        if figuras and MATPLOTLIB_AVAILABLE:
            self.story.append(PageBreak())
            self._agregar_graficos(figuras)

        # Pie
        self._agregar_pie()

        # Guardar
        self.doc.build(self.story)

    def _agregar_encabezado(self):
        """Encabezado del reporte."""
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import Paragraph, Spacer

        style_titulo = ParagraphStyle(
            'CustomTitle',
            parent=getSampleStyleSheet()['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1A2332'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        style_subtitulo = ParagraphStyle(
            'CustomSubtitle',
            parent=getSampleStyleSheet()['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#2E86AB'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )

        self.story.append(
            Paragraph("DISEÑO DE VIGA DE CONCRETO REFORZADO", style_titulo)
        )
        self.story.append(
            Paragraph(f"Norma: NTP E.060 / ACI 318 — {datetime.now().strftime('%d/%m/%Y')}", 
                     style_subtitulo)
        )
        self.story.append(Spacer(1, 0.2 * inch))

    def _agregar_datos_entrada(self, r):
        """Tabla de datos de entrada."""
        from reportlab.platypus import Table, TableStyle

        data = [
            ['Parámetro', 'Valor', 'Unidad'],
            ['Base (b)', f"{r['b']:.2f}", 'cm'],
            ['Altura total (h)', f"{r['h']:.2f}", 'cm'],
            ['Peralte efectivo (d)', f"{r['d']:.2f}", 'cm'],
            ['Recubrimiento (r)', f"{r['r']:.2f}", 'cm'],
            ['Luz libre (L)', f"{r['L']:.2f}", 'm'],
            ["Resistencia concreto (f'c)", f"{r['fc']:.0f}", 'kg/cm²'],
            ['Fluencia acero (fy)', f"{r['fy']:.0f}", 'kg/cm²'],
            ['Momento carga muerta (Md)', f"{r['Md']:.3f}", 'ton·m'],
            ['Momento carga viva (Ml)', f"{r['Ml']:.3f}", 'ton·m'],
        ]

        table = Table(data, colWidths=[3.5 * cm, 2 * cm, 2 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))

        self.story.append(Paragraph('<b>1. DATOS DE ENTRADA</b>', 
                                   getSampleStyleSheet()['Heading2']))
        self.story.append(Spacer(1, 0.15 * inch))
        self.story.append(table)
        self.story.append(Spacer(1, 0.3 * inch))

    def _agregar_diseno_flexion(self, r):
        """Sección de diseño de flexión."""
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

        self.story.append(Paragraph('<b>2. DISEÑO DE FLEXIÓN</b>',
                                   getSampleStyleSheet()['Heading2']))
        self.story.append(Spacer(1, 0.1 * inch))

        # Momento último
        data = [
            ['Concepto', 'Valor'],
            ['Momento último (Mu)', f"{r['Mu']:.4f} ton·m"],
            ['β₁ (Factor Whitney)', f"{r['beta1']:.4f}"],
            ['As requerido', f"{r['As_req']:.3f} cm²"],
            ['Cuantía requerida', f"{r['rho_req']*100:.4f} %"],
            ['As mínimo', f"{r['As_min']:.3f} cm²"],
            ['As máximo', f"{r['As_max']:.3f} cm²"],
            ['As diseño (final)', f"{r['As_diseno']:.3f} cm²"],
            ['Profundidad bloque (a)', f"{r['a']:.4f} cm"],
            ['Deformación acero (εt)', f"{r['epsilon_t']:.6f}"],
        ]

        table = Table(data, colWidths=[4.5 * cm, 2.5 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8A020')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        self.story.append(table)
        self.story.append(Spacer(1, 0.2 * inch))

        # Verificaciones
        checks = r['verificaciones']
        verif_data = [['Verificación', 'Estado']]
        for clave, check in checks.items():
            estado = '✓ CUMPLE' if check['cumple'] else '✗ NO CUMPLE'
            verif_data.append([check['descripcion'], estado])

        if r['cumple_cuantia_maxima']:
            verif_data.append(['Cuantía máxima', '✓ CUMPLE'])
        else:
            verif_data.append(['Cuantía máxima', '✗ NO CUMPLE'])

        if r['cumple_ductilidad']:
            verif_data.append(['Falla dúctil (εt≥0.004)', '✓ CUMPLE'])
        else:
            verif_data.append(['Falla dúctil (εt≥0.004)', '✗ NO CUMPLE'])

        verif_table = Table(verif_data, colWidths=[4.5 * cm, 2.5 * cm])
        verif_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27AE60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        self.story.append(Paragraph('<i>Verificaciones</i>',
                                   getSampleStyleSheet()['Normal']))
        self.story.append(Spacer(1, 0.1 * inch))
        self.story.append(verif_table)
        self.story.append(Spacer(1, 0.2 * inch))

        # Sugerencia de varillas
        self.story.append(Paragraph('<i>Sugerencia de Varillas Comerciales</i>',
                                   getSampleStyleSheet()['Normal']))
        self.story.append(Spacer(1, 0.1 * inch))

        varillas_data = [['Varilla', 'Cantidad', 'As Provisto', 'Cabe en Base']]
        for v in r['varillas']:
            cabe = '✓ Sí' if v['cabe_en_base'] else '✗ No'
            varillas_data.append([
                f"ϕ {v['varilla']}",
                str(v['n_barras']),
                f"{v['As_provisto']:.3f} cm²",
                cabe
            ])

        varillas_table = Table(varillas_data, colWidths=[1.5 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm])
        varillas_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E74C3C')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        self.story.append(varillas_table)
        self.story.append(Spacer(1, 0.3 * inch))

    def _agregar_diseno_corte(self, r):
        """Sección de diseño de corte."""
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

        self.story.append(Paragraph('<b>3. DISEÑO DE CORTE (NTP E.060 Art. 11)</b>',
                                   getSampleStyleSheet()['Heading2']))
        self.story.append(Spacer(1, 0.1 * inch))

        data = [
            ['Concepto', 'Valor'],
            ['Cortante último (Vu)', f"{r['Vu']:.4f} ton"],
            ['Cortante concreto (Vc)', f"{r['Vc']:.4f} ton"],
            ['Cortante acero (Vs)', f"{r['Vs']:.4f} ton"],
            ['Necesita acero', 'Sí' if r['necesita_acero'] else 'No'],
            ['Acero mínimo (Av min)', f"{r['Av_min']:.3f} cm²"],
        ]

        table = Table(data, colWidths=[4.5 * cm, 2.5 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        self.story.append(table)
        self.story.append(Spacer(1, 0.2 * inch))

        # Estribos sugeridos
        self.story.append(Paragraph('<i>Estribos Sugeridos</i>',
                                   getSampleStyleSheet()['Normal']))
        self.story.append(Spacer(1, 0.1 * inch))

        estribos_data = [['Estribo', 'Área (Av)', 'Espaciamiento']]
        for e in r['estribos']:
            estribos_data.append([
                f"ϕ {e['estribo']}",
                f"{e['Av']:.3f} cm²",
                f"{e['s']:.1f} cm"
            ])

        estribos_table = Table(estribos_data, colWidths=[2 * cm, 2.5 * cm, 3 * cm])
        estribos_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8A020')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        self.story.append(estribos_table)
        self.story.append(Spacer(1, 0.3 * inch))

    def _agregar_graficos(self, figuras):
        """Agrega gráficos al reporte."""
        from reportlab.platypus import Paragraph, Spacer

        self.story.append(Paragraph('<b>4. DIAGRAMAS Y GRÁFICOS</b>',
                                   getSampleStyleSheet()['Heading2']))
        self.story.append(Spacer(1, 0.1 * inch))

        for titulo, fig in figuras.items():
            if fig is None:
                continue

            # Convertir matplotlib figure a imagen en memoria
            buf = BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)

            img = RLImage(buf, width=7 * inch, height=4 * inch)
            self.story.append(img)
            self.story.append(Spacer(1, 0.2 * inch))

            plt.close(fig)

    def _agregar_pie(self):
        """Pie del reporte."""
        from reportlab.platypus import Paragraph, Spacer

        self.story.append(Spacer(1, 0.3 * inch))
        pie_style = ParagraphStyle(
            'Pie',
            parent=getSampleStyleSheet()['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER,
        )

        self.story.append(
            Paragraph(
                "⚠ Este reporte es de pre-dimensionamiento. Verifique siempre con un "
                "ingeniero estructural habilitado antes de ejecutar cualquier obra.<br/>"
                f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                pie_style
            )
        )


# ===========================================================================
# MÓDULO DE INTERFAZ GRÁFICA (Tkinter)
# ===========================================================================

class AppVigas(tk.Tk):
    """
    Aplicación de escritorio para el diseño de vigas de concreto reforzado.
    """

    COLORES = {
        'fondo':       '#1A2332',
        'panel':       '#243447',
        'acento':      '#E8A020',
        'acento2':     '#2E86AB',
        'texto':       '#E8EDF2',
        'texto_dim':   '#8A9BB0',
        'exito':       '#27AE60',
        'error':       '#E74C3C',
        'advertencia': '#F39C12',
        'borde':       '#3A5068',
        'entrada_bg':  '#0F1923',
    }

    def __init__(self):
        super().__init__()
        self.title("Diseño de Vigas — NTP E.060 v3.0")
        self.geometry("1200x800")
        self.resizable(True, True)
        self.configure(bg=self.COLORES['fondo'])
        self._configurar_estilos()
        self._construir_ui()

    # -----------------------------------------------------------------------
    # CONFIGURACIÓN DE ESTILOS
    # -----------------------------------------------------------------------
    def _configurar_estilos(self):
        style = ttk.Style(self)
        style.theme_use('clam')

        style.configure('Panel.TFrame', background=self.COLORES['panel'])
        style.configure('Fondo.TFrame', background=self.COLORES['fondo'])

        style.configure('Titulo.TLabel',
                        background=self.COLORES['fondo'],
                        foreground=self.COLORES['acento'],
                        font=('Segoe UI', 15, 'bold'))

        style.configure('Subtitulo.TLabel',
                        background=self.COLORES['panel'],
                        foreground=self.COLORES['acento2'],
                        font=('Segoe UI', 10, 'bold'))

        style.configure('Campo.TLabel',
                        background=self.COLORES['panel'],
                        foreground=self.COLORES['texto'],
                        font=('Segoe UI', 9))

        style.configure('Unidad.TLabel',
                        background=self.COLORES['panel'],
                        foreground=self.COLORES['texto_dim'],
                        font=('Segoe UI', 9, 'italic'))

        style.configure('Resultado.TLabel',
                        background=self.COLORES['fondo'],
                        foreground=self.COLORES['texto'],
                        font=('Consolas', 9))

        style.configure('Calcular.TButton',
                        background=self.COLORES['acento'],
                        foreground='#1A2332',
                        font=('Segoe UI', 11, 'bold'),
                        relief='flat',
                        padding=(20, 10))
        style.map('Calcular.TButton',
                  background=[('active', '#F5B833'), ('pressed', '#C88510')])

        style.configure('Limpiar.TButton',
                        background=self.COLORES['acento2'],
                        foreground='white',
                        font=('Segoe UI', 10),
                        relief='flat',
                        padding=(15, 8))
        style.map('Limpiar.TButton',
                  background=[('active', '#3A9DC0'), ('pressed', '#1A6080')])

        style.configure('PDF.TButton',
                        background=self.COLORES['exito'],
                        foreground='white',
                        font=('Segoe UI', 10),
                        relief='flat',
                        padding=(15, 8))
        style.map('PDF.TButton',
                  background=[('active', '#229954'), ('pressed', '#0E6251')])

        style.configure('Graficos.TButton',
                        background=self.COLORES['advertencia'],
                        foreground='white',
                        font=('Segoe UI', 10),
                        relief='flat',
                        padding=(15, 8))
        style.map('Graficos.TButton',
                  background=[('active', '#E67E22'), ('pressed', '#B8601E')])

        style.configure('TSeparator', background=self.COLORES['borde'])

    # -----------------------------------------------------------------------
    # CONSTRUCCIÓN DE LA INTERFAZ
    # -----------------------------------------------------------------------
    def _construir_ui(self):
        # Encabezado
        header = tk.Frame(self, bg=self.COLORES['fondo'], pady=12)
        header.pack(fill='x', padx=20)

        tk.Label(header,
                 text="⚙  DISEÑO DE VIGAS — CONCRETO REFORZADO v3.0",
                 bg=self.COLORES['fondo'],
                 fg=self.COLORES['acento'],
                 font=('Segoe UI', 16, 'bold')).pack(side='left')

        tk.Label(header,
                 text="NTP E.060  |  ACI 318  |  Flexión + Corte + Gráficos + PDF",
                 bg=self.COLORES['fondo'],
                 fg=self.COLORES['texto_dim'],
                 font=('Segoe UI', 9)).pack(side='right', pady=4)

        ttk.Separator(self, orient='horizontal').pack(fill='x', padx=20)

        # Contenedor principal
        contenedor = ttk.Frame(self, style='Fondo.TFrame')
        contenedor.pack(fill='both', expand=True, padx=20, pady=10)

        contenedor.columnconfigure(0, weight=0, minsize=350)
        contenedor.columnconfigure(1, weight=1)
        contenedor.rowconfigure(0, weight=1)

        # Panel izquierdo (formulario)
        self._panel_formulario(contenedor)

        # Panel derecho (resultados + pestaña de gráficos)
        self._panel_derecho(contenedor)

    def _panel_formulario(self, parent):
        """Construye el panel de entrada de datos."""
        frame = tk.Frame(parent, bg=self.COLORES['panel'],
                         bd=0, relief='flat')
        frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10), pady=2)

        tk.Label(frame, text="  DATOS DE ENTRADA",
                 bg=self.COLORES['acento2'],
                 fg='white',
                 font=('Segoe UI', 10, 'bold'),
                 anchor='w', pady=6).pack(fill='x')

        scroll_frame = tk.Frame(frame, bg=self.COLORES['panel'])
        scroll_frame.pack(fill='both', expand=True, padx=12, pady=8)

        self.vars = {}

        # Sección Geometría
        self._seccion(scroll_frame, "📐 GEOMETRÍA DE LA SECCIÓN")
        campos_geo = [
            ('b',    'Base de la viga (b)',          'cm',   '30'),
            ('h',    'Altura total (h)',              'cm',   '60'),
            ('r',    'Recubrimiento libre (r)',       'cm',   '4'),
            ('L',    'Luz libre de la viga (L)',      'm',    '5.0'),
        ]
        for clave, etq, unidad, defecto in campos_geo:
            self._campo_entrada(scroll_frame, clave, etq, unidad, defecto)

        # Sección Materiales
        self._seccion(scroll_frame, "🔩 PROPIEDADES DE MATERIALES")
        campos_mat = [
            ('fc', "Resistencia concreto (f'c)", 'kg/cm²', '210'),
            ('fy', "Fluencia del acero (fy)",     'kg/cm²', '4200'),
        ]
        for clave, etq, unidad, defecto in campos_mat:
            self._campo_entrada(scroll_frame, clave, etq, unidad, defecto)

        tk.Label(scroll_frame, text="  Preset f'c:",
                 bg=self.COLORES['panel'], fg=self.COLORES['texto_dim'],
                 font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 2))
        frame_presets = tk.Frame(scroll_frame, bg=self.COLORES['panel'])
        frame_presets.pack(fill='x', pady=(0, 6))
        for fc_val in ['175', '210', '245', '280']:
            tk.Button(frame_presets, text=f"f'c={fc_val}",
                      bg=self.COLORES['borde'],
                      fg=self.COLORES['texto'],
                      font=('Segoe UI', 8),
                      relief='flat', cursor='hand2',
                      command=lambda v=fc_val: self.vars['fc'].set(v)
                      ).pack(side='left', padx=2)

        # Sección Cargas
        self._seccion(scroll_frame, "⚖  CARGAS ACTUANTES")
        campos_carga = [
            ('Md', 'Momento carga muerta (Md)',   'ton·m', '10.0'),
            ('Ml', 'Momento carga viva (Ml)',     'ton·m', '8.0'),
            ('Vd', 'Cortante carga muerta (Vd)',  'ton',   '8.0'),
            ('Vl', 'Cortante carga viva (Vl)',    'ton',   '6.0'),
        ]
        for clave, etq, unidad, defecto in campos_carga:
            self._campo_entrada(scroll_frame, clave, etq, unidad, defecto)

        # Botones
        frame_btns = tk.Frame(frame, bg=self.COLORES['panel'])
        frame_btns.pack(fill='x', padx=12, pady=10)

        ttk.Button(frame_btns, text="▶  CALCULAR",
                   style='Calcular.TButton',
                   command=self._calcular).pack(fill='x', pady=(0, 4))

        btn_frame = tk.Frame(frame_btns, bg=self.COLORES['panel'])
        btn_frame.pack(fill='x', pady=(0, 4))

        ttk.Button(btn_frame, text="📊 Gráficos",
                   style='Graficos.TButton',
                   command=self._mostrar_graficos).pack(side='left', fill='x', expand=True, padx=(0, 2))

        ttk.Button(btn_frame, text="💾 PDF",
                   style='PDF.TButton',
                   command=self._generar_pdf).pack(side='left', fill='x', expand=True, padx=(2, 0))

        ttk.Button(frame_btns, text="↺  Limpiar",
                   style='Limpiar.TButton',
                   command=self._limpiar).pack(fill='x')

    def _panel_derecho(self, parent):
        """Panel de resultados con pestañas."""
        # Crear notebook (pestañas)
        notebook = ttk.Notebook(parent)
        notebook.grid(row=0, column=1, sticky='nsew', pady=2)

        # Pestaña 1: Resultados
        frame_resultados = ttk.Frame(notebook, style='Fondo.TFrame')
        notebook.add(frame_resultados, text='  📋 Resultados  ')

        tk.Label(frame_resultados, text="  RESULTADOS DEL DISEÑO",
                 bg=self.COLORES['acento2'],
                 fg='white',
                 font=('Segoe UI', 10, 'bold'),
                 anchor='w', pady=6).pack(fill='x')

        txt_frame = tk.Frame(frame_resultados, bg=self.COLORES['fondo'])
        txt_frame.pack(fill='both', expand=True, pady=4)

        scrollbar = ttk.Scrollbar(txt_frame, orient='vertical')
        scrollbar.pack(side='right', fill='y')

        self.txt_resultado = tk.Text(
            txt_frame,
            bg=self.COLORES['entrada_bg'],
            fg=self.COLORES['texto'],
            font=('Consolas', 8),
            relief='flat',
            bd=4,
            wrap='word',
            state='disabled',
            yscrollcommand=scrollbar.set,
        )
        self.txt_resultado.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.txt_resultado.yview)

        # Etiquetas de color
        self.txt_resultado.tag_configure('titulo',
                                         font=('Consolas', 9, 'bold'),
                                         foreground=self.COLORES['acento'])
        self.txt_resultado.tag_configure('ok',
                                         foreground=self.COLORES['exito'])
        self.txt_resultado.tag_configure('error',
                                         foreground=self.COLORES['error'])
        self.txt_resultado.tag_configure('warn',
                                         foreground=self.COLORES['advertencia'])
        self.txt_resultado.tag_configure('valor',
                                         foreground=self.COLORES['acento'],
                                         font=('Consolas', 8, 'bold'))
        self.txt_resultado.tag_configure('dim',
                                         foreground=self.COLORES['texto_dim'])

        self._escribir_bienvenida()

        # Pestaña 2: Gráficos
        self.frame_graficos = ttk.Frame(notebook, style='Fondo.TFrame')
        notebook.add(self.frame_graficos, text='  📊 Gráficos  ')

        tk.Label(self.frame_graficos, text="  DIAGRAMAS Y VISUALIZACIONES",
                 bg=self.COLORES['acento2'],
                 fg='white',
                 font=('Segoe UI', 10, 'bold'),
                 anchor='w', pady=6).pack(fill='x')

        self.canvas_graficos = None

    # -----------------------------------------------------------------------
    # MÉTODOS AUXILIARES DE UI
    # -----------------------------------------------------------------------
    def _seccion(self, parent, titulo):
        """Inserta un encabezado de sección."""
        tk.Label(parent, text=titulo,
                 bg=self.COLORES['panel'],
                 fg=self.COLORES['acento'],
                 font=('Segoe UI', 9, 'bold'),
                 pady=6).pack(anchor='w')
        tk.Frame(parent, bg=self.COLORES['borde'], height=1).pack(fill='x', pady=(0, 6))

    def _campo_entrada(self, parent, clave, etiqueta, unidad, defecto):
        """Crea una fila de entrada."""
        row = tk.Frame(parent, bg=self.COLORES['panel'])
        row.pack(fill='x', pady=2)

        tk.Label(row, text=etiqueta,
                 bg=self.COLORES['panel'],
                 fg=self.COLORES['texto'],
                 font=('Segoe UI', 8),
                 width=33, anchor='w').pack(side='left')

        var = tk.StringVar(value=defecto)
        self.vars[clave] = var

        entry = tk.Entry(row, textvariable=var,
                         bg=self.COLORES['entrada_bg'],
                         fg=self.COLORES['acento'],
                         insertbackground=self.COLORES['acento'],
                         relief='flat',
                         font=('Consolas', 9, 'bold'),
                         width=8,
                         justify='right')
        entry.pack(side='left', padx=4)

        tk.Label(row, text=unidad,
                 bg=self.COLORES['panel'],
                 fg=self.COLORES['texto_dim'],
                 font=('Segoe UI', 7, 'italic')).pack(side='left')

    def _limpiar_resultados(self):
        self.txt_resultado.config(state='normal')
        self.txt_resultado.delete('1.0', 'end')

    def _escribir(self, texto, tag=None):
        self.txt_resultado.config(state='normal')
        if tag:
            self.txt_resultado.insert('end', texto, tag)
        else:
            self.txt_resultado.insert('end', texto)
        self.txt_resultado.config(state='disabled')

    def _nl(self):
        self._escribir('\n')

    def _escribir_bienvenida(self):
        self._limpiar_resultados()
        self._nl()
        self._escribir("  Ingrese los datos y presione ▶ CALCULAR.\n\n", 'dim')
        self._escribir("  Características v3.0:\n", 'dim')
        items = [
            "  • Diseño de flexión (NTP E.060)",
            "  • Diseño de corte y estribos",
            "  • Sugerencia de varillas comerciales",
            "  • Verificaciones dimensionales",
            "  • Visualización gráfica de acero",
            "  • Generación de reportes PDF",
        ]
        for item in items:
            self._escribir(item + '\n', 'dim')
        self._nl()

    # -----------------------------------------------------------------------
    # LÓGICA DE CÁLCULO
    # -----------------------------------------------------------------------
    def _leer_float(self, clave, nombre, minimo=0.001):
        """Lee y valida un campo numérico."""
        try:
            valor = float(self.vars[clave].get().replace(',', '.'))
        except ValueError:
            raise ValueError(f"El campo '{nombre}' debe ser un número.")
        if valor <= minimo:
            raise ValueError(f"El campo '{nombre}' debe ser mayor que {minimo}.")
        return valor

    def _limpiar(self):
        defaults = {
            'b': '30', 'h': '60', 'r': '4', 'L': '5.0',
            'fc': '210', 'fy': '4200', 'Md': '10.0', 'Ml': '8.0',
            'Vd': '8.0', 'Vl': '6.0'
        }
        for k, v in defaults.items():
            if k in self.vars:
                self.vars[k].set(v)
        self._escribir_bienvenida()

    def _calcular(self):
        """Calcula diseño de flexión y corte."""
        try:
            b  = self._leer_float('b',  'Base (b)',             0)
            h  = self._leer_float('h',  'Altura (h)',           0)
            r  = self._leer_float('r',  'Recubrimiento (r)',    0)
            L  = self._leer_float('L',  'Luz libre (L)',        0)
            fc = self._leer_float('fc', "f'c",                  0)
            fy = self._leer_float('fy', 'fy',                   0)
            Md = self._leer_float('Md', 'Momento muerto (Md)',  0)
            Ml = self._leer_float('Ml', 'Momento vivo (Ml)',    0)
            Vd = self._leer_float('Vd', 'Cortante muerto (Vd)', 0)
            Vl = self._leer_float('Vl', 'Cortante vivo (Vl)',   0)
        except ValueError as e:
            messagebox.showerror("Error de entrada", str(e))
            return

        try:
            # Flexión
            viga = DisenoViga(b, h, L, fc, fy, Md, Ml, r)
            self.res_flexion = viga.calcular()

            # Corte
            corte = DisenoCorte(b, self.res_flexion['d'], fc, fy, Vd, Vl)
            self.res_corte = corte.calcular()

        except ValueError as e:
            messagebox.showerror("Error en el cálculo", str(e))
            return

        self._mostrar_resultados()

    def _mostrar_resultados(self):
        """Muestra los resultados en el área de texto."""
        self._limpiar_resultados()
        r = self.res_flexion
        rc = self.res_corte

        # Encabezado
        self._escribir("\n  ╔════════════════════════════════════════╗\n", 'dim')
        self._escribir("  ║  DISEÑO DE VIGA — NTP E.060 v3.0     ║\n", 'titulo')
        self._escribir("  ╚════════════════════════════════════════╝\n\n", 'dim')

        # FLEXIÓN
        self._escribir("  [FLEXIÓN]\n", 'titulo')
        self._escribir("  " + "─" * 40 + "\n", 'dim')
        self._escribir(f"  Mu = {r['Mu']:.3f} ton·m  |  As = {r['As_diseno']:.2f} cm²\n", 'valor')
        self._escribir(f"  Peralte (d) = {r['d']:.2f} cm  |  Profundidad bloque (a) = {r['a']:.2f} cm\n\n", 'dim')

        # Verificaciones flexión
        checks_ok = sum(1 for c in r['verificaciones'].values() if c['cumple'])
        checks_total = len(r['verificaciones'])
        self._escribir(f"  Verificaciones: {checks_ok}/{checks_total} ✓\n", 'ok' if checks_ok == checks_total else 'error')
        self._escribir(f"  Ductilidad: {'✓' if r['cumple_ductilidad'] else '✗'} | ", 'ok' if r['cumple_ductilidad'] else 'error')
        self._escribir(f"Cuantía máx: {'✓' if r['cumple_cuantia_maxima'] else '✗'}\n\n", 'ok' if r['cumple_cuantia_maxima'] else 'error')

        # Varillas
        self._escribir("  Varillas comerciales sugeridas:\n", 'dim')
        opciones_validas = [v for v in r['varillas'] if v['cabe_en_base']]
        if opciones_validas:
            mejor = min(opciones_validas, key=lambda x: x['diferencia'])
            self._escribir(f"    ★ {mejor['n_barras']} ϕ {mejor['varilla']} → As = {mejor['As_provisto']:.2f} cm²\n", 'ok')
        self._nl()

        # CORTE
        self._escribir("  [CORTE]\n", 'titulo')
        self._escribir("  " + "─" * 40 + "\n", 'dim')
        self._escribir(f"  Vu = {rc['Vu']:.3f} ton  |  Vc = {rc['Vc']:.3f} ton  |  Vs = {rc['Vs']:.3f} ton\n", 'valor')
        self._escribir(f"  Acero requerido: {'Sí ✓' if rc['necesita_acero'] else 'Mínimo'}\n\n", 'ok' if rc['necesita_acero'] else 'dim')

        # Estribos
        self._escribir("  Estribos sugeridos:\n", 'dim')
        for e in rc['estribos']:
            self._escribir(f"    • ϕ {e['estribo']} @ {e['s']:.1f} cm\n", 'dim')

        self._nl()
        self._escribir("  ⚠ Verifique con ingeniero habilitado\n", 'warn')

        self.txt_resultado.config(state='normal')
        self.txt_resultado.see('1.0')
        self.txt_resultado.config(state='disabled')

    def _mostrar_graficos(self):
        """Muestra gráficos en la pestaña gráficos."""
        if not hasattr(self, 'res_flexion'):
            messagebox.showwarning("Advertencia", "Debe calcular primero (botón ▶ CALCULAR)")
            return

        if not MATPLOTLIB_AVAILABLE:
            messagebox.showerror("Error", "matplotlib no está instalado.\nInstale con: pip install matplotlib pillow")
            return

        r = self.res_flexion
        rc = self.res_corte

        # Obtener mejor opción de varillas
        opciones_validas = [v for v in r['varillas'] if v['cabe_en_base']]
        mejor_varilla = min(opciones_validas, key=lambda x: x['diferencia']) if opciones_validas else r['varillas'][0]

        mejor_estribo = rc['estribos'][0]

        # Crear gráficos
        grafico = GraficosViga(r['b'], r['h'], r['d'], r['r'],
                              varillas_info=mejor_varilla,
                              estribos_info=mejor_estribo)

        fig1 = grafico.dibujar_seccion_transversal()
        fig2 = grafico.dibujar_vista_lateral_corte(L=int(r['L'] * 100))

        # Limpiar frame de gráficos
        for widget in self.frame_graficos.winfo_children():
            if isinstance(widget, tk.Label) and "DIAGRAMAS" in widget.cget("text"):
                continue
            if not isinstance(widget, tk.Label):
                widget.destroy()

        # Crear frame para gráficos
        if fig1:
            canvas1 = FigureCanvasTkAgg(fig1, master=self.frame_graficos)
            canvas1.get_tk_widget().pack(fill='both', expand=True, padx=5, pady=5)

        if fig2:
            canvas2 = FigureCanvasTkAgg(fig2, master=self.frame_graficos)
            canvas2.get_tk_widget().pack(fill='both', expand=True, padx=5, pady=5)

        # Hacer visible la pestaña de gráficos
        notebook = self.frame_graficos.master
        notebook.select(1)  # Índice 1 es la pestaña de gráficos

    def _generar_pdf(self):
        """Genera un reporte PDF."""
        if not hasattr(self, 'res_flexion'):
            messagebox.showwarning("Advertencia", "Debe calcular primero (botón ▶ CALCULAR)")
            return

        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Error", "reportlab no está instalado.\nInstale con: pip install reportlab")
            return

        # Diálogo de guardado
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"reporte_viga_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )

        if not filename:
            return

        try:
            r = self.res_flexion
            rc = self.res_corte

            # Generar gráficos
            opciones_validas = [v for v in r['varillas'] if v['cabe_en_base']]
            mejor_varilla = min(opciones_validas, key=lambda x: x['diferencia']) if opciones_validas else r['varillas'][0]
            mejor_estribo = rc['estribos'][0]

            grafico = GraficosViga(r['b'], r['h'], r['d'], r['r'],
                                  varillas_info=mejor_varilla,
                                  estribos_info=mejor_estribo)

            figuras = {
                'Sección Transversal': grafico.dibujar_seccion_transversal(),
                'Vista Lateral - Corte': grafico.dibujar_vista_lateral_corte(int(r['L'] * 100))
            }

            # Generar PDF
            gen = GeneradorPDF(filename)
            gen.crear_reporte(r, rc, figuras)

            messagebox.showinfo("Éxito", f"PDF generado correctamente:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))


# ===========================================================================
# PUNTO DE ENTRADA
# ===========================================================================

if __name__ == '__main__':
    app = AppVigas()
    app.mainloop()
