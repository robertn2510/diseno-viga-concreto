# Diseño de vigas de concreto armado según la NTE E.060 (Perú)

Programa en Python que se conecta a **ETABS v18–v23** por COM (`comtypes` o
`pywin32`), extrae las fuerzas internas de las vigas de concreto y genera la
memoria de cálculo a flexión y cortante según la **Norma Técnica E.060
Concreto Armado** del Reglamento Nacional de Edificaciones.

El diseño cubre:

- **Flexión** con armadura simple y doble, acero mínimo, límites de ductilidad
  y selección de varillas comerciales.
- **Cortante** con estribos, zona de confinamiento de 2h, cortante por
  capacidad (Mpr = 1.25·Mn) y reducción de Vc a cero según 21.5.4.2.
- **Requisitos sísmicos** del capítulo 21 para vigas de pórticos especiales a
  momento y sistemas duales tipo II: geometría, refuerzo continuo, cuantía
  máxima, relación de momentos y detalles de estribado.
- **Memoria de cálculo** en Markdown y/o Word (.docx) con fórmulas sustituidas,
  acero teórico vs. colocado, verificación de combinaciones y trazabilidad
  ETABS.

---

## 1. Requisitos

| Componente | Requisito |
| --- | --- |
| Sistema operativo | **Windows** para conectarse a ETABS (la API es COM). El modo demostración y los tests funcionan en Linux/macOS. |
| ETABS | v18, v19, v20, v21, v22 o v23, con el modelo abierto y el análisis ejecutado. |
| Python | 3.9 o superior. |
| COM | `comtypes` (recomendado) **o** `pywin32`. |
| Reporte Word | `python-docx` (opcional; si no está, se genera solo Markdown). |

Instalación:

```bash
pip install -r requirements.txt
```

Para desarrollo y pruebas:

```bash
pip install -r requirements-dev.txt
pytest -q
```

También puede instalarse como paquete (`pip install -e .`) y usar el comando
`vigas-e060`, equivalente a `python main.py`.

> En algunos Linux con Python administrado por el sistema, `pip install` falla
> con `externally-managed-environment`. Use un entorno virtual:
> `python -m venv .venv` y active el entorno antes de instalar.

---

## 2. Uso rápido

### 2.1 Modo demostración (sin ETABS)

Genera tres vigas sintéticas, las diseña y escribe la memoria:

```bash
python main.py --demo
```

Salida típica:

```text
Viga   Piso    b×h    M+ (t·m)  M− (t·m)  V (t)  Sup. apoyo  Inf. centro  Estribado (izq. | resto | der.)                                     Estado
-----  ------  -----  --------  --------  -----  ----------  -----------  ------------------------------------------------------------------  ------
V-101  Piso 2  25×50  10.00     19.00     20.00  5 Φ 5/8"    6 Φ 1/2"     1 @ 0.05, 9 @ 0.10 m | Resto: 17 @ 0.21 m | 9 @ 0.10, 1 @ 0.05 m    CUMPLE
V-201  Piso 3  30×60  22.00     36.00     28.00  3 Φ 1"      10 Φ 1/2"    1 @ 0.05, 11 @ 0.10 m | Resto: 18 @ 0.26 m | 11 @ 0.10, 1 @ 0.05 m  CUMPLE
V-301  Piso 1  25×50  12.00     31.00     30.00  3 Φ 1"      4 Φ 5/8"     1 @ 0.05, 10 @ 0.09 m | Resto: 13 @ 0.20 m | 10 @ 0.09, 1 @ 0.05 m  CUMPLE
```

Los archivos se guardan en `salidas/`:
`memoria_vigas_E060_<proyecto>_<fecha>.md` y `.docx`. En
`docs/ejemplo/` se incluye una memoria de ejemplo generada con este modo.

### 2.2 Con ETABS abierto

1. Abra ETABS y el modelo `.edb`.
2. Ejecute el análisis (`Analyze > Run Analysis`).
3. Desde la carpeta del proyecto:

```bash
python main.py --listar
```

`--listar` muestra las vigas rectangulares de concreto detectadas, sin
diseñarlas:

```bash
python main.py --seccion VP-25x50 --piso "Piso 2" --formato ambos
python main.py --vigas V-101,V-102 --proyecto "Edificio A" --salida salidas
```

Si el modelo usa nombres de casos distintos de `DEAD`/`LIVE`/`SISMO`, indíquelos:

```bash
python main.py \
  --caso-muerta CM --caso-viva CV --caso-sismo "SISMO X,SISMO Y" \
  --proyecto "Edificio A" --ubicacion "Cusco, Perú"
```

Las combinaciones E.060 se generan y se comparan con las del modelo. Si faltan,
el programa se detiene y muestra el detalle; con `--crear-combos` las crea en
ETABS (el modelo debe estar desbloqueado) y con `--analizar` ejecuta el análisis
después de crearlas:

```bash
python main.py --crear-combos --analizar --caso-sismo "SISMO X"
```

### 2.3 Variante del factor sísmico

Por defecto se usan las combinaciones solicitadas en el proyecto:

```text
U = 1.4D + 1.7L
U = 1.25(D + L) ± 1.25S
U = 0.9D ± 1.25S
```

La E.060 2009 se reproduce en algunas ediciones con `±CS` (factor 1.0). Para
usar esa variante:

```bash
python main.py --norma-combos e060-2009
```

La variante adoptada se documenta en la sección 2.2 de la memoria.

---

## 3. Opciones de línea de comandos

| Opción | Descripción |
| --- | --- |
| `--demo` | Ejecuta el caso sintético, sin ETABS. |
| `--listar` | Lista las vigas detectadas y sale. |
| `--vigas A,B` | Filtra por nombre o etiqueta de viga. |
| `--seccion VP-25x50` | Filtra por nombre de sección (subcadena). |
| `--piso "Piso 2"` | Filtra por piso (subcadena). |
| `--max-vigas N` | Procesa como máximo N vigas. |
| `--caso-muerta`, `--caso-viva`, `--caso-sismo` | Nombres de los casos de carga. |
| `--crear-combos` | Crea en ETABS las combinaciones E.060 faltantes. |
| `--analizar` | Ejecuta el análisis después de crear combinaciones. |
| `--norma-combos {usuario,e060-2009}` | Factor 1.25 o 1.0 sobre la acción sísmica. |
| `--fc` | Fuerza f'c en kgf/cm² (si no, se lee del material de ETABS). |
| `--fy` | fy en kgf/cm² (por defecto 4200). |
| `--recubrimiento` | Recubrimiento libre al estribo en cm (por defecto 4.0). |
| `--usar-recubrimiento-etabs` | Estima r a partir del recubrimiento al centroide definido en ETABS. |
| `--estribo` | Diámetro de estribo (por defecto `3/8"`). |
| `--fraccion-rho-b` | 0.75 (por defecto) o 0.50. |
| `--salida DIR` | Carpeta de salida (por defecto `salidas`). |
| `--formato {md,docx,ambos}` | Formato de la memoria. |
| `--crear-instancia` | Abre una instancia nueva de ETABS. |
| `--ruta-etabs` | Ruta de `ETABS.exe` si se crea una instancia. |
| `--pywin32` | Usa pywin32 en lugar de comtypes. |
| `--modelo RUTA.edb` | Abre un modelo después de conectar. |
| `--proyecto`, `--ubicacion`, `--cliente`, `--ingeniero`, `--revision` | Datos de la portada. |
| `--verbose` | Muestra la traza completa si hay un error. |

---

## 4. Estructura del paquete

```text
vigas_e060/
├── __init__.py            # API pública: conectar_etabs, extraer_fuerzas,
│                          # diseno_flexion, diseno_cortante, generar_reporte
├── __main__.py            # python -m vigas_e060
├── cli.py                 # interfaz de línea de comandos
├── config.py              # ConfiguracionDiseno
├── unidades.py            # conversión de unidades ETABS → sistema técnico
├── modelos.py             # dataclasses de entrada, fuerzas y resultados
├── demo.py                # datos sintéticos (MODO_DEMO)
├── normativa/
│   └── e060.py            # fórmulas y límites de la E.060
├── calculo/
│   ├── varillas.py        # catálogo y selección de barras comerciales
│   ├── flexion.py         # diseño a flexión
│   ├── cortante.py        # diseño a cortante y estribado
│   └── diseno.py          # orquestación + verificaciones del capítulo 21
├── etabs/
│   ├── api.py             # utilidades para tuplas COM
│   ├── conexion.py        # conexión COM v18–v23 (comtypes/pywin32)
│   ├── combos.py          # combinaciones E.060 y verificación en ETABS
│   └── extraccion.py      # geometría, materiales y fuerzas internas
└── reporte/
    ├── documento.py       # modelo de documento independiente del formato
    ├── markdown.py        # render Markdown
    ├── docx_render.py     # render Word (python-docx)
    └── generador.py       # memoria de cálculo completa
```

`diseno_viga_concreto_v3.py` se conserva como la versión anterior (GUI Tkinter
para diseño manual). La versión 4 es el paquete `vigas_e060`.

---

## 5. Criterios de diseño aplicados

### 5.1 Unidades

El núcleo trabaja en **kgf, cm, kgf/cm² y kgf·cm**. La memoria presenta
**t, t·m, cm y kgf/cm²**. ETABS se configura en `kgf_m` (eUnits = 8) y la
conversión se hace en `ConexionETABS`; si no se puede cambiar la unidad, se
convierten los resultados desde la unidad presente.

### 5.2 Combinaciones (E.060 9.2)

| Combinación | Referencia |
| --- | --- |
| `1.4D + 1.7L` | 9.2.1 |
| `1.25(D + L) ± 1.25S` | 9.2.3 (variante del proyecto) |
| `0.9D ± 1.25S` | 9.2.3 |

Cada combinación requerida se compara con las definidas en ETABS (casos y
factores). Solo se usan para extraer fuerzas las que coinciden exactamente o
las creadas por el programa; las parciales se informan y no se usan.

### 5.3 Flexión

| Tema | Artículo |
| --- | --- |
| β1 | 10.2.7.3 |
| ρb | 10.3.2 |
| φ = 0.90 (εt ≥ 0.005), interpolación | 9.3.2.1 / 9.3.2.2 |
| As,mín = 0.7√f'c·b·d/fy | 10.5.1 |
| ρ ≤ 0.025 en vigas sísmicas | 21.5.2.2 |
| εt ≥ 0.004 (ductilidad) | 10.3.5 |
| Mn+ ≥ Mn−/2 en la cara del nudo | 21.5.2.3 |
| Mn ≥ Mn,max/4 en toda la viga | 21.5.2.4 |
| Dos barras continuas superior e inferior | 21.5.2.1 |

El programa resuelve la ecuación cuadrática de flexión simple; si `Mu` supera
la capacidad con εt = 0.005, diseña armadura doble fijando `c = 0.375d` y
calculando `As'` por equilibrio y compatibilidad. Luego selecciona barras
comerciales, recalcula el peralte efectivo real (centroide de la armadura) y
verifica `φMn ≥ Mu` con el φ real. Si la continuidad 21.5.2.3/21.5.2.4 exige
más acero, lo aumenta automáticamente y lo reporta como sección ampliada.

### 5.4 Cortante

| Tema | Artículo |
| --- | --- |
| Vc = 0.53√f'c·b·d | 11.3.1.1 |
| φ = 0.85 | 9.3.2.3 |
| Vs ≤ 2.1√f'c·b·d | 11.5.6.9 |
| Av,mín/s | 11.5.6.3 |
| s ≤ d/2 ≤ 60 cm | 11.5.5.1 |
| Mpr = 1.25 Mn; Ve = ΣMpr/ln | 21.5.4.1 |
| Vc = 0 en confinamiento si Ve/Vu ≥ 0.50 y P < 0.05f'cAg | 21.5.4.2 |
| Zona de confinamiento 2h | 21.5.3.1 |
| Primer estribo ≤ 5 cm | 21.5.3.3 |
| sconf ≤ mín(d/4; 8db,long; 24db,est; 30 cm) | 21.5.3.4 |
| scentral ≤ d/2 | 21.5.3.5 |
| Separación entre ramas ≤ 30 cm | 21.5.3.6 |
| Estribo mínimo 3/8" (1/2" si db,long > 1") | 21.5.3.2 |

El cortante de diseño es `Vu = máx(Ve + Vg; V_ETABS)` en la cara del apoyo y
en el centro. El estribado se detalla por tramos:

```text
1 @ 0.05, 9 @ 0.10 m | Resto: 17 @ 0.21 m | 9 @ 0.10, 1 @ 0.05 m
```

El tramo derecho se detalla desde el eje de columna hacia el centro de la luz
(primero la separación menor y al final el estribo a 5 cm de la cara).

---

## 6. Uso como biblioteca

Las cinco funciones requeridas están disponibles en la raíz del paquete:

```python
from vigas_e060 import (
    ConfiguracionDiseno, conectar_etabs, extraer_vigas, extraer_fuerzas,
    diseno_flexion, diseno_cortante, generar_reporte,
)
from vigas_e060.calculo.diseno import disenar_viga

config = ConfiguracionDiseno(proyecto="Edificio A", fc_default=210)

conexion = conectar_etabs()                  # ETABS abierto y analizado
vigas = extraer_vigas(conexion, config)      # geometría, materiales, filtros
viga = vigas[0]
fuerzas = extraer_fuerzas(conexion, viga, ["E060-1.4D+1.7L", "..."],
                          combo_gravedad="E060-1.4D+1.7L")
resultado = disenar_viga(viga, fuerzas, config)   # flexión + cortante + Cap. 21
```

`diseno_flexion` y `diseno_cortante` son alias de `disenar_flexion` y
`disenar_cortante`; reciben la geometría, los materiales y la configuración, y
devuelven los objetos `ResultadoFlexion` / `ResultadoCortante` con fórmulas y
verificaciones. `disenar_viga` orquesta ambas y aplica los mínimos de
continuidad del capítulo 21.

---

## 7. Memoria de cálculo

Cada viga incluye:

1. Identificación: ID, piso (Story), eje, sección, nudos, luces y apoyos.
2. Materiales y geometría con β1, ρb, d, recubrimiento.
3. Fuerzas críticas de ETABS en I-End, cara de apoyo, centro y J-End, más los
   máximos globales con su combinación y estación.
4. Flexión paso a paso: fórmulas, valores sustituidos, As teórico, varillas
   comerciales, As' cuando hay doble refuerzo, φMn y verificaciones.
5. Cortante paso a paso: Mpr, Ve, Vg, Vu, Vc, Vs, separaciones, distribución de
   estribos, número de piezas y peso aproximado.
6. Verificaciones globales del capítulo 21 y observaciones.

Además: resumen global, verificación de combinaciones, criterio del factor
sísmico, anexos de formulación, trazabilidad ETABS y registro de observaciones.

---

## 8. Pruebas

```bash
pytest -q
```

La suite incluye:

- Fórmulas de la E.060 (β1, ρb, As,mín, φ, momento nominal, cortante).
- Catálogo y colocación de varillas.
- Extracción de geometría y fuerzas con un `SapModel` simulado que reproduce
  las tuplas de la API ETABS.
- Generación y verificación de combinaciones.
- Diseño completo de las tres vigas del demo.
- Memoria Markdown y DOCX.
- Flujo de la CLI, incluido el flujo ETABS simulado.

Resultado esperado: **54 pruebas aprobadas**.

> El `SapModel` simulado está en `tests/conftest.py`. No sustituye una prueba
> real en ETABS, pero valida el orden de las tuplas, las unidades y el flujo
> completo.

---

## 9. Limitaciones

- La conexión COM solo funciona en Windows con ETABS instalado; Python y
  ETABS deben tener la misma arquitectura (normalmente 64 bits).
- No se diseña torsión; si `T` es significativa, se debe hacer un diseño
  específico (E.060 11.6).
- No se verifican deflexiones, fisuración, longitudes de desarrollo ni
  traslapes; la memoria indica el armado y el estribado, pero el despiece debe
  completarse en el proyecto.
- No se diseña la losa colaborante; las secciones se tratan como rectangulares.
- Si una sección no resiste la demanda, el programa coloca la mayor armadura
  comercial que cumple ρ ≤ 0.025 y deja la verificación en **NO CUMPLE** con
  una advertencia; no se inventa una solución no verificable.
- Las fuerzas dependen de que el modelo ETABS esté correctamente cargado y
  analizado. La memoria es una ayuda de cálculo y debe ser revisada por un
  ingeniero estructural colegiado.

---

## 10. Referencias

- NTE E.060 Concreto Armado, D.S. N° 010-2009, Reglamento Nacional de
  Edificaciones del Perú.
- NTE E.020 Cargas.
- NTE E.030 Diseño Sismorresistente.
- ACI 318, como referencia concordante para los artículos no desarrollados
  explícitamente en la E.060.
