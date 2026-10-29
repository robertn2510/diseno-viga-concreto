"""
Interfaz de escritorio (Tkinter) del sistema de diseño E.060 + ETABS.

Ejecución:
    python app_escritorio.py

Diseñada para Windows junto a ETABS v20–v23 (conexión COM/OAPI), pero funciona
también en Linux/macOS con el modelo demo o con tablas exportadas.

Compatible con Python 3.8 o superior (sin sintaxis de tipos modernos).
"""

from __future__ import annotations

import os
import sys
import traceback
import webbrowser
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

RAIZ = os.path.dirname(os.path.abspath(__file__))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from e060 import __version__, servicio                       # noqa: E402
from e060.etabs import ETABSTablas, ETABSDemo                # noqa: E402
from e060.memoria import construir_memoria, guardar_pdf      # noqa: E402

SALIDAS = os.path.join(RAIZ, "salidas")

COLOR_AZUL = "#1f3864"
COLOR_AZUL2 = "#2c5282"
COLOR_FONDO = "#eef2f7"
COLOR_OK = "#1f7a4d"
COLOR_MAL = "#c0392b"
COLOR_GRIS = "#63708a"


# ===========================================================================
# Utilidades
# ===========================================================================
def abrir_archivo(ruta):
    """Abre un archivo con la aplicación predeterminada del sistema."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(ruta)                       # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system('open "%s"' % ruta)
        else:
            webbrowser.open("file://" + os.path.abspath(ruta))
    except Exception:
        webbrowser.open("file://" + os.path.abspath(ruta))


def fmt(valor, dec=2):
    if valor is None:
        return "—"
    try:
        return ("{:,.%df}" % dec).format(float(valor))
    except (TypeError, ValueError):
        return str(valor)


# ===========================================================================
# Ventana principal
# ===========================================================================
class AppE060(tk.Tk):

    def __init__(self):
        tk.Tk.__init__(self)
        self.title("Diseño de Concreto Armado E.060 · Vigas y Columnas · ETABS 20–23")
        self.geometry("1360x820")
        self.minsize(1120, 700)
        self.configure(bg=COLOR_FONDO)

        self.fuente = None
        self.fuente_id = None
        self.elementos = []
        self.elemento_actual = None
        self.datos_elemento = None
        self.salida = None
        self.memoria_doc = None

        self.var = {
            "fuente": tk.StringVar(value="Modelo demo"),
            "buscar": tk.StringVar(),
            "filtro": tk.StringVar(value="Todos"),
            "tipo": tk.StringVar(value="auto"),
            "fc": tk.StringVar(value="210"),
            "fy": tk.StringVar(value="4200"),
            "b": tk.StringVar(),
            "h": tk.StringVar(),
            "rec": tk.StringVar(value="4.0"),
            "estribo": tk.StringVar(value='#3'),
            "nest": tk.StringVar(value="5"),
            "proyecto": tk.StringVar(value="Proyecto"),
            "ubicacion": tk.StringVar(value=""),
            "autor": tk.StringVar(value="Ing. Estructural"),
            "sismico": tk.BooleanVar(value=True),
            "torsion": tk.BooleanVar(value=True),
            "esbeltez": tk.BooleanVar(value=False),
            "capacidad": tk.BooleanVar(value=True),
            "estado": tk.StringVar(value="Listo."),
        }

        self._estilos()
        self._construir()
        self.cargar_demo()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    # ------------------------------------------------------------------
    def _estilos(self):
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure(".", font=("Segoe UI", 9), background=COLOR_FONDO)
        estilo.configure("TFrame", background=COLOR_FONDO)
        estilo.configure("TLabel", background=COLOR_FONDO, foreground="#1b2430")
        estilo.configure("TLabelframe", background=COLOR_FONDO, bordercolor="#d8e0ea")
        estilo.configure("TLabelframe.Label", background=COLOR_FONDO,
                         foreground=COLOR_AZUL, font=("Segoe UI", 9, "bold"))
        estilo.configure("TButton", padding=(10, 5))
        estilo.configure("Accion.TButton", background=COLOR_AZUL, foreground="white",
                         font=("Segoe UI", 9, "bold"), padding=(14, 6))
        estilo.map("Accion.TButton", background=[("active", "#17294a")])
        estilo.configure("Sec.TButton", background="#ffffff", foreground=COLOR_AZUL)
        estilo.configure("Treeview", rowheight=23, fieldbackground="white",
                         background="white", font=("Segoe UI", 9))
        estilo.configure("Treeview.Heading", background=COLOR_AZUL, foreground="white",
                         font=("Segoe UI", 8, "bold"))
        estilo.map("Treeview", background=[("selected", "#dbe8f7")],
                   foreground=[("selected", "#12233d")])
        estilo.configure("TNotebook", background=COLOR_FONDO, borderwidth=0)
        estilo.configure("TNotebook.Tab", padding=(16, 8), font=("Segoe UI", 9))
        estilo.map("TNotebook.Tab", background=[("selected", "#ffffff")],
                   foreground=[("selected", COLOR_AZUL)])
        estilo.configure("TEntry", fieldbackground="white")
        estilo.configure("Header.TFrame", background=COLOR_AZUL)
        estilo.configure("Header.TLabel", background=COLOR_AZUL, foreground="white")
        estilo.configure("HeaderSub.TLabel", background=COLOR_AZUL, foreground="#c9d7ea")

    # ------------------------------------------------------------------
    def _construir(self):
        # -------- cabecera ------------------------------------------------
        cab = ttk.Frame(self, style="Header.TFrame")
        cab.pack(fill="x")
        tk.Label(cab, text="  E.060  ", bg="#ffffff", fg=COLOR_AZUL,
                 font=("Segoe UI", 12, "bold")).pack(side="left", padx=(10, 8), pady=10)
        caja = ttk.Frame(cab, style="Header.TFrame")
        caja.pack(side="left")
        ttk.Label(caja, text="Diseño de Concreto Armado · Vigas y Columnas",
                  style="Header.TLabel", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(caja, text="Norma Técnica Peruana E.060 (RNE) · Integración ETABS v20 – v23",
                  style="HeaderSub.TLabel", font=("Segoe UI", 8)).pack(anchor="w")
        ttk.Label(cab, text="v" + __version__ + "  ", style="HeaderSub.TLabel").pack(side="right")

        # -------- barra de herramientas ----------------------------------
        barra = ttk.Frame(self, padding=(10, 8))
        barra.pack(fill="x")
        ttk.Label(barra, text="Fuente de datos:").pack(side="left")
        self.combo_fuente = ttk.Combobox(barra, textvariable=self.var["fuente"],
                                         state="readonly", width=34,
                                         values=["Modelo demo"])
        self.combo_fuente.pack(side="left", padx=(6, 12))
        self.combo_fuente.bind("<<ComboboxSelected>>", lambda e: self.cambiar_fuente())

        ttk.Button(barra, text="Conectar ETABS", style="Sec.TButton",
                   command=self.conectar_etabs).pack(side="left", padx=3)
        ttk.Button(barra, text="Importar tablas…", style="Sec.TButton",
                   command=self.importar_tablas).pack(side="left", padx=3)
        ttk.Button(barra, text="Actualizar lista", style="Sec.TButton",
                   command=self.cargar_elementos).pack(side="left", padx=3)

        # -------- cuerpo ---------------------------------------------------
        cuerpo = ttk.Panedwindow(self, orient="horizontal")
        cuerpo.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # ---- panel izquierdo: lista de elementos -------------------------
        izq = ttk.Frame(cuerpo, width=330)
        cuerpo.add(izq, weight=0)

        caja_busqueda = ttk.Frame(izq)
        caja_busqueda.pack(fill="x", pady=(0, 6))
        ttk.Label(caja_busqueda, text="Buscar:").pack(side="left")
        entrada = ttk.Entry(caja_busqueda, textvariable=self.var["buscar"])
        entrada.pack(side="left", fill="x", expand=True, padx=(6, 0))
        entrada.bind("<KeyRelease>", lambda e: self.cargar_elementos(solo_filtro=True))

        caja_filtro = ttk.Frame(izq)
        caja_filtro.pack(fill="x", pady=(0, 6))
        ttk.Label(caja_filtro, text="Mostrar:").pack(side="left")
        for texto in ("Todos", "Vigas", "Columnas"):
            ttk.Radiobutton(caja_filtro, text=texto, value=texto[:-1] if texto != "Todos" else "Todos",
                            variable=self.var["filtro"],
                            command=self.cargar_elementos).pack(side="left", padx=4)

        marco_lista = ttk.Frame(izq)
        marco_lista.pack(fill="both", expand=True)
        self.lista = ttk.Treeview(marco_lista, columns=("tipo", "seccion", "piso"),
                                  show="tree headings", height=22)
        self.lista.heading("#0", text="Elemento")
        self.lista.heading("tipo", text="Tipo")
        self.lista.heading("seccion", text="Sección")
        self.lista.heading("piso", text="Nivel")
        self.lista.column("#0", width=110)
        self.lista.column("tipo", width=72, anchor="center")
        self.lista.column("seccion", width=76, anchor="center")
        self.lista.column("piso", width=76, anchor="center")
        scroll = ttk.Scrollbar(marco_lista, orient="vertical", command=self.lista.yview)
        self.lista.configure(yscrollcommand=scroll.set)
        self.lista.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.lista.bind("<<TreeviewSelect>>", self._seleccionar_lista)
        self.lista.bind("<Double-1>", lambda e: self.disenar())

        self.lbl_info = ttk.Label(izq, text="", foreground=COLOR_GRIS, wraplength=310,
                                  justify="left")
        self.lbl_info.pack(fill="x", pady=(6, 0))

        # ---- panel derecho: pestañas -------------------------------------
        der = ttk.Frame(cuerpo)
        cuerpo.add(der, weight=1)
        self.cuaderno = ttk.Notebook(der)
        self.cuaderno.pack(fill="both", expand=True)

        self.tab_elemento = ttk.Frame(self.cuaderno, padding=10)
        self.tab_diseno = ttk.Frame(self.cuaderno, padding=10)
        self.tab_resultados = ttk.Frame(self.cuaderno, padding=10)
        self.tab_memoria = ttk.Frame(self.cuaderno, padding=10)
        self.tab_ayuda = ttk.Frame(self.cuaderno, padding=10)
        self.cuaderno.add(self.tab_elemento, text="1 · Elemento")
        self.cuaderno.add(self.tab_diseno, text="2 · Diseño")
        self.cuaderno.add(self.tab_resultados, text="3 · Resultados")
        self.cuaderno.add(self.tab_memoria, text="4 · Memoria de cálculo")
        self.cuaderno.add(self.tab_ayuda, text="Ayuda")

        self._construir_tab_elemento()
        self._construir_tab_diseno()
        self._construir_tab_resultados()
        self._construir_tab_memoria()
        self._construir_tab_ayuda()

        barra_estado = ttk.Frame(self, padding=(10, 4))
        barra_estado.pack(fill="x")
        ttk.Label(barra_estado, textvariable=self.var["estado"],
                  foreground=COLOR_GRIS).pack(side="left")

    # ==================================================================
    # Construcción de pestañas
    # ==================================================================
    def _construir_tab_elemento(self):
        cont = self.tab_elemento
        cab = ttk.Frame(cont)
        cab.pack(fill="x")
        self.lbl_nombre = ttk.Label(cab, text="Sin elemento seleccionado",
                                    font=("Segoe UI", 14, "bold"), foreground=COLOR_AZUL)
        self.lbl_nombre.pack(side="left")
        self.lbl_tipo = ttk.Label(cab, text="", font=("Segoe UI", 9, "bold"),
                                  foreground=COLOR_AZUL2)
        self.lbl_tipo.pack(side="left", padx=12)

        self.lbl_datos = ttk.Label(cont, text="Seleccione una viga o columna en la lista.",
                                   foreground=COLOR_GRIS, font=("Segoe UI", 9))
        self.lbl_datos.pack(anchor="w", pady=(4, 10))

        marco = ttk.LabelFrame(cont, text=" Envolventes por estación (solicitaciones del modelo) ",
                               padding=8)
        marco.pack(fill="both", expand=True)
        cols = ("estacion", "mpos", "mneg", "vu", "tu", "pu", "combo")
        self.tabla_env = ttk.Treeview(marco, columns=cols, show="headings", height=14)
        titulos = [("estacion", "Estación [m]", 90), ("mpos", "M3+ [t·m]", 90),
                   ("mneg", "M3− [t·m]", 90), ("vu", "V2 [t]", 80),
                   ("tu", "T [t·m]", 80), ("pu", "P [t]", 80),
                   ("combo", "Combinación gobernante M3−", 260)]
        for c, t, w in titulos:
            self.tabla_env.heading(c, text=t)
            self.tabla_env.column(c, width=w, anchor="center")
        sc = ttk.Scrollbar(marco, orient="vertical", command=self.tabla_env.yview)
        self.tabla_env.configure(yscrollcommand=sc.set)
        self.tabla_env.pack(side="left", fill="both", expand=True)
        sc.pack(side="right", fill="y")

        self.lbl_combos = ttk.Label(cont, text="", foreground=COLOR_GRIS, wraplength=900,
                                    justify="left")
        self.lbl_combos.pack(anchor="w", pady=(8, 0))

    def _construir_tab_diseno(self):
        cont = self.tab_diseno
        marco = ttk.LabelFrame(cont, text=" Parámetros de diseño según E.060 ", padding=10)
        marco.pack(fill="x")

        def campo(fila, col, etiqueta, variable, ancho=12, valores=None):
            ttk.Label(marco, text=etiqueta).grid(row=fila, column=col * 2, sticky="e",
                                                 padx=(0, 6), pady=4)
            if valores:
                w = ttk.Combobox(marco, textvariable=variable, values=valores,
                                 width=ancho - 2, state="readonly")
            else:
                w = ttk.Entry(marco, textvariable=variable, width=ancho)
            w.grid(row=fila, column=col * 2 + 1, sticky="w", padx=(0, 22), pady=4)
            return w

        campo(0, 0, "Tipo:", self.var["tipo"], 14, ["auto", "Viga", "Columna"])
        campo(0, 1, "f'c [kgf/cm²]:", self.var["fc"], 12)
        campo(0, 2, "fy [kgf/cm²]:", self.var["fy"], 12)
        campo(1, 0, "b [cm]:", self.var["b"], 14)
        campo(1, 1, "h [cm]:", self.var["h"], 12)
        campo(1, 2, "Recubrimiento [cm]:", self.var["rec"], 12)
        campo(2, 0, "Estribo:", self.var["estribo"], 14, ["#3", "#4"])
        campo(2, 1, "N.º estaciones:", self.var["nest"], 12, ["3", "5", "7", "9"])
        campo(2, 2, "Norma sísmica:", tk.StringVar(value="E.030-2018"), 12)

        campo(3, 0, "Proyecto:", self.var["proyecto"], 30)
        campo(4, 0, "Ubicación:", self.var["ubicacion"], 30)
        campo(5, 0, "Responsable:", self.var["autor"], 30)

        opciones = ttk.Frame(cont)
        opciones.pack(fill="x", pady=10)
        ttk.Checkbutton(opciones, text="Requisitos sismorresistentes (cap. 21)",
                        variable=self.var["sismico"]).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(opciones, text="Considerar torsión",
                        variable=self.var["torsion"]).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(opciones, text="Amplificar momentos por esbeltez (10.10.7)",
                        variable=self.var["esbeltez"]).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(opciones, text="Cortante por capacidad (21.4.5)",
                        variable=self.var["capacidad"]).pack(side="left")

        botones = ttk.Frame(cont)
        botones.pack(fill="x", pady=(4, 10))
        ttk.Button(botones, text="Diseñar según E.060", style="Accion.TButton",
                   command=self.disenar).pack(side="left")
        ttk.Button(botones, text="Limpiar resultados", style="Sec.TButton",
                   command=self.limpiar).pack(side="left", padx=8)

        self.lbl_dis_estado = ttk.Label(cont, text="", foreground=COLOR_GRIS,
                                        wraplength=980, justify="left")
        self.lbl_dis_estado.pack(anchor="w")

        marco_info = ttk.LabelFrame(cont, text=" Criterios aplicados ", padding=10)
        marco_info.pack(fill="both", expand=True, pady=(10, 0))
        texto = tk.Text(marco_info, height=12, wrap="word", relief="flat",
                        bg="#fbfcfe", fg="#2b3648", font=("Segoe UI", 9))
        texto.pack(fill="both", expand=True)
        texto.insert("1.0", CRITERIOS)
        texto.configure(state="disabled")

    def _construir_tab_resultados(self):
        cont = self.tab_resultados
        self.lbl_resumen = ttk.Label(cont, text="Diseñe un elemento para ver los resultados.",
                                     font=("Segoe UI", 10, "bold"), foreground=COLOR_AZUL)
        self.lbl_resumen.pack(anchor="w")

        self.marco_kpi = ttk.Frame(cont)
        self.marco_kpi.pack(fill="x", pady=8)

        self.cuaderno_res = ttk.Notebook(cont)
        self.cuaderno_res.pack(fill="both", expand=True)
        self.tabla_res = ttk.Frame(self.cuaderno_res, padding=6)
        self.tabla_chk = ttk.Frame(self.cuaderno_res, padding=6)
        self.texto_res = ttk.Frame(self.cuaderno_res, padding=6)
        self.cuaderno_res.add(self.tabla_res, text="Detalle por estación")
        self.cuaderno_res.add(self.tabla_chk, text="Verificaciones")
        self.cuaderno_res.add(self.texto_res, text="Resumen")

        self.tree_res = ttk.Treeview(self.tabla_res, show="headings", height=12)
        sc = ttk.Scrollbar(self.tabla_res, orient="vertical", command=self.tree_res.yview)
        self.tree_res.configure(yscrollcommand=sc.set)
        self.tree_res.pack(side="left", fill="both", expand=True)
        sc.pack(side="right", fill="y")

        self.tree_chk = ttk.Treeview(self.tabla_chk, show="headings", height=12)
        for c, t, w in (("verif", "Verificación", 420), ("valor", "Valor", 110),
                        ("limite", "Límite", 110), ("res", "Resultado", 110),
                        ("ref", "Referencia", 180)):
            self.tree_chk.heading(c, text=t)
            self.tree_chk.column(c, width=w, anchor="w" if c in ("verif", "ref") else "center")
        self.tree_chk.tag_configure("mal", foreground=COLOR_MAL)
        self.tree_chk.tag_configure("ok", foreground=COLOR_OK)
        sc2 = ttk.Scrollbar(self.tabla_chk, orient="vertical", command=self.tree_chk.yview)
        self.tree_chk.configure(yscrollcommand=sc2.set)
        self.tree_chk.pack(side="left", fill="both", expand=True)
        sc2.pack(side="right", fill="y")

        self.txt_res = tk.Text(self.texto_res, wrap="word", relief="flat",
                               bg="#fbfcfe", font=("Consolas", 9))
        self.txt_res.pack(fill="both", expand=True)

    def _construir_tab_memoria(self):
        cont = self.tab_memoria
        ttk.Label(cont, text="Memoria de cálculo", font=("Segoe UI", 12, "bold"),
                  foreground=COLOR_AZUL).pack(anchor="w")
        ttk.Label(cont, text="Documento completo: datos, solicitaciones, fórmulas, "
                             "resultados, verificaciones, conclusiones y gráficos.",
                  foreground=COLOR_GRIS).pack(anchor="w", pady=(2, 12))

        botones = ttk.Frame(cont)
        botones.pack(fill="x")
        self.btn_mem_html = ttk.Button(botones, text="Generar y abrir HTML",
                                       style="Accion.TButton", command=self.abrir_memoria)
        self.btn_mem_html.pack(side="left")
        self.btn_mem_pdf = ttk.Button(botones, text="Exportar PDF", style="Sec.TButton",
                                      command=self.exportar_pdf)
        self.btn_mem_pdf.pack(side="left", padx=8)
        ttk.Button(botones, text="Exportar Markdown", style="Sec.TButton",
                   command=self.exportar_md).pack(side="left")
        ttk.Button(botones, text="Abrir carpeta de salidas", style="Sec.TButton",
                   command=lambda: abrir_archivo(SALIDAS)).pack(side="left", padx=8)

        marco = ttk.LabelFrame(cont, text=" Vista previa ", padding=8)
        marco.pack(fill="both", expand=True, pady=(12, 0))
        self.txt_mem = tk.Text(marco, wrap="word", relief="flat", bg="#fbfcfe",
                               font=("Consolas", 9))
        sc = ttk.Scrollbar(marco, orient="vertical", command=self.txt_mem.yview)
        self.txt_mem.configure(yscrollcommand=sc.set)
        self.txt_mem.pack(side="left", fill="both", expand=True)
        sc.pack(side="right", fill="y")

    def _construir_tab_ayuda(self):
        cont = self.tab_ayuda
        texto = tk.Text(cont, wrap="word", relief="flat", bg="#fbfcfe",
                        font=("Segoe UI", 9), padx=12, pady=10)
        sc = ttk.Scrollbar(cont, orient="vertical", command=texto.yview)
        texto.configure(yscrollcommand=sc.set)
        texto.pack(side="left", fill="both", expand=True)
        sc.pack(side="right", fill="y")
        texto.insert("1.0", AYUDA)
        texto.configure(state="disabled")

    # ==================================================================
    # Fuentes de datos
    # ==================================================================
    def cargar_demo(self):
        try:
            self.fuente = ETABSDemo()
            self.fuente_id = "demo"
            self.var["fuente"].set("Modelo demo")
            self.cargar_elementos()
            self.var["estado"].set("Modelo demo cargado (pórtico de 4 pisos y 3 vanos).")
        except Exception as exc:
            messagebox.showerror("Error", "No se pudo cargar el modelo demo:\n%s" % exc)

    def cambiar_fuente(self):
        nombre = self.var["fuente"].get()
        if nombre.startswith("Modelo demo"):
            self.cargar_demo()
        elif nombre.startswith("ETABS"):
            self.conectar_etabs()
        # las fuentes de tablas se cargan directamente en el evento del archivo

    def conectar_etabs(self):
        try:
            from e060.etabs import conectar
        except Exception:
            messagebox.showerror("ETABS", "La conexión COM solo está disponible en Windows.")
            return
        self.var["estado"].set("Conectando con ETABS…")
        self.update_idletasks()
        try:
            fuente = conectar(adjuntar=True)
            self.fuente = fuente
            self.fuente_id = "etabs"
            info = fuente.info_modelo()
            self.var["fuente"].set("ETABS v%s" % info.get("version", "?"))
            valores = list(self.combo_fuente["values"])
            etiqueta = "ETABS v%s" % info.get("version", "?")
            if etiqueta not in valores:
                valores.append(etiqueta)
                self.combo_fuente["values"] = valores
            self.cargar_elementos()
            self.var["estado"].set("Conectado a ETABS %s · modelo: %s"
                                   % (info.get("version", "?"), info.get("modelo", "")))
        except Exception as exc:
            messagebox.showerror("Conexión con ETABS",
                                 "No se pudo conectar.\n\n"
                                 "1. Verifique que ETABS v20–v23 esté abierto con el modelo.\n"
                                 "2. Instale comtypes: pip install comtypes\n\n"
                                 "Detalle: %s" % exc)
            self.var["estado"].set("Sin conexión con ETABS.")

    def importar_tablas(self):
        ruta_f = filedialog.askopenfilename(
            title="Tabla 'Element Forces - Frames' exportada de ETABS",
            filetypes=[("Tablas ETABS", "*.csv *.txt *.xlsx"), ("Todos", "*.*")])
        if not ruta_f:
            return
        ruta_s = filedialog.askopenfilename(
            title="Tabla de secciones (opcional, Cancelar para omitir)",
            filetypes=[("Tablas ETABS", "*.csv *.txt *.xlsx"), ("Todos", "*.*")])
        ruta_m = filedialog.askopenfilename(
            title="Tabla de materiales (opcional, Cancelar para omitir)",
            filetypes=[("Tablas ETABS", "*.csv *.txt *.xlsx"), ("Todos", "*.*")])
        try:
            self.var["estado"].set("Importando tablas…")
            self.update_idletasks()
            fuente = ETABSTablas.desde_archivos(ruta_f, ruta_s or None, ruta_m or None,
                                                tipo_defecto="auto")
            self.fuente = fuente
            self.fuente_id = "tablas"
            info = fuente.info_modelo()
            etiqueta = "Tablas · %s" % info.get("archivo", "")
            valores = list(self.combo_fuente["values"])
            if etiqueta not in valores:
                valores.append(etiqueta)
                self.combo_fuente["values"] = valores
            self.var["fuente"].set(etiqueta)
            self.cargar_elementos()
            self.var["estado"].set("Importados %d elementos y %d combinaciones."
                                   % (info.get("elementos", 0), info.get("combos", 0)))
        except Exception as exc:
            messagebox.showerror("Importación de tablas", str(exc))
            self.var["estado"].set("Error al importar tablas.")

    # ------------------------------------------------------------------
    def cargar_elementos(self, solo_filtro=False):
        if self.fuente is None:
            return
        filtro = self.var["filtro"].get()
        tipo = "Todos" if filtro == "Todos" else filtro
        try:
            nombres = self.fuente.listar_elementos(tipo=tipo)
        except Exception as exc:
            self.var["estado"].set("Error al listar elementos: %s" % exc)
            return
        texto = self.var["buscar"].get().strip().lower()
        self.elementos = []
        self.lista.delete(*self.lista.get_children())
        for nombre in nombres:
            try:
                el = self.fuente.obtener_elemento(nombre)
            except Exception:
                continue
            if texto and texto not in (nombre + " " + el.seccion + " " + el.story).lower():
                continue
            self.elementos.append(nombre)
            self.lista.insert("", "end", iid=nombre, text=nombre,
                              values=(el.tipo, el.seccion, el.story))
        self.lbl_info.configure(text="%d elementos disponibles." % len(self.elementos))

    def _seleccionar_lista(self, evento=None):
        sel = self.lista.selection()
        if sel:
            self.seleccionar_elemento(sel[0])

    # ==================================================================
    # Elemento
    # ==================================================================
    def seleccionar_elemento(self, nombre):
        try:
            el = self.fuente.obtener_elemento(nombre)
        except Exception as exc:
            messagebox.showerror("Elemento", str(exc))
            return
        self.elemento_actual = nombre
        self.datos_elemento = el
        self.salida = None
        self.memoria_doc = None

        self.lbl_nombre.configure(text=nombre)
        self.lbl_tipo.configure(text=el.tipo.upper())
        self.lbl_datos.configure(
            text="Sección %.0f × %.0f cm  ·  Nivel: %s  ·  Longitud: %.2f m  ·  "
                 "f'c = %.0f kgf/cm²  ·  fy = %.0f kgf/cm²  ·  %d combinaciones  ·  %s"
                 % (el.b, el.h, el.story or "—", el.L / 100.0, el.fc, el.fy,
                    len(el.combos), el.origen or ""))
        self.var["b"].set("%.0f" % el.b if el.b else "")
        self.var["h"].set("%.0f" % el.h if el.h else "")
        self.var["fc"].set("%.0f" % el.fc)
        self.var["fy"].set("%.0f" % el.fy)
        self.var["tipo"].set("auto")

        self.tabla_env.delete(*self.tabla_env.get_children())
        for e in el.envolventes():
            self.tabla_env.insert("", "end", values=(
                fmt(e["estacion"] / 100.0), fmt(e["Mu_pos"] / 1e5),
                fmt(-e["Mu_neg"] / 1e5), fmt(e["Vu"] / 1e3),
                fmt(e["Tu"] / 1e5), fmt(e["Pu"] / 1e3),
                e["combo_neg"] or e["combo_pos"]))
        self.lbl_combos.configure(text="Combinaciones: " + " · ".join(el.combos[:14])
                                  + (" …" if len(el.combos) > 14 else ""))
        self.var["estado"].set("Elemento %s cargado." % nombre)
        self.cuaderno.select(self.tab_elemento)

    # ==================================================================
    # Diseño
    # ==================================================================
    def _opciones(self):
        opc = servicio.OpcionesDiseno()
        opc.tipo = self.var["tipo"].get() or "auto"
        opc.sismico = bool(self.var["sismico"].get())
        opc.considerar_torsion = bool(self.var["torsion"].get())
        opc.amplificar_esbeltez = bool(self.var["esbeltez"].get())
        opc.db_estribo = self.var["estribo"].get() or "#3"
        opc.proyecto = self.var["proyecto"].get()
        opc.ubicacion = self.var["ubicacion"].get()
        opc.autor = self.var["autor"].get()
        for campo in ("fc", "fy", "b", "h", "rec"):
            valor = self.var[campo].get().strip().replace(",", ".")
            if valor:
                try:
                    setattr(opc, "recubrimiento" if campo == "rec" else campo, float(valor))
                except ValueError:
                    pass
        try:
            opc.n_estaciones = int(self.var["nest"].get())
        except ValueError:
            opc.n_estaciones = 5
        return opc

    def disenar(self):
        if self.fuente is None or not self.elemento_actual:
            messagebox.showinfo("Diseño", "Seleccione primero un elemento de la lista.")
            return
        self.var["estado"].set("Diseñando…")
        self.update_idletasks()
        try:
            el = self.fuente.obtener_elemento(self.elemento_actual)
            self.salida = servicio.disenar_elemento(el, self._opciones())
        except Exception as exc:
            self.var["estado"].set("Error en el diseño.")
            messagebox.showerror("Diseño", str(exc))
            traceback.print_exc()
            return
        self.mostrar_resultados()
        self.cuaderno.select(self.tab_resultados)
        self.var["estado"].set("Diseño completado: %s · %s"
                               % (self.salida["tipo"], self.elemento_actual))

    def mostrar_resultados(self):
        out = self.salida
        res = out["resumen"]
        aprobado = servicio.aprobado(out)
        self.lbl_resumen.configure(
            text="%s %s · sección %.0f×%.0f cm · %s"
                 % (out["tipo"].upper(), out["elemento"].nombre,
                    out["elemento"].b, out["elemento"].h,
                    "CUMPLE TODAS LAS VERIFICACIONES E.060" if aprobado
                    else "REVISAR VERIFICACIONES"),
            foreground=COLOR_OK if aprobado else COLOR_MAL)

        for w in self.marco_kpi.winfo_children():
            w.destroy()
        if out["tipo"] == "Viga":
            c = res["corte_gobernante"] or {}
            tarjetas = [
                ("Refuerzo inferior", max(res["filas"], key=lambda f: f["As_pos"])["ref_pos"]),
                ("Refuerzo superior", max(res["filas"], key=lambda f: f["As_neg"])["ref_neg"]),
                ("Estribos", "%s @ %.0f cm" % (c.get("estribo", "—"), c.get("s_conf", 0))),
                ("D/C corte", fmt(c.get("dcr", 0), 2)),
                ("D/C flexión", fmt(max(max(f["dcr_pos"], f["dcr_neg"]) for f in res["filas"]), 2)),
            ]
        else:
            tarjetas = [
                ("Refuerzo", res["refuerzo"]),
                ("Cuantía", "%.2f %%" % (res["rho"] * 100)),
                ("D/C biaxial", fmt(res["dcr"], 3)),
                ("Estribos", res["estribos"]),
                ("Esbeltez k·lu/r", fmt(res["esbeltez"]["klu_r"], 1)),
            ]
        for i, (titulo, valor) in enumerate(tarjetas):
            caja = tk.Frame(self.marco_kpi, bg="white", highlightbackground="#d8e0ea",
                            highlightthickness=1, padx=12, pady=8)
            caja.grid(row=0, column=i, sticky="nsew", padx=(0, 8))
            self.marco_kpi.columnconfigure(i, weight=1)
            tk.Label(caja, text=titulo.upper(), bg="white", fg=COLOR_GRIS,
                     font=("Segoe UI", 7, "bold")).pack(anchor="w")
            tk.Label(caja, text=str(valor), bg="white", fg=COLOR_AZUL,
                     font=("Segoe UI", 11, "bold")).pack(anchor="w")

        self.tree_res.delete(*self.tree_res.get_children())
        if out["tipo"] == "Viga":
            columnas = ("estacion", "mpos", "refpos", "phipos", "mneg", "refneg",
                        "phineg", "dcr")
            titulos = ["Estación", "Mu+ [t·m]", "Refuerzo +", "φMn+ [t·m]",
                       "Mu− [t·m]", "Refuerzo −", "φMn− [t·m]", "D/C"]
            anchos = [130, 85, 95, 90, 85, 95, 90, 60]
            self.tree_res["columns"] = columnas
            for c, t, w in zip(columnas, titulos, anchos):
                self.tree_res.heading(c, text=t)
                self.tree_res.column(c, width=w, anchor="center")
            for f in res["filas"]:
                self.tree_res.insert("", "end", values=(
                    f["estacion"], fmt(f["Mu_pos"]), f["ref_pos"], fmt(f["phiMn_pos"]),
                    fmt(f["Mu_neg"]), f["ref_neg"], fmt(f["phiMn_neg"]),
                    fmt(max(f["dcr_pos"], f["dcr_neg"]), 3)))
        else:
            columnas = ("combo", "p", "m2", "m3", "cap", "dcr")
            titulos = ["Combinación", "P [t]", "M2 [t·m]", "M3 [t·m]",
                       "φMcap [t·m]", "D/C"]
            anchos = [300, 90, 90, 90, 100, 60]
            self.tree_res["columns"] = columnas
            for c, t, w in zip(columnas, titulos, anchos):
                self.tree_res.heading(c, text=t)
                self.tree_res.column(c, width=w, anchor="center")
            for det in out["resultado"]["detalle_demanda"]:
                d = det["demanda"]
                self.tree_res.insert("", "end", values=(
                    d.combo, fmt(d.P / 1e3), fmt(abs(d.M2) / 1e5),
                    fmt(abs(d.M3) / 1e5), fmt(det["info"].get("Mcap", 0) / 1e5, 2),
                    fmt(det["dcr"], 3)))

        self.tree_chk.delete(*self.tree_chk.get_children())
        for v in servicio.verificar_resultado(out):
            valor = v.get("valor")
            limite = v.get("limite")
            self.tree_chk.insert("", "end", tags=("ok" if v["cumple"] else "mal",),
                                 values=(v["nombre"],
                                         fmt(valor, 3) if isinstance(valor, float) else valor,
                                         fmt(limite, 3) if isinstance(limite, float) else limite,
                                         "CUMPLE" if v["cumple"] else "NO CUMPLE",
                                         v.get("ref", "")))

        self.txt_res.configure(state="normal")
        self.txt_res.delete("1.0", "end")
        self.txt_res.insert("1.0", self._texto_resumen())
        self.txt_res.configure(state="disabled")
        self._actualizar_previa_memoria()

    def _texto_resumen(self):
        out = self.salida
        res = out["resumen"]
        lineas = []
        el = out["elemento"]
        lineas.append("ELEMENTO: %s (%s) · %s" % (el.nombre, el.tipo, el.story))
        lineas.append("Sección: %.0f × %.0f cm   L = %.2f m" % (el.b, el.h, el.L / 100.0))
        lineas.append("Materiales: f'c = %.0f kgf/cm² · fy = %.0f kgf/cm²"
                      % (el.fc, el.fy))
        lineas.append("")
        if out["tipo"] == "Viga":
            c = res["corte_gobernante"] or {}
            for f in res["filas"]:
                lineas.append(
                    "%-16s Mu+=%7.2f t·m  %-9s Mu-=%7.2f t·m  %-9s D/C=%.2f"
                    % (f["estacion"], f["Mu_pos"], f["ref_pos"], f["Mu_neg"],
                       f["ref_neg"], max(f["dcr_pos"], f["dcr_neg"])))
            lineas.append("")
            lineas.append("Corte: Vu = %.2f t (diseño %.2f t) · Vc = %.2f t · φ = %.2f"
                          % (c.get("Vu", 0), c.get("Vu_conf", 0), c.get("Vc", 0),
                             c.get("phi", 0)))
            lineas.append("Estribos %s: @ %.1f cm en zona de confinamiento y @ %.1f cm en el resto"
                          % (c.get("estribo", ""), c.get("s_conf", 0), c.get("s_resto", 0)))
        else:
            lineas.append("Refuerzo longitudinal: %s" % res["refuerzo"])
            lineas.append("Cuantía ρ = %.2f %%   As = %.2f cm²"
                          % (res["rho"] * 100, res["As"]))
            lineas.append("P0 = %.1f t · φPn,max = %.1f t · Pu = %.1f t"
                          % (res["P0"] / 1e3, res["phiPn_max"] / 1e3, res["Pu"] / 1e3))
            lineas.append("D/C flexo-compresión biaxial = %.3f" % res["dcr"])
            lineas.append("Estribos: %s · @ %.0f cm fuera de confinamiento"
                          % (res["estribos"], res["s_ext"]))
            lineas.append("Esbeltez k·lu/r = %.1f (límite %.1f) → %s"
                          % (res["esbeltez"]["klu_r"], res["esbeltez"]["limite"],
                             "esbelta" if res["esbeltez"]["esbelto"] else "no esbelta"))
        lineas.append("")
        lineas.append("VERIFICACIONES")
        for v in servicio.verificar_resultado(out):
            lineas.append("  [%s] %s" % ("OK" if v["cumple"] else "NO", v["nombre"]))
        lineas.append("")
        lineas.append("La memoria de cálculo completa está en la pestaña 4.")
        return "\n".join(lineas)

    def limpiar(self):
        self.salida = None
        self.memoria_doc = None
        self.lbl_resumen.configure(text="Diseñe un elemento para ver los resultados.",
                                   foreground=COLOR_AZUL)
        for w in self.marco_kpi.winfo_children():
            w.destroy()
        self.tree_res.delete(*self.tree_res.get_children())
        self.tree_chk.delete(*self.tree_chk.get_children())
        self.txt_res.delete("1.0", "end")
        self.txt_mem.delete("1.0", "end")
        self.var["estado"].set("Resultados borrados.")

    # ==================================================================
    # Memoria
    # ==================================================================
    def _actualizar_previa_memoria(self):
        if self.salida is None:
            return
        try:
            doc = construir_memoria(self.salida)
            self.memoria_doc = doc
            texto = doc.markdown()
            self.txt_mem.delete("1.0", "end")
            self.txt_mem.insert("1.0", texto)
        except Exception as exc:
            self.txt_mem.insert("end", "\nError al generar la memoria: %s" % exc)

    def _ruta_salida(self, extension):
        os.makedirs(SALIDAS, exist_ok=True)
        nombre = "memoria_%s_%s.%s" % (
            (self.salida["elemento"].nombre or "elemento").replace("/", "-"),
            datetime.now().strftime("%Y%m%d_%H%M"), extension)
        return os.path.join(SALIDAS, nombre)

    def abrir_memoria(self):
        if self.salida is None:
            messagebox.showinfo("Memoria", "Diseñe primero el elemento.")
            return
        try:
            doc = self.memoria_doc or construir_memoria(self.salida)
            ruta = self._ruta_salida("html")
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(doc.html())
            self.var["estado"].set("Memoria generada: %s" % ruta)
            abrir_archivo(ruta)
        except Exception as exc:
            messagebox.showerror("Memoria", "No se pudo generar la memoria:\n%s" % exc)

    def exportar_pdf(self):
        if self.salida is None:
            messagebox.showinfo("Memoria", "Diseñe primero el elemento.")
            return
        ruta = self._ruta_salida("pdf")
        try:
            ok = guardar_pdf(self.salida, ruta)
            if not ok:
                messagebox.showwarning(
                    "PDF no disponible",
                    "Para exportar en PDF instale reportlab:\n\n"
                    "  pip install reportlab\n\n"
                    "Mientras tanto puede usar el HTML y la opción de impresión "
                    "del navegador (Guardar como PDF).")
                return
            self.var["estado"].set("PDF generado: %s" % ruta)
            abrir_archivo(ruta)
        except Exception as exc:
            messagebox.showerror("PDF", str(exc))

    def exportar_md(self):
        if self.salida is None:
            messagebox.showinfo("Memoria", "Diseñe primero el elemento.")
            return
        doc = self.memoria_doc or construir_memoria(self.salida)
        ruta = self._ruta_salida("md")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(doc.markdown())
        self.var["estado"].set("Markdown generado: %s" % ruta)
        abrir_archivo(ruta)

    # ------------------------------------------------------------------
    def _cerrar(self):
        try:
            if self.fuente is not None:
                self.fuente.cerrar()
        except Exception:
            pass
        self.destroy()


# ===========================================================================
# Textos
# ===========================================================================
CRITERIOS = """Criterios y referencias normativas aplicados (NTP E.060 – RNE)

1. FLEXIÓN
   • Bloque rectangular equivalente de esfuerzos: a = β1·c (10.2.7.3) y φ = 0.90
     para secciones controladas por tracción (9.3.2.1), con interpolación en la
     zona de transición según εt.
   • Acero mínimo: As ≥ máx(0.7√f'c/fy ; 14/fy)·b·d (10.5.1).
   • Cuantía máxima dúctil para εt ≥ 0.004 y ρ ≤ 0.025 en pórticos (10.3.4, 21.4.4).
   • Separación libre entre barras: máx(2.5 cm ; 1.33·db ; 1.33·agregado) (7.6.1).

2. CORTE Y TORSIÓN
   • Vc = 0.53·√f'c·bw·d·(1 + Nu/(14Ag)) (11.3.1.1).
   • Vs,req = Vu/φ − Vc; φ = 0.85 (9.3.2.3 / 21.2.4.3), con Vc = 0 en la rótula
     plástica cuando el cortante sismoinducido ≥ 50 % del total (21.4.5.2).
   • Cortante por capacidad: Ve = (Mpr1 + Mpr2)/ln + wu·ln/2, con Mpr = 1.25·fy
     (21.4.5.1).
   • Av/s,mín = máx(0.062√f'c·b/fy ; 0.35·b/fy) (11.4.6.3); Vs ≤ 2.1√f'c·bw·d
     (11.4.7.9).
   • Espaciamientos máximos en zona de confinamiento: s ≤ mín(d/4, 8·db_long,
     24·db_est, 30 cm) (21.4.4.2).
   • Torsión: Tcr = 0.27√f'c·Acp²/Pcp (11.5.2.2); At/s = Tu/(φ·2·A0·fy) (11.5.3.6).

3. COLUMNAS
   • Carga axial máxima: φPn,max = 0.80·φ·P0 con φ = 0.65 (10.3.6).
   • Flexo-compresión por compatibilidad de deformaciones (εcu = 0.003, acero
     elastoplástico) y superficie de interacción P-Mx-My para flexión biaxial.
   • Cuantía 1 % ≤ ρ ≤ 6 % (10.9.1) y mínimo 4 barras (10.9.2).
   • Esbeltez: k·lu/r ≤ 34 − 12(M1/M2) ≤ 40 (10.10.1.1) y magnificación
     δns = Cm/(1 − Pu/(0.75·Pc)) (10.10.7).
   • Confinamiento: Ash/s ≥ máx[0.3(Ag/Ach − 1)f'c/fy ; 0.09f'c/fy]·bc (21.4.4.4),
     s ≤ mín(b/4, 10 cm, 6·db_long, 24·db_est).

4. COMBINACIONES DE CARGA
   • E.060 9.2: 1.4CM + 1.7CV; 1.2CM + 1.6CV + 0.5CVt; 1.2CM ± 1.0CV ± CS;
     1.2CM + 1.6CVt; 0.9CM ± CS.
   • E.030-2018 art. 1.4.2: 1.4CM + 1.7CV; 1.25(CM+CV) ± CS; 0.9CM ± CS.

5. ALCANCE
   El programa toma las solicitaciones del modelo ETABS (que ya incluyen las
   combinaciones) y diseña/verifica el elemento. No reemplaza la verificación
   global de la estructura (derivas, irregularidades, columna fuerte–viga débil,
   losas, cimentación).
"""

AYUDA = """Sistema de diseño de concreto armado según la NTP E.060 (RNE) con integración a ETABS 20–23

FLUJO DE TRABAJO
  1. Elija la fuente de datos:
       • "Modelo demo": pórtico de 4 pisos analizado por rigidez (sin ETABS).
       • "Conectar ETABS": se enlaza con la instancia abierta de ETABS (COM/OAPI).
         Puede seleccionar las barras en ETABS y el programa las lista primero.
       • "Importar tablas": cargue el CSV "Element Forces - Frames" exportado de
         ETABS (Display > Tables > Analysis > Element Forces - Frames, luego
         File > Export > Tables to CSV). Opcionalmente cargue las tablas de
         secciones y materiales.
  2. Seleccione un elemento en la lista (se muestran sus solicitaciones).
  3. Revise los parámetros de diseño (f'c, fy, b, h, recubrimiento, estribo).
  4. Pulse "Diseñar según E.060".
  5. Revise las verificaciones y genere la memoria de cálculo (HTML/PDF/MD).

CONEXIÓN CON ETABS (Windows)
  • Requiere Python de 64 bits y la librería comtypes:  pip install comtypes
  • ETABS v20, v21, v22 y v23 usan la misma interfaz OAPI
    (CSI.ETABS.API.ETABSObject), por lo que el conector sirve para las cuatro.
  • ETABS debe estar abierto con el modelo cargado. El programa fija
    temporalmente las unidades en kgf-m para leer y convierte a las unidades
    internas (kgf, cm), restaurando las unidades al cerrar.

FORMATOS DE SALIDA
  • HTML autocontenido con figuras SVG (se abre en el navegador y se imprime a PDF).
  • PDF (requiere reportlab; opcionalmente svglib para las figuras).
  • Markdown (editable en cualquier gestor de documentos).
  Los archivos se guardan en la carpeta "salidas".

UNIDADES
  Internamente el cálculo trabaja en kgf y cm. Las tablas de ETABS se convierten
  automáticamente desde tonf-m, kgf-m, kN-m, kip-ft, etc.

ALCANCE Y RESPONSABILIDAD
  El programa automatiza el diseño seccional de vigas y columnas según E.060.
  El ingeniero estructural responsable debe revisar los resultados, el modelo
  global (derivas, irregularidades, columna fuerte–viga débil), los detalles de
  anclaje y los planos.
"""


def main():
    try:
        app = AppE060()
        app.mainloop()
    except Exception:
        traceback.print_exc()
        try:
            messagebox.showerror("Error", traceback.format_exc())
        except Exception:
            pass


if __name__ == "__main__":
    main()
