# Diseño de Concreto Armado E.060 · Vigas y Columnas · ETABS v20 – v23

Sistema para el **diseño y verificación de vigas y columnas de concreto armado**
según la **Norma Técnica Peruana E.060 "Concreto Armado" (RNE)** que toma las
solicitaciones directamente de **ETABS (versiones 20, 21, 22 y 23)**, permite
**seleccionar un elemento del modelo** y entrega su **memoria de cálculo**
completa (HTML, PDF y Markdown).

> Versión 4.1 — reemplaza la versión 3 (solo vigas, entrada manual), conservada
> en `legado/diseno_viga_concreto_v3.py`.

---

## 1. Qué hace

| Etapa | Detalle |
|---|---|
| **Importación** | Conexión COM/OAPI con ETABS v20–v23 (elementos seleccionados o todo el modelo), importación de tablas exportadas (CSV/XLSX) o modelo demo analizado por rigidez. |
| **Solicitaciones** | Lee P, V2, V3, T, M2, M3 por combinación y estación, y construye envolventes con la combinación que gobierna. |
| **Diseño de vigas** | Flexión (As requerido, mínimo, máximo, ductilidad), selección automática de varillas verificando espaciamiento y capas, corte (Vc, Vs, estribos por zonas), torsión, cortante por capacidad y requisitos sismorresistentes E.060 cap. 21. |
| **Diseño de columnas** | Flexo-compresión **biaxial** por compatibilidad de deformaciones (superficie P-Mx-My), cuantías 1–6 %, esbeltez y magnificación de momentos, confinamiento (Ash) y cortante. |
| **Memoria de cálculo** | Documento con datos, solicitaciones, fórmulas con valores sustituidos, tablas de resultados, verificaciones, conclusiones y figuras (sección, diagrama de interacción, envolvente). |
| **Interfaces** | Aplicación de escritorio (Tkinter) y aplicación web local (sin dependencias), con vista previa de la memoria. |

Todo el cálculo interno trabaja en **kgf y cm**; las tablas se convierten
automáticamente desde tonf-m, kgf-m, kN-m, kN-mm, kip-ft, etc.

---

## 2. Instalación

```bash
git clone <repositorio>
cd diseno-viga-concreto

# El motor no requiere dependencias externas (solo biblioteca estándar de Python 3.8+)
python -m unittest discover -s tests -v     # verificación del motor (64 pruebas)
```

Dependencias **opcionales**:

| Paquete | Para qué | Instalación |
|---|---|---|
| `reportlab` | Exportar la memoria en PDF | `pip install reportlab` |
| `svglib` | Incluir figuras en el PDF | `pip install svglib` |
| `openpyxl` | Leer tablas de ETABS en `.xlsx` | `pip install openpyxl` |
| `comtypes` | Conexión COM/OAPI con ETABS (Windows, 64 bits) | `pip install comtypes` |

---

## 3. Uso

### 3.1 Aplicación web local (recomendada para revisar y presentar)

```bash
python servidor.py                # http://localhost:8000
python servidor.py --puerto 9000 --host 0.0.0.0
```

Pasos: elegir fuente → seleccionar elemento → revisar solicitaciones →
`Diseñar según E.060` → `Abrir memoria`.

### 3.2 Aplicación de escritorio (Windows + ETABS)

```bash
python app_escritorio.py
```

Pasos: `Conectar ETABS` (todo el modelo) o `Solo selección ETABS` (las barras
seleccionadas en ETABS); también `Modelo demo` / `Importar tablas…` → seleccionar
el elemento en la lista → pestaña **2 · Diseño** → `Diseñar según E.060` →
pestaña **4 · Memoria de cálculo** → `Generar y abrir HTML` / `Exportar PDF`.

Para cambiar de elemento en ETABS basta con volver a seleccionar la fuente
`ETABS v…` en la lista: relee las tablas sin reiniciar nada.

### 3.3 Tablas de ejemplo (sin ETABS)

```bash
python ejemplos/generar_ejemplos.py     # regenera los CSV de ejemplo
```

Los archivos de `ejemplos/` reproducen el formato de exportación de ETABS
(`TABLE:  Element Forces - Frames`, etc.) y permiten probar la importación
completa desde la interfaz web o de escritorio.

### 3.4 Modelo demo (sin ETABS)

El modelo demo es un **pórtico plano de 4 pisos y 3 vanos** resuelto por el
método de rigidez (elementos frame 2D), con cargas muerta y viva y sismo según
E.030. Sirve para probar todo el flujo sin ETABS instalado y para validar el
motor de diseño con solicitaciones reales de análisis.

---

### 3.5 Puente con ETABS en otra máquina (`puente_etabs.py`)

La automatización COM/OAPI de ETABS **solo funciona en Windows**. Si la interfaz
web corre en otro equipo (Linux, contenedor, servidor), el puente se ejecuta en
el Windows donde está abierto ETABS y envía las solicitaciones a la interfaz:

```bat
REM en el PC con Windows y ETABS abierto
pip install comtypes
python puente_etabs.py --seleccionados --subir https://<servidor>:8000
```

* `--seleccionados` exporta solo las barras elegidas en ETABS (deseleccione para
  exportar todo el modelo).
* `--carpeta salida` guarda los tres CSV con formato de ETABS si prefiere
  cargarlos a mano con **Importar tablas**.
* `--demo` prueba el puente sin ETABS.
* `--elemento V1-2` (repetible) limita la exportación a ciertos elementos.

Al terminar, la fuente aparece en la interfaz y basta seleccionar el elemento
para diseñarlo y descargar su memoria.

**Sin escribir comandos (recomendado):** en la interfaz, la tarjeta
*ETABS en ejecución* está siempre activa. Al pulsarla se abre el panel de
conexión, que:

1. entrega un **paquete `.zip`** (`/descargas/puente.zip`) con el puente, los
   módulos que necesita y dos archivos `SUBIR_seleccion.bat` / `SUBIR_todo.bat`
   **con la dirección de esta interfaz ya escrita**;
2. muestra el comando equivalente, con botón para copiarlo;
3. **espera la conexión**: cuando el puente envía las tablas, la interfaz
   detecta la fuente nueva, la selecciona sola y avisa («Conectado: N
   elementos»).

Así la tarjeta de ETABS nunca es un callejón sin salida: en Windows conecta por
COM y, si la interfaz corre en otro equipo, conecta con el ETABS de tu PC en
tres pasos (descargar, ejecutar, listo).

### 3.6 Línea de comandos

```bash
python -m e060.cli --demo --listar
python -m e060.cli --demo --elemento V1-2 --pdf salidas/V1-2.pdf
python -m e060.cli --fuerzas ejemplos/ElementForces_Frames.csv \
    --secciones ejemplos/FrameSections_Rectangular.csv \
    --materiales ejemplos/MaterialProperties_Concrete.csv \
    --todos --carpeta salidas/memorias
```

Permite generar memorias en lote (HTML, PDF, Markdown) y encaja en flujos de
revisión o scripts de control de calidad.

## 4. Conexión con ETABS v20 – v23

### 4.1 Puesta en marcha en Windows (paso a paso)

La conexión en vivo es **COM/OAPI**, así que el programa debe correr en el
**mismo Windows** donde está ETABS, con la **misma arquitectura** (ETABS de
64 bits → Python de 64 bits).

1. Instale **Python 3.8 o superior de 64 bits** (python.org, "Windows installer
   (64-bit)"). Compruebe en la consola:
   ```bat
   python -c "import platform; print(platform.architecture()[0])"
   ```
   Debe imprimir `64bit`.
2. Instale la librería de automatización COM (una de las dos basta):
   ```bat
   pip install comtypes
   ::  o bien
   pip install pywin32
   ```
3. Abra **ETABS v20, v21, v22 o v23**, cargue el modelo y **desbloquéelo**
   (`Model > Unlock Model`).
4. Ejecute el análisis: `Analyze > Run Analysis`. Sin resultados no hay
   solicitaciones que leer (el programa lo detecta y lo explica).
5. Arranque el programa en esa misma máquina:
   ```bat
   python servidor.py            :: interfaz web en http://localhost:8000
   iniciar_escritorio.bat        :: app de escritorio (Tkinter)
   ```
6. En la interfaz:
   * **Conectar ETABS** → lee **todo el modelo**.
   * **Solo selección** → lee únicamente las barras que haya seleccionado en
     ETABS (permite seleccionar la viga o columna y diseñarla al instante).
   * Tras cambiar la selección en ETABS, ese mismo botón **vuelve a leer** sin
     reconectar.

Si ETABS no está abierto, el programa **no lanza una instancia vacía**: informa
del problema con pasos concretos (código `etabs_cerrado`). Para abrir ETABS
desde el programa, indique explícitamente la ruta:

```python
from e060.etabs.com import abrir_etabs
fuente = abrir_etabs(modelo=r"C:\proyectos\Edificio.edb")   # lanza ETABS y abre el modelo
```

### 4.2 Qué se lee de ETABS y por qué

* Se usa la interfaz **OAPI** (`CSI.ETABS.API.ETABSObject`), estable y común a
  las versiones 20, 21, 22 y 23; la versión se lee y se muestra en la interfaz.
* Las solicitaciones se leen de la **base de datos de presentación**
  (`DatabaseTables.GetTableForDisplayArray`), no de `Results.FrameForce`. La
  razón es decisiva: `FrameForce` no devuelve la **estación** de cada resultado,
  y sin estación no se puede construir la envolvente de momentos a lo largo del
  elemento. Con las tablas se obtienen las estaciones reales del modelo
  (p. ej. `0, 100, …, 600 cm`) y las mismas columnas que el usuario ve en ETABS.
* Se importan además las tablas de **secciones** (`Frame Assignments - Section
  Properties`, `Frame Section Properties - Rectangular`) y de **materiales**
  (`Material Properties - Concrete Data`) para obtener `b`, `h` y `f'c`.
* La clasificación viga/columna se deduce de la orientación de la barra
  (coordenadas de sus nudos), no del nombre.
* Las tablas del API **no** traen unidades en el encabezado: el programa fija
  el modelo en **kgf-m** mientras lee (y **restituye** el sistema original al
  terminar). Si ETABS no permite cambiar de unidades, se traduce el sistema en
  que esté el modelo.
* El tipo de cada barra sale de la geometría y de la sección asignada; el modelo
  importado por COM pasa por **el mismo analizador** que la importación de CSV,
  de modo que ambos caminos dan resultados idénticos (hay una prueba que lo
  compara elemento por elemento).
* COM exige **`CoInitialize` por hilo** y el servidor web atiende cada petición
  en un hilo distinto: el conector inicializa COM en cada hilo y se reengancha
  a la instancia abierta de ETABS cuando la petición llega en otro hilo
  (`GetActiveObject`), sin reutilizar un objeto de otro apartamento.

Todo esto es verificable **sin Windows**: `tests/simulador_com.py` reproduce la
API COM/OAPI de ETABS (con `comtypes` y con `win32com`) sobre el modelo demo, y
la suite lo ejecuta de verdad.

```bash
python tests/simulador_com.py     # demostración de la conexión simulada
```

### 4.3 Errores de conexión y sus códigos

La interfaz **nunca** muestra un error técnico de `comtypes`: muestra el motivo
en español, los pasos a seguir y la alternativa de trabajo. Las respuestas de la
API llevan el código para poder automatizar.

| Código | Significado | Qué hace el programa |
|---|---|---|
| `plataforma` | El servidor no es Windows | Aviso al abrir + `409`; ofrece importar tablas o el puente |
| `sin_com` | No hay `comtypes`/`pywin32` | Explica cómo instalarlo en el Python de 64 bits |
| `etabs_cerrado` | ETABS no está abierto (o se cerró) | Indica abrir ETABS con el modelo, no crea una instancia vacía |
| `sin_tablas` | No hay tablas de resultados | Pide ejecutar el análisis (`Analyze > Run Analysis`) |
| `sin_seleccion` | «Solo selección» sin barras elegidas | Explica cómo seleccionar en ETABS o usar todo el modelo |
| `error_com` | Otro fallo de COM | Mensaje y sugerencias genéricas de diagnóstico |

```json
{"ok": false, "codigo": "etabs_cerrado",
 "error": "No se encontró una instancia de ETABS en ejecución. …",
 "es_windows": true, "sugerencias": ["Abra ETABS v20, v21, v22 o v23 …", "…"]}
```

La app de escritorio verifica antes de conectar y, si no es posible, ofrece
importar las tablas en el mismo diálogo.

Rutas de la API para quien quiera automatizarlo:

| Ruta | Para qué |
|---|---|
| `GET /api/puente` | URL pública de la interfaz, comando del puente, ruta de descarga y fuentes cargadas |
| `GET /descargas/puente.zip` | paquete listo para ejecutar en el Windows con ETABS (incluye los `.bat` con la URL) |
| `POST /api/importar` | multipart con las tablas (es lo que usa el puente) |
| `POST /api/conectar-etabs` | conexión COM (`{"solo_seleccionados": true}` para la selección) |
| `POST /api/recargar-etabs` | relee las tablas sin reconectar (tras cambiar la selección en ETABS) |

### 4.4 Si la interfaz corre en Linux/macOS

La automatización COM no existe fuera de Windows, así que el programa **no
intenta conectarse a ciegas**: detecta la situación, marca la tarjeta *ETABS en
ejecución* como **no disponible** y muestra el motivo y las alternativas en el
panel lateral. `POST /api/conectar-etabs` responde `409` con el diagnóstico.

| Situación | Cómo trabajar |
|---|---|
| Windows con ETABS abierto | App de escritorio o web local → **Conectar ETABS** (COM/OAPI). |
| Interfaz web en Linux/macOS | Tarjeta **ETABS** → *Conectar con mi ETABS*: descarga el puente, ejecútalo en el Windows de ETABS y la interfaz lo detecta sola. Alternativa: **Importar tablas**. |
| Sin ETABS (pruebas, docencia) | **Modelo demo** o los CSV de `ejemplos/`. |

**Solución de problemas**

| Síntoma | Causa / solución |
|---|---|
| "No se pudo conectar con ETABS" | ETABS cerrado o con el modelo bloqueado; abra el modelo y desbloquéelo. |
| "No se encontró la librería de automatización COM" | `pip install comtypes` con el Python de 64 bits que ejecuta el programa. |
| "…solo existe en Windows" | El servidor no es Windows: use el puente o **Importar tablas**. |
| `comtypes`/`pywin32` instalado y sigue fallando | Python de 32 bits frente a ETABS de 64 bits (o al revés); iguale la arquitectura. |
| "La tabla de fuerzas está vacía" / `sin_tablas` | El modelo no está analizado: `Analyze > Run Analysis`. |
| "No hay barras seleccionadas" | Seleccione barras en ETABS, o use **Todo el modelo**. |
| No aparecen combinaciones | Verifique que existan *Load Combinations* en el modelo. |
| Se cierra ETABS y la app queda "conectada" | Vuelva a pulsar el botón de ETABS: reconecta y, si ya no está, lo explica (`etabs_cerrado`). |

---

## 5. Importación de tablas de ETABS

1. En ETABS: `Display > Tables… > Analysis > Element Forces - Frames`.
2. `File > Export > Tables > to CSV` (o `to Excel`).
3. Opcionalmente exporte también:
   * `Frame Assignments - Section Properties` (barra → sección),
   * `Frame Section Properties - Rectangular` (sección → t3, t2),
   * `Material Properties - Concrete Data` (material → f'c).
4. En la aplicación: **Importar tablas…** y seleccione los archivos.

Archivos de ejemplo listos para probar en `ejemplos/`:

```
ejemplos/ElementForces_Frames.csv            # fuerzas por estación y combinación
ejemplos/FrameSections_Rectangular.csv       # asignaciones + dimensiones
ejemplos/MaterialProperties_Concrete.csv     # f'c
```

Si su exportación no incluye secciones, indique `b` y `h` en el formulario; el
programa usará esos valores para todos los elementos.

---

## 6. Metodología de cálculo (resumen)

### 6.1 Materiales y factores

* `β1` según E.060 10.2.7.3; `Ec = 15000·√f'c` (8.5.1); `Es = 2 000 000 kgf/cm²`.
* `φ` de flexión por deformación neta de tracción (9.3.2, interpolación entre
  εt = εy → 0.65 y εt = 0.005 → 0.90); `φv = 0.85` (9.3.2.3 / 21.2.4.3).

### 6.2 Vigas

* **Flexión**: bloque rectangular equivalente;
  `As,mín = máx(0.7√f'c/fy ; 14/fy)·b·d` (10.5.1);
  ductilidad `εt ≥ 0.004` y `ρ ≤ 0.025` (10.3.4, 21.4.4.1).
* **Selección de barras**: se minimiza el exceso de acero con penalización por
  número de barras y capas, verificando separación libre
  `máx(2.5 cm ; 1.33·db ; 1.33·agregado)` (7.6.1).
* **Corte**: `Vc = 0.53√f'c·bw·d·(1 + Nu/14Ag)` (11.3.1.1);
  `Av/s,mín = máx(0.062√f'c·b/fy ; 0.35·b/fy)` (11.4.6.3);
  `Vs ≤ 2.1√f'c·bw·d` (11.4.7.9).
* **Cortante por capacidad** (21.4.5):
  `Ve = (Mpr_i + Mpr_j)/ln + wu·ln/2` con `Mpr = 1.25·fy·As·(d − a/2)`;
  `Vc = 0` cuando el cortante sismoinducido ≥ 50 % del total (21.4.5.2).
* **Estribos**: zona de confinamiento `s ≤ mín(d/4, 8·db_long, 24·db_est, 30 cm)`
  en `2h ≤ 60 cm` desde el apoyo (21.4.4.2/21.4.4.4) y `s ≤ mín(d/2, 30 cm)` en
  el resto, con `Av/s ≥ Av/s,mín`.
* **Refuerzo continuo**: al menos 2 barras corridas arriba y abajo y, en los
  extremos, `As` de una cara ≥ 25 % de la otra (21.4.4.1).
* **Torsión**: `Tcr = 0.27√f'c·Acp²/Pcp` (11.5.2.2), `At/s` (11.5.3.6) y `Al`
  mínimo (11.5.5.3).

### 6.3 Columnas

* `P0 = 0.85f'c(Ag − As) + fy·As` y `φPn,max = 0.80·φ·P0` (10.3.6).
* **Compatibilidad de deformaciones** sobre la sección completa
  (εcu = 0.003, acero elastoplástico, bloque de Whitney con geometría poligonal)
  para obtener puntos P-Mx-My.
* **Convención de ejes** (idéntica a ETABS): `t3 = h` (peralte) y `t2 = b`
  (ancho); por lo tanto `M3` se verifica con el peralte `h` (`Mux`) y `M2` con
  el ancho `b` (`Muy`).
* **Flexión biaxial exacta**: para la dirección del momento demandado
  `α = atan2(M2, M3)` se resuelve el sistema `φ(c)·P(θ, c) = Pu` sobre la
  superficie de interacción (θ = orientación del eje neutro, c = profundidad)
  por bisección anidada, obteniendo `φMcap` en la dirección exacta de la
  demanda y `D/C = Mdem/φMcap`. No se usa la simplificación de Bresler.
* **Esbeltez**: `k·lu/r ≤ 34 − 12(M1/M2) ≤ 40` (10.10.1.1) y magnificación
  **por eje**: `δns = Cm/(1 − Pu/0.75Pc)` con `Ig3 = b·h³/12` para M3 e
  `Ig2 = h·b³/12` para M2 (10.10.7).
* **Excentricidad mínima** `Mmín = Pu(1.5 + 0.03·h)` (10.10.6.5), de modo que
  la columna se verifica aunque el análisis entregue momentos nulos.
* **Tracción**: si alguna combinación deja la columna en tracción se verifica
  `Pu ≤ φPn,t = 0.90·fy·As` (10.3.5).
* **Confinamiento**: `Ash/s ≥ máx[0.3(Ag/Ach−1)f'c/fy ; 0.09f'c/fy]·bc`
  (21.4.4.4), `s ≤ mín(b/4, 10 cm, 6·db_long, 24·db_est)` y
  `lo ≥ máx(b, h, lu/6, 45 cm)`; el número de ramas se elige para que el
  espaciamiento resulte constructivo (≥ 8 cm) en lugar de forzar ramas
  innecesarias.
* **Selección de refuerzo**: búsqueda de la distribución (n.º de barras por cara
  y diámetro) de menor costo que cumple todos los estados de carga, con
  separación entre barras ≤ 30 cm y 1 % ≤ ρ ≤ 6 %.

### 6.4 Combinaciones

E.060 9.2 y E.030-2018 art. 1.4.2: `1.4CM+1.7CV`, `1.2CM+1.6CV+0.5CVt`,
`1.2CM+1.0CV±CS`, `1.2CM+1.6CVt`, `0.9CM±CS`, `1.25(CM+CV)±CS`, `CM+CV`.

> ETABS entrega las solicitaciones ya combinadas; el programa usa directamente
> cada combinación del modelo y calcula las envolventes.

---

## 7. Memoria de cálculo

Se genera automáticamente para el elemento seleccionado e incluye:

1. Datos generales e identificación del elemento.
2. Materiales, `β1`, `Ec`, recubrimientos y factores `φ`.
3. Solicitaciones por estación con la combinación gobernante.
4. Diseño por flexión: fórmulas con valores sustituidos, refuerzo adoptado,
   verificación de espaciamiento, capas y ductilidad.
5. Diseño por corte y torsión: Vc, Vs, Av/s, espaciamientos por zona, torsión.
6. Requisitos sismorresistentes del capítulo 21.
7. Columnas: esbeltez, `P0`, `φPn,max`, verificación biaxial por combinación,
   confinamiento y cortante.
8. Cuadro de verificaciones (CUMPLE / NO CUMPLE) y conclusiones.
9. Anexos gráficos: sección transversal, diagrama de interacción, envolvente de
   momentos, distribución de estribos.

Salidas: **HTML** (autocontenido, imprimible a PDF desde el navegador), **PDF**
(con `reportlab`) y **Markdown**.

---

## 8. Estructura del proyecto

```
diseno-viga-concreto/
├── e060/                     # motor de cálculo (sin dependencias externas)
│   ├── normas.py             # φ, β1, acero mínimo, varillas, requisitos cap. 21
│   ├── unidades.py           # conversión de unidades (sistemas de ETABS)
│   ├── seccion.py            # compatibilidad de deformaciones, P-Mx-My biaxial
│   ├── viga.py               # diseño de vigas (flexión, corte, torsión)
│   ├── columna.py            # diseño de columnas (biaxial, esbeltez, confinamiento)
│   ├── combinaciones.py      # combinaciones y envolventes
│   ├── etabs/                # conectores: COM/OAPI, tablas, exportación y demo
│   ├── servicio.py           # orquestación elemento → diseño → memoria
│   ├── figuras.py            # figuras SVG
│   ├── memoria.py            # memoria de cálculo (HTML/PDF/Markdown)
│   └── cli.py                # consola (python -m e060.cli)
├── web/index.html            # interfaz web (una sola página, sin dependencias)
├── servidor.py               # servidor web local + API JSON
├── puente_etabs.py           # puente: exporta de ETABS (Windows) y sube a la web
├── app_escritorio.py         # interfaz Tkinter (Windows/ETABS)
├── ejemplos/                 # tablas de ETABS de ejemplo (y su generador)
├── tests/test_e060.py        # pruebas automáticas del motor y de la conexión
├── tests/simulador_com.py    # simulador de la API COM/OAPI de ETABS (sin Windows)
├── legado/                   # versión 3 (solo vigas, entrada manual)
└── salidas/                  # memorias generadas (no versionado)
```

---

## 9. Pruebas

```bash
python -m unittest discover -s tests -v
```

Cubren: factores normativos, conversión de unidades, geometría de secciones,
`P0`, diagrama de interacción (uniaxial y biaxial, simetría), diseño de vigas,
columnas, confinamiento, cortante por capacidad, el modelo demo completo
(28 elementos), importación de tablas de ejemplo, figuras SVG (validación XML),
generación de la memoria en HTML, Markdown y PDF, el puente de exportación y la
**conexión COM/OAPI con ETABS simulada** (`tests/simulador_com.py`): lectura de
las tablas del modelo, estaciones reales, clasificación viga/columna, unidades
(con restitución), backends `comtypes` y `win32com`, «solo selección», conexión
desde otro hilo y todos los errores de conexión explicados.

Incluye una **validación independiente de la sección**: los valores `P` y `M`
de una fibra se comparan contra una integración numérica por franjas
(`test_equilibrio_integracion_independiente`) y la capacidad biaxial en α = 0°
se compara con la uniaxial (`test_biaxial_coincide_con_uniaxial`).

---

## 10. Alcance y responsabilidad

El programa automatiza el **diseño seccional** de vigas y columnas según E.060.
No sustituye:

* la verificación global de la estructura (derivas, irregularidades, torsión en
  planta, columna fuerte–viga débil, losas, cimentación),
* el detalle de anclajes, empalmes, ganchos y compatibilidad con otras
  especialidades,
* la revisión y firma del **ingeniero estructural responsable**.

Los resultados deben interpretarse junto con el modelo de ETABS del proyecto.
