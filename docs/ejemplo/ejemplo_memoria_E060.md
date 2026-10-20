# MEMORIA DE CÁLCULO


## DISEÑO DE VIGAS DE CONCRETO ARMADO — NORMA E.060

Diseño por flexión y cortante de vigas rectangulares de concreto armado, con extracción automática de fuerzas internas desde ETABS y verificación de las disposiciones sísmicas del capítulo 21 de la Norma Técnica E.060 del Reglamento Nacional de Edificaciones.

| Dato | Valor |
| --- | --- |
| Proyecto | Edificio demostración — Cusco |
| Ubicación | Cusco, Perú |
| Cliente | Cliente demostración |
| Ingeniero responsable | Ing. Estructural |
| Revisión | A |
| Fecha | 20/10/2026 |
| Software | vigas-e060 — Python + API ETABS (comtypes/pywin32) |
| Versión ETABS | v23 (datos sintéticos) |
| Modelo ETABS | demo_vigas.edb |
| Ruta del modelo | — |
| Número de vigas | 3 |
| Observaciones | Caso demostrativo generado por vigas_e060. |

> **Nota:** Este documento es una memoria de cálculo asistida por computadora. Los resultados deben ser revisados y validados por un ingeniero estructural colegiado antes de su uso en obra.


---


# 1. GENERALIDADES


## 1.1 Alcance

- Diseño a flexión de vigas rectangulares de concreto armado, incluyendo armadura simple y doble.
- Diseño a cortante con estribos, zona de confinamiento y cortante por capacidad para pórticos especiales a momento y sistemas duales tipo II.
- Verificación de límites de acero, ductilidad, cuantías y detalles mínimos del capítulo 21 de la E.060.
- Generación de memoria de cálculo por elemento y resumen global.


## 1.2 Normativa aplicada

- NTE E.060 Concreto Armado — D.S. N° 010-2009 (RNE).
- NTE E.020 Cargas.
- NTE E.030 Diseño Sismorresistente.
- ACI 318-05 / ACI 318-08 como referencia concordante para los artículos no desarrollados explícitamente en la E.060.


## 1.3 Unidades y convención

| Magnitud | Unidad de cálculo | Unidad de reporte |
| --- | --- | --- |
| Longitud | cm | cm / m |
| Fuerza | kgf | t |
| Momento | kgf·cm | t·m |
| Esfuerzo | kgf/cm² | kgf/cm² |
| Área de acero | cm² | cm² |

Convención de momentos: M3 positivo = tracción en fibra inferior (sagging); M3 negativo = tracción en fibra superior (hogging). La armadura superior se diseña para el momento negativo y la inferior para el positivo. Si el modelo ETABS tiene los ejes locales rotados, el usuario debe verificar la convención antes de usar los resultados.


## 1.4 Limitaciones

- No se diseña torsión; ETABS reporta T pero la memoria solo la informa. Si T es significativa, se debe hacer un diseño específico (E.060 11.6).
- No se verifica deflexión ni fisuración por servicio.
- No se diseñan columnas, nudos ni cimentación.
- No se verifican longitudes de desarrollo, traslapes ni detalles de anclaje; se indica el detalle de estribado y el armado longitudinal.
- El diseño asume secciones rectangulares sin losa colaborante; si la viga es parte de un sistema T, debe revisarse el ancho efectivo.
- Las fuerzas se toman de ETABS; la calidad del resultado depende del modelo, las combinaciones y el análisis ejecutado.


---


# 2. COMBINACIONES DE CARGA

La resistencia requerida se evaluó con las combinaciones de la E.060, artículo 9.2. El programa verifica que cada combinación requerida exista en ETABS con los mismos casos y factores; las combinaciones ausentes se informan y, si se solicita, se crean automáticamente.

| N° | Combinación requerida | Factores | Referencia | Combinación ETABS | Estado | Detalle |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | E060-1.4D+1.7L | 1.4·DEAD + 1.7·LIVE | E.060 9.2.1 (9-1) | E060-1.4D+1.7L | COINCIDE | Caso demostrativo: combinación declarada en el modelo sintético. |
| 2 | E060-1.25(D+L)+1.25SISMOX | 1.25·DEAD + 1.25·LIVE + 1.25·SISMO X | E.060 9.2.3 (9-4) — variante 1.25·CS | E060-1.25(D+L)+1.25SISMOX | COINCIDE | Caso demostrativo: combinación declarada en el modelo sintético. |
| 3 | E060-1.25(D+L)-1.25SISMOX | 1.25·DEAD + 1.25·LIVE − 1.25·SISMO X | E.060 9.2.3 (9-4) — variante 1.25·CS | E060-1.25(D+L)-1.25SISMOX | COINCIDE | Caso demostrativo: combinación declarada en el modelo sintético. |
| 4 | E060-0.9D+1.25SISMOX | 0.9·DEAD + 1.25·SISMO X | E.060 9.2.3 (9-5) — variante 1.25·CS | E060-0.9D+1.25SISMOX | COINCIDE | Caso demostrativo: combinación declarada en el modelo sintético. |
| 5 | E060-0.9D-1.25SISMOX | 0.9·DEAD − 1.25·SISMO X | E.060 9.2.3 (9-5) — variante 1.25·CS | E060-0.9D-1.25SISMOX | COINCIDE | Caso demostrativo: combinación declarada en el modelo sintético. |


## 2.1 Combinaciones de diseño de concreto en ETABS

ETABS reporta las siguientes combinaciones para el diseño de concreto:

- E060-1.4D+1.7L
- E060-1.25(D+L)+1.25SISMOX
- E060-1.25(D+L)-1.25SISMOX
- E060-0.9D+1.25SISMOX
- E060-0.9D-1.25SISMOX


## 2.2 Criterio sobre el factor sísmico

La variante adoptada en este proyecto es U = 1.25(D + L) ± 1.25S y U = 0.9D ± 1.25S (factor 1.25 sobre la acción sísmica). La E.060 2009, artículo 9.2.3, se reproduce en algunas ediciones con ±CS (factor 1.0), mientras que la edición 2006 y la práctica ACI emplean ±1.25CS. El programa permite ambas variantes con el parámetro --norma-combos; la variante usada se indica en la tabla anterior.


---


# 3. RESUMEN DE RESULTADOS

| Viga | Piso | b×h (cm) | ln (m) | M+ (t·m) | M− (t·m) | V (t) | Estribos (zona conf.) | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V-101 | Piso 2 | 25×50 | 5.40 | 10.00 | 19.00 | 20.00 | 1 @ 0.05, 9 @ 0.10 m | CUMPLE CON OBSERVACIONES |
| V-201 | Piso 3 | 30×60 | 6.90 | 22.00 | 36.00 | 28.00 | 1 @ 0.05, 11 @ 0.10 m | CUMPLE CON OBSERVACIONES |
| V-301 | Piso 1 | 25×50 | 4.40 | 12.00 | 31.00 | 30.00 | 1 @ 0.05, 10 @ 0.09 m | CUMPLE CON OBSERVACIONES |

> **Nota:** M+ y M− son los máximos de la envolvente en toda la longitud de la viga, incluidos los ejes de columna; el diseño a flexión se realiza en la cara del apoyo y en el centro de la luz. De igual modo, la columna V (t) es la envolvente global y el cortante de diseño se toma en la cara del apoyo (E.060 21.5.4.1).

Se procesaron 3 vigas. Se registraron 9 observaciones; consulte el detalle por elemento y el Anexo C.


---


# 4. MEMORIA DE CÁLCULO POR VIGA

Cada elemento incluye identificación, materiales, geometría, fuerzas críticas, fórmulas con valores sustituidos, comparación de acero teórico vs. colocado y detalle de estribado.


## 4.1 Viga V-101 — Piso 2

Elemento V-101 de sección VP-25x50, ubicado en Piso 2 (Eje A-A / B). Diseño según E.060 para f'c = 210 kgf/cm² y fy = 4200 kgf/cm².


### Identificación del elemento

| Identificación | Valor | Identificación | Valor |
| --- | --- | --- | --- |
| ID de la viga | V-101 | Nombre ETABS | V-101 |
| Piso (Story) | Piso 2 | Eje / ubicación | Eje A-A / B |
| Sección | VP-25x50 | Material | Concreto f'c = 210 kgf/cm² |
| Nudo I | V-101-I | Nudo J | V-101-J |
| Coordenada I (m) | (0.00; 0.00; 3.00) | Coordenada J (m) | (6.00; 0.00; 3.00) |
| L entre ejes (m) | 6.000 | Luz libre ln (m) | 5.400 |
| Apoyos detectados | COL-1 / COL-2 | Recubrimiento libre r (cm) | 4.00 |


### Propiedades de materiales y geometría

| Parámetro | Símbolo | Valor | Unidad | Referencia |
| --- | --- | --- | --- | --- |
| Resistencia del concreto | f'c | 210.0 | kgf/cm² | E.060 4.2 / 5 |
| Fluencia del acero longitudinal | fy | 4200 | kgf/cm² | E.060 4.3 |
| Fluencia del acero transversal | fyt | 4200 | kgf/cm² | E.060 4.3 |
| Módulo de elasticidad del acero | Es | 2000000 | kgf/cm² | E.060 10.2.4 |
| Factor del bloque rectangular | β1 | 0.850 | — | E.060 10.2.7.3 |
| Cuantía balanceada | ρb | 0.02125 | — | E.060 10.3.2 |
| Ancho | b | 25.0 | cm | — |
| Peralte total | h | 50.0 | cm | — |
| Peralte efectivo estimado | d | 44.09 | cm | E.060 10.2.2 |
| Recubrimiento libre al estribo | r | 4.00 | cm | E.060 7.6.1 |
| Diámetro de estribo | Øe | 0.953 | cm | E.060 21.5.3.2 |
| Área bruta | Ag | 1250.0 | cm² | — |
| Longitud entre ejes | L | 6.000 | m | — |
| Luz libre | ln | 5.400 | m | E.060 21.5.1.1 |

> **Nota:** ETABS reporta un recubrimiento al centroide de la armadura de 6.00 cm. El valor de r usado en el diseño es el recubrimiento libre al estribo (4.00 cm).


### Resumen de cargas y momentos críticos de ETABS

| Estación | x (m) | M3 máx (t·m) | M3 mín (t·m) | \|V2\| máx (t) | P mín / máx (t) | \|T\| máx (t·m) | Combo M3 mín |
| --- | --- | --- | --- | --- | --- | --- | --- |
| I-End | 0.000 | -5.00 | -18.00 | 20.00 | -2.80 / -1.50 | 0.00 | E060-1.25(D+L)+1.25SISMOX |
| Cara-I | 0.300 | -3.39 | -13.06 | 18.00 | -2.80 / -1.50 | 0.00 | E060-1.25(D+L)+1.25SISMOX |
| Centro | 3.000 | 10.00 | 4.00 | 0.00 | -2.80 / -1.50 | 0.00 | E060-0.9D-1.25SISMOX |
| Cara-J | 5.700 | -4.29 | -13.96 | 18.00 | -2.80 / -1.50 | 0.00 | E060-1.25(D+L)+1.25SISMOX |
| J-End | 6.000 | -6.00 | -19.00 | 20.00 | -2.80 / -1.50 | 0.00 | E060-1.25(D+L)+1.25SISMOX |

| Máximo global | Valor | Estación (m) | Combinación |
| --- | --- | --- | --- |
| Momento positivo M+ | 10.00 t·m | 3.000 | E060-1.25(D+L)+1.25SISMOX |
| Momento negativo M− | 19.00 t·m | 6.000 | E060-1.25(D+L)+1.25SISMOX |
| Cortante \|V2\| | 20.00 t | 0.000 | E060-1.25(D+L)+1.25SISMOX |
| Torsión \|T\| | 0.00 t·m | — | — |
| Compresión máxima P | 2.80 t | — | — |
| Cortante gravitacional en caras | 12.60 / 12.60 t | — | E060-1.4D+1.7L |

> **Nota:** Convención: M3 positivo produce tracción en la fibra inferior (momento positivo o sagging); M3 negativo produce tracción en la fibra superior (momento negativo o hogging). V2 y P se presentan en valor absoluto y con signo según ETABS, respectivamente. Verifique los ejes locales del elemento si el modelo tiene rotaciones distintas de la vertical.


### Diseño por flexión

Se diseñaron las secciones críticas de apoyo y centro, además de las estaciones donde la envolvente global alcanza sus máximos dentro de la luz libre (los valores en el eje de la columna no son secciones de diseño). El acero mínimo se verificó en todas las secciones (E.060 10.5.1) y la cuantía máxima se limitó a 0.025 (E.060 21.5.2.2). El factor φ se recalcula a partir de la deformación εt (E.060 9.3.2). Las secciones marcadas con (*) se ampliaron para cumplir los mínimos de continuidad Mn+ ≥ Mn−/2 y Mn ≥ Mn,max/4 (E.060 21.5.2.3 y 21.5.2.4).

| Sección | Fibra | Mu (t·m) | As req (cm²) | As prov (cm²) | Varillas | Doble | φMn (t·m) | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Apoyo izquierdo (cara) | superior | 13.06 | 9.00 | 9.90 | 5 Φ 5/8" | No | 14.21 | CUMPLE |
| Apoyo izquierdo (cara) (*) | inferior | 7.32 | 4.58 | 5.08 | 4 Φ 1/2" | No | 8.07 | CUMPLE |
| Centro | inferior | 10.00 | 6.72 | 7.62 | 6 Φ 1/2" | No | 11.22 | CUMPLE |
| Centro | superior | 0.00 | 2.68 | 3.81 | 3 Φ 1/2" | No | 6.14 | CUMPLE |
| Apoyo derecho (cara) | superior | 13.96 | 9.71 | 9.90 | 5 Φ 5/8" | No | 14.21 | CUMPLE |
| Apoyo derecho (cara) (*) | inferior | 7.32 | 4.58 | 5.08 | 4 Φ 1/2" | No | 8.07 | CUMPLE |


#### Detalle: Apoyo derecho (cara) — fibra superior (Mu de diseño = 13.96 t·m)

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Apoyo derecho (cara) | Fibra diseñada | superior |
| Mu (t·m) | 13.963 | d (cm) | 42.62 |
| As mínimo (cm²) | 2.573 | As máximo (cm²) | 14.434 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 19.547 |
| As calculado (cm²) | 9.708 | As requerido (cm²) | 9.708 |
| As colocado (cm²) | 9.900 | Varillas | 5 Φ 5/8" |
| ¿Doble refuerzo? | No | As' requerido (cm²) | — |
| As' colocado (cm²) | — | Varillas de compresión | — |
| a (cm) | 9.318 | c (cm) | 10.962 |
| εt | 0.00866 | φ | 0.900 |
| Mn (t·m) | 15.784 | φMn (t·m) | 14.205 |
| As colocado / requerido | 1.02 | Estado | CUMPLE |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 210 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(210/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02125
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√210/4200 · 25.0 · 42.62 = 2.573 cm²
→ As,min = 2.573 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(16.981; 14.434; 26.637) = 14.434 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 13.585 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 19.547 t·m
```

**E.060 10.2.2**
```text
Armadura superior
Mu− produce tracción en la cara superior; d se mide desde el borde superior.
d = h − r − Øe − Ø/2 = 50.0 − ... = 42.62 cm
→ d = 42.62 cm
```

**E.060 10.3.1**
```text
Ecuación de flexión simple
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
13.963·10⁵ = 0.90·As·4200·(42.62 − As·4200/(2·0.85·210·25.0))
→ As = 9.708 cm²  (discriminante = 1.978e+10)
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 9.900·4200/(0.85·210·25.0) = 9.318 cm; c = 10.962 cm
→ a = 9.318 cm; c = 10.962 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(42.62 − 10.962)/10.962 = 0.00866
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 9.900·4200·(42.62 − 9.318/2)/10⁵
→ Mn = 15.784 t·m; φMn = 14.205 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
5 Φ 5/8" → As,prov = 9.900 cm² ≥ 9.708 cm²
→ 5 Φ 5/8"  (d = 42.62 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 9.900 cm² | As,min = 2.573 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.00929 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Límite de armadura simple (ductilidad) | As = 9.900 cm² | As,max = 14.434 cm² | CUMPLE | E.060 10.3.5 / 9.3.2.1 | El límite asegura εt ≥ 0.005 y φ = 0.90. |
| Control de ductilidad | εt = 0.00866 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.00866) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 14.205 t·m | Mu = 13.963 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 5.17 cm | s ≥ máx(Ø; 2.5 cm) = 2.50 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 5 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 7.38 cm | y ≤ h/2 = 25.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


#### Detalle: Centro — fibra inferior (Mu de diseño = 10.00 t·m)

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Centro | Fibra diseñada | inferior |
| Mu (t·m) | 10.000 | d (cm) | 42.53 |
| As mínimo (cm²) | 2.568 | As máximo (cm²) | 14.403 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 19.463 |
| As calculado (cm²) | 6.720 | As requerido (cm²) | 6.720 |
| As colocado (cm²) | 7.620 | Varillas | 6 Φ 1/2" |
| ¿Doble refuerzo? | No | As' requerido (cm²) | — |
| As' colocado (cm²) | — | Varillas de compresión | — |
| a (cm) | 7.172 | c (cm) | 8.437 |
| εt | 0.01212 | φ | 0.900 |
| Mn (t·m) | 12.463 | φMn (t·m) | 11.217 |
| As colocado / requerido | 1.13 | Estado | CUMPLE |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 210 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(210/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02125
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√210/4200 · 25.0 · 42.53 = 2.568 cm²
→ As,min = 2.568 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(16.945; 14.403; 26.580) = 14.403 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 13.556 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 19.463 t·m
```

**E.060 10.3.1**
```text
Ecuación de flexión simple
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
10.000·10⁵ = 0.90·As·4200·(42.53 − As·4200/(2·0.85·210·25.0))
→ As = 6.720 cm²  (discriminante = 2.312e+10)
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 7.620·4200/(0.85·210·25.0) = 7.172 cm; c = 8.437 cm
→ a = 7.172 cm; c = 8.437 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(42.53 − 8.437)/8.437 = 0.01212
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 7.620·4200·(42.53 − 7.172/2)/10⁵
→ Mn = 12.463 t·m; φMn = 11.217 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
6 Φ 1/2" → As,prov = 7.620 cm² ≥ 6.720 cm²
→ 6 Φ 1/2"  (d = 42.53 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 7.620 cm² | As,min = 2.568 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.00717 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Límite de armadura simple (ductilidad) | As = 7.620 cm² | As,max = 14.403 cm² | CUMPLE | E.060 10.3.5 / 9.3.2.1 | El límite asegura εt ≥ 0.005 y φ = 0.90. |
| Control de ductilidad | εt = 0.01212 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.01212) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 11.217 t·m | Mu = 10.000 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 5.64 cm | s ≥ máx(Ø; 2.5 cm) = 2.50 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 6 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 7.47 cm | y ≤ h/2 = 25.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


#### Detalle: Apoyo izquierdo (cara) — fibra inferior (Mu de diseño = 7.32 t·m) — ampliada por Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4); demanda ETABS = 0.00 t·m

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Apoyo izquierdo (cara) | Fibra diseñada | inferior |
| Mu (t·m) | 7.316 | d (cm) | 44.41 |
| As mínimo (cm²) | 2.682 | As máximo (cm²) | 15.041 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 21.227 |
| As calculado (cm²) | 4.580 | As requerido (cm²) | 4.580 |
| As colocado (cm²) | 5.080 | Varillas | 4 Φ 1/2" |
| ¿Doble refuerzo? | No | As' requerido (cm²) | — |
| As' colocado (cm²) | — | Varillas de compresión | — |
| a (cm) | 4.781 | c (cm) | 5.625 |
| εt | 0.02069 | φ | 0.900 |
| Mn (t·m) | 8.966 | φMn (t·m) | 8.069 |
| As colocado / requerido | 1.11 | Estado | CUMPLE |
| Motivo de ampliación | Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4) | Demanda ETABS (t·m) | 0.000 |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 210 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(210/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02125
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√210/4200 · 25.0 · 44.41 = 2.682 cm²
→ As,min = 2.682 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(17.696; 15.041; 27.758) = 15.041 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 14.156 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 21.227 t·m
```

**E.060 10.3.1**
```text
Ecuación de flexión simple
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
7.316·10⁵ = 0.90·As·4200·(44.41 − As·4200/(2·0.85·210·25.0))
→ As = 4.580 cm²  (discriminante = 2.837e+10)
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 5.080·4200/(0.85·210·25.0) = 4.781 cm; c = 5.625 cm
→ a = 4.781 cm; c = 5.625 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(44.41 − 5.625)/5.625 = 0.02069
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 5.080·4200·(44.41 − 4.781/2)/10⁵
→ Mn = 8.966 t·m; φMn = 8.069 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
4 Φ 1/2" → As,prov = 5.080 cm² ≥ 4.580 cm²
→ 4 Φ 1/2"  (d = 44.41 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 5.080 cm² | As,min = 2.682 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.00458 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Límite de armadura simple (ductilidad) | As = 5.080 cm² | As,max = 15.041 cm² | CUMPLE | E.060 10.3.5 / 9.3.2.1 | El límite asegura εt ≥ 0.005 y φ = 0.90. |
| Control de ductilidad | εt = 0.02069 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.02069) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 8.069 t·m | Mu = 7.316 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 3.34 cm | s ≥ máx(Ø; 2.5 cm) = 2.50 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 4 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 5.59 cm | y ≤ h/2 = 25.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


#### Detalle: Apoyo derecho (cara) — fibra inferior (Mu de diseño = 7.32 t·m) — ampliada por Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4); demanda ETABS = 0.00 t·m

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Apoyo derecho (cara) | Fibra diseñada | inferior |
| Mu (t·m) | 7.316 | d (cm) | 44.41 |
| As mínimo (cm²) | 2.682 | As máximo (cm²) | 15.041 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 21.227 |
| As calculado (cm²) | 4.580 | As requerido (cm²) | 4.580 |
| As colocado (cm²) | 5.080 | Varillas | 4 Φ 1/2" |
| ¿Doble refuerzo? | No | As' requerido (cm²) | — |
| As' colocado (cm²) | — | Varillas de compresión | — |
| a (cm) | 4.781 | c (cm) | 5.625 |
| εt | 0.02069 | φ | 0.900 |
| Mn (t·m) | 8.966 | φMn (t·m) | 8.069 |
| As colocado / requerido | 1.11 | Estado | CUMPLE |
| Motivo de ampliación | Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4) | Demanda ETABS (t·m) | 0.000 |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 210 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(210/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02125
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√210/4200 · 25.0 · 44.41 = 2.682 cm²
→ As,min = 2.682 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(17.696; 15.041; 27.758) = 15.041 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 14.156 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 21.227 t·m
```

**E.060 10.3.1**
```text
Ecuación de flexión simple
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
7.316·10⁵ = 0.90·As·4200·(44.41 − As·4200/(2·0.85·210·25.0))
→ As = 4.580 cm²  (discriminante = 2.837e+10)
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 5.080·4200/(0.85·210·25.0) = 4.781 cm; c = 5.625 cm
→ a = 4.781 cm; c = 5.625 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(44.41 − 5.625)/5.625 = 0.02069
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 5.080·4200·(44.41 − 4.781/2)/10⁵
→ Mn = 8.966 t·m; φMn = 8.069 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
4 Φ 1/2" → As,prov = 5.080 cm² ≥ 4.580 cm²
→ 4 Φ 1/2"  (d = 44.41 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 5.080 cm² | As,min = 2.682 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.00458 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Límite de armadura simple (ductilidad) | As = 5.080 cm² | As,max = 15.041 cm² | CUMPLE | E.060 10.3.5 / 9.3.2.1 | El límite asegura εt ≥ 0.005 y φ = 0.90. |
| Control de ductilidad | εt = 0.02069 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.02069) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 8.069 t·m | Mu = 7.316 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 3.34 cm | s ≥ máx(Ø; 2.5 cm) = 2.50 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 4 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 5.59 cm | y ≤ h/2 = 25.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


### Resumen de acero teórico vs. acero colocado

| Sección | Fibra | Mu (t·m) | As teórico (cm²) | As colocado (cm²) | Varillas comerciales | φMn (t·m) | Doble |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Apoyo izquierdo (cara) | superior | 13.06 | 9.00 | 9.90 | 5 Φ 5/8" | 14.21 | No |
| Apoyo izquierdo (cara) | inferior | 7.32 | 4.58 | 5.08 | 4 Φ 1/2" | 8.07 | No |
| Centro | inferior | 10.00 | 6.72 | 7.62 | 6 Φ 1/2" | 11.22 | No |
| Centro | superior | 0.00 | 2.68 | 3.81 | 3 Φ 1/2" | 6.14 | No |
| Apoyo derecho (cara) | superior | 13.96 | 9.71 | 9.90 | 5 Φ 5/8" | 14.21 | No |
| Apoyo derecho (cara) | inferior | 7.32 | 4.58 | 5.08 | 4 Φ 1/2" | 8.07 | No |


### Armado longitudinal propuesto

| Zona | Armadura superior | Armadura inferior | Mu− (t·m) | Mu+ (t·m) |
| --- | --- | --- | --- | --- |
| Apoyo izquierdo (cara) | 5 Φ 5/8" | 4 Φ 1/2" | 13.06 | 7.32 |
| Centro | 3 Φ 1/2" | 6 Φ 1/2" | 0.00 | 10.00 |
| Apoyo derecho (cara) | 5 Φ 5/8" | 4 Φ 1/2" | 13.96 | 7.32 |

> **Nota:** Se disponen como mínimo dos barras continuas superior e inferior en toda la longitud de la viga (E.060 21.5.2.1). El armado de la memoria es una propuesta de diseño; el despiece final debe compatibilizarse con longitudes de desarrollo, traslapes y detalles del proyecto.


### Diseño por cortante

El cortante de diseño se determinó por capacidad, sumando el cortante asociado a las resistencias probables en flexión Mpr = 1.25·Mn en los extremos y el cortante gravitacional (E.060 21.5.4.1). Se comparó con la envolvente de ETABS y se adoptó el mayor. En la zona de confinamiento se aplicó la reducción de Vc a cero cuando el sismo aporta al menos la mitad del cortante y la carga axial es baja (E.060 21.5.4.2).

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| d de cortante (cm) | 42.53 | ln (m) | 5.400 |
| Mpr,i (t·m) | 20.06 | Mpr,j (t·m) | 20.06 |
| Ve = ΣMpr/ln (t) | 5.81 | Vg caras i/j (t) | 12.60 / 12.60 |
| Vu,i (t) | 18.41 | Vu,j (t) | 18.41 |
| Vu de diseño (t) | 18.41 | V envolvente ETABS (t) | 20.00 |
| Vc (t) | 8.17 | Vc zona confinada (t) | 8.17 |
| φ cortante | 0.85 | Vs req izquierdo (t) | 13.50 |
| Vs req derecho (t) | 13.50 | s req izquierdo (cm) | 18.79 |
| s req derecho (cm) | 18.79 | s conf. izquierdo (cm) | 10.00 |
| s conf. derecho (cm) | 10.00 | s central (cm) | 21.00 |
| s máx. confinamiento (cm) | 10.16 | s máx. central (cm) | 21.26 |
| Av (cm²) | 1.42 | Ramas por estribo | 2 |
| Estribo | Φ 3/8" | L zona confinada (m) | 1.00 |

Fórmulas aplicadas:

**E.060 21.5.4.1**
```text
Resistencia probable a flexión en los extremos
Mpr = 1.25·Mn (con el acero realmente colocado)
Mpr−,izq = 1.25·16.045 = 20.056; Mpr+,izq = 1.25·9.062 = 11.328; Mpr−,der = 1.25·16.045 = 20.056; Mpr+,der = 1.25·9.062 = 11.328 t·m
→ ΣMpr gobierna = 31.384 t·m
```

**E.060 21.5.4.1**
```text
Cortante por capacidad
Ve = (Mpr,i + Mpr,j)/ln
Ve = máx[(20.056+11.328)/5.40; (11.328+20.056)/5.40]
→ Ve = 5.812 t
```

**E.060 21.5.4.1**
```text
Cortante de diseño
Vu = máx(Ve + Vg; V_ETABS)
Vu,izq = máx(18.412; 18.000) = 18.412 t; Vu,der = máx(18.412; 18.000) = 18.412 t; Vu,centro = máx(5.812; 0.000) = 5.812 t
→ Vu,gobierna = 18.412 t
```

**E.060 11.3.1.1**
```text
Resistencia del concreto
Vc = 0.53·√(f'c)·b·d
Vc = 0.53·√210·25.0·42.53/1000
→ Vc = 8.166 t
```

**E.060 11.5.7.2**
```text
Cortante del refuerzo requerido
Vs,req = Vu/φ − Vc
Vs,req,izq = 18.412/0.85 − 8.166 = 13.495 t; Vs,req,der = 13.495 t
→ Vs,req = 13.495 t
```

**E.060 11.5.7.2**
```text
Espaciamiento requerido
s = Av·fy·d/Vs
s = 1.42·4200·42.53/13495.3
→ s,req = 18.79 cm
```

**E.060 21.5.3.4 / 21.5.3.5**
```text
Límites de espaciamiento
sconf ≤ mín(d/4; 8db,long; 24db,est; 30 cm); scentral ≤ d/2
sconf ≤ mín(10.63; 10.16; 22.86; 30) = 10.16 cm; scentral ≤ 21.26 cm
→ sconf = 10.00/10.00 cm; scentral = 21.00 cm
```

**E.060 11.5.6.3**
```text
Cuantía mínima de estribos
Av,min/s = máx(0.20√(f'c)·b/fy; 3.5·b/fy)
Av,min/s = máx(0.20·√210·25.0/4200; 3.5·25.0/4200) = 0.0208 cm²/cm
→ Av/s provisto = 0.1420 cm²/cm
```


#### Detalle de estribado

| Tramo | Distribución | Separación (m) |
| --- | --- | --- |
| Apoyo izquierdo (zona de confinamiento, 2h) | 1 @ 0.05, 9 @ 0.10 m | 0.10 |
| Tramo central | 17 @ 0.21 m | 0.21 |
| Apoyo derecho (zona de confinamiento, 2h) | 9 @ 0.10, 1 @ 0.05 m | 0.10 |
| Total de estribos | 37 piezas | — |
| Peso aproximado de estribos | 27.48 kg | — |

**Detalle de estribado**
```text
Distribución: 1 @ 0.05, 9 @ 0.10 m | Resto: 17 @ 0.21 m | 9 @ 0.10, 1 @ 0.05 m
Estribo: Φ 3/8" de 2 ramas, Av = 1.42 cm²
Ganchos sísmicos a 135° con extensión ≥ 8db y ≥ 75 mm (E.060 7.1.3.c).
```

Verificaciones de cortante:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Cortante resistente en apoyo izquierdo | φVn = 28.500 t | Vu = 18.412 t | CUMPLE | E.060 11.5.7.2 / 21.5.4.1 |  |
| Cortante resistente en apoyo derecho | φVn = 28.500 t | Vu = 18.412 t | CUMPLE | E.060 11.5.7.2 / 21.5.4.1 |  |
| Cortante resistente en el centro | φVn = 17.207 t | Vu = 5.812 t | CUMPLE | E.060 11.5.7.2 / 21.5.4.1 |  |
| Máximo cortante del refuerzo | Vs,req = 13.495 t | Vs,max = 32.355 t | CUMPLE | E.060 11.5.6.9 | El límite se aplica al cortante usado en el diseño (Vs,req), no a la capacidad nominal de un estribado más cerrado que el requerido. |
| Espaciamiento en confinamiento | s = 10.00 cm | s,max = 10.16 cm | CUMPLE | E.060 21.5.3.4 |  |
| Espaciamiento central | s = 21.00 cm | s,max = 21.26 cm | CUMPLE | E.060 21.5.3.5 / 11.5.5.1 |  |
| Cuantía mínima de estribos (confinamiento) | Av/s = 0.1420 cm²/cm | Av,min/s = 0.0208 cm²/cm | CUMPLE | E.060 11.5.6.3 |  |
| Cuantía mínima de estribos (tramo central) | Av/s = 0.0676 cm²/cm | Av,min/s = 0.0208 cm²/cm | CUMPLE | E.060 11.5.6.3 |  |
| Separación entre ramas | 15.1/(2 − 1) = 15.10 cm | ≤ 30 cm | CUMPLE | E.060 21.5.3.6 |  |
| Primer estribo | 0.05 m desde la cara del apoyo | ≤ 0.05 m | CUMPLE | E.060 21.5.3.3 |  |
| Diámetro mínimo del estribo | Φ 3/8" | ≥ 3/8" | CUMPLE | E.060 21.5.3.2 |  |


### Verificaciones globales de la viga

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Luz libre mínima | ln = 540.0 cm | ln ≥ 4h = 200.0 cm | CUMPLE | E.060 21.5.1.1 |  |
| Ancho mínimo relativo | b = 25.0 cm | b ≥ 0.25h = 12.5 cm | CUMPLE | E.060 21.5.1.3 |  |
| Ancho mínimo absoluto | b = 25.0 cm | b ≥ 25.0 cm | CUMPLE | E.060 21.5.1.3 |  |
| Relación de momentos en apoyo izquierdo | Mn+ = 8.97 t·m | Mn+ ≥ Mn−/2 = 7.89 t·m | CUMPLE | E.060 21.5.2.3 |  |
| Relación de momentos en apoyo derecho | Mn+ = 8.97 t·m | Mn+ ≥ Mn−/2 = 7.89 t·m | CUMPLE | E.060 21.5.2.3 |  |
| Momento mínimo a lo largo de la viga | Mn,mín = 6.82 t·m | Mn ≥ Mn,max/4 = 3.95 t·m | CUMPLE | E.060 21.5.2.4 |  |
| Refuerzo continuo mínimo | superior: 3 barras; inferior: 4 barras | ≥ 2 barras en cada cara | CUMPLE | E.060 21.5.2.1 |  |


#### Observaciones

- Algunas secciones se diseñaron con un momento mayor que el de la envolvente para cumplir los mínimos de continuidad del capítulo 21.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 6.82 a 8.97 t·m.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 6.82 a 8.97 t·m.


---


## 4.2 Viga V-201 — Piso 3

Elemento V-201 de sección VP-30x60, ubicado en Piso 3 (Eje B-B / C). Diseño según E.060 para f'c = 280 kgf/cm² y fy = 4200 kgf/cm².


### Identificación del elemento

| Identificación | Valor | Identificación | Valor |
| --- | --- | --- | --- |
| ID de la viga | V-201 | Nombre ETABS | V-201 |
| Piso (Story) | Piso 3 | Eje / ubicación | Eje B-B / C |
| Sección | VP-30x60 | Material | Concreto f'c = 280 kgf/cm² |
| Nudo I | V-201-I | Nudo J | V-201-J |
| Coordenada I (m) | (0.00; 0.00; 3.00) | Coordenada J (m) | (7.50; 0.00; 3.00) |
| L entre ejes (m) | 7.500 | Luz libre ln (m) | 6.900 |
| Apoyos detectados | COL-1 / COL-2 | Recubrimiento libre r (cm) | 4.00 |


### Propiedades de materiales y geometría

| Parámetro | Símbolo | Valor | Unidad | Referencia |
| --- | --- | --- | --- | --- |
| Resistencia del concreto | f'c | 280.0 | kgf/cm² | E.060 4.2 / 5 |
| Fluencia del acero longitudinal | fy | 4200 | kgf/cm² | E.060 4.3 |
| Fluencia del acero transversal | fyt | 4200 | kgf/cm² | E.060 4.3 |
| Módulo de elasticidad del acero | Es | 2000000 | kgf/cm² | E.060 10.2.4 |
| Factor del bloque rectangular | β1 | 0.850 | — | E.060 10.2.7.3 |
| Cuantía balanceada | ρb | 0.02833 | — | E.060 10.3.2 |
| Ancho | b | 30.0 | cm | — |
| Peralte total | h | 60.0 | cm | — |
| Peralte efectivo estimado | d | 54.09 | cm | E.060 10.2.2 |
| Recubrimiento libre al estribo | r | 4.00 | cm | E.060 7.6.1 |
| Diámetro de estribo | Øe | 0.953 | cm | E.060 21.5.3.2 |
| Área bruta | Ag | 1800.0 | cm² | — |
| Longitud entre ejes | L | 7.500 | m | — |
| Luz libre | ln | 6.900 | m | E.060 21.5.1.1 |

> **Nota:** ETABS reporta un recubrimiento al centroide de la armadura de 6.00 cm. El valor de r usado en el diseño es el recubrimiento libre al estribo (4.00 cm).


### Resumen de cargas y momentos críticos de ETABS

| Estación | x (m) | M3 máx (t·m) | M3 mín (t·m) | \|V2\| máx (t) | P mín / máx (t) | \|T\| máx (t·m) | Combo M3 mín |
| --- | --- | --- | --- | --- | --- | --- | --- |
| I-End | 0.000 | -9.00 | -35.00 | 28.00 | -4.00 / -2.00 | 0.00 | E060-1.25(D+L)+1.25SISMOX |
| Cara-I | 0.300 | -6.73 | -26.99 | 25.76 | -4.00 / -2.00 | 0.00 | E060-1.25(D+L)+1.25SISMOX |
| Centro | 3.750 | 22.00 | 7.00 | 0.00 | -4.00 / -2.00 | 0.00 | E060-0.9D-1.25SISMOX |
| Cara-J | 7.200 | -7.65 | -27.91 | 25.76 | -4.00 / -2.00 | 0.00 | E060-1.25(D+L)+1.25SISMOX |
| J-End | 7.500 | -10.00 | -36.00 | 28.00 | -4.00 / -2.00 | 0.00 | E060-1.25(D+L)+1.25SISMOX |

| Máximo global | Valor | Estación (m) | Combinación |
| --- | --- | --- | --- |
| Momento positivo M+ | 22.00 t·m | 3.750 | E060-1.25(D+L)+1.25SISMOX |
| Momento negativo M− | 36.00 t·m | 7.500 | E060-1.25(D+L)+1.25SISMOX |
| Cortante \|V2\| | 28.00 t | 0.000 | E060-1.25(D+L)+1.25SISMOX |
| Torsión \|T\| | 0.00 t·m | — | — |
| Compresión máxima P | 4.00 t | — | — |
| Cortante gravitacional en caras | 18.40 / 18.40 t | — | E060-1.4D+1.7L |

> **Nota:** Convención: M3 positivo produce tracción en la fibra inferior (momento positivo o sagging); M3 negativo produce tracción en la fibra superior (momento negativo o hogging). V2 y P se presentan en valor absoluto y con signo según ETABS, respectivamente. Verifique los ejes locales del elemento si el modelo tiene rotaciones distintas de la vertical.


### Diseño por flexión

Se diseñaron las secciones críticas de apoyo y centro, además de las estaciones donde la envolvente global alcanza sus máximos dentro de la luz libre (los valores en el eje de la columna no son secciones de diseño). El acero mínimo se verificó en todas las secciones (E.060 10.5.1) y la cuantía máxima se limitó a 0.025 (E.060 21.5.2.2). El factor φ se recalcula a partir de la deformación εt (E.060 9.3.2). Las secciones marcadas con (*) se ampliaron para cumplir los mínimos de continuidad Mn+ ≥ Mn−/2 y Mn ≥ Mn,max/4 (E.060 21.5.2.3 y 21.5.2.4).

| Sección | Fibra | Mu (t·m) | As req (cm²) | As prov (cm²) | Varillas | Doble | φMn (t·m) | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Apoyo izquierdo (cara) | superior | 26.99 | 14.41 | 15.21 | 3 Φ 1" | No | 28.35 | CUMPLE |
| Apoyo izquierdo (cara) (*) | inferior | 14.60 | 7.42 | 7.92 | 4 Φ 5/8" | No | 15.54 | CUMPLE |
| Centro | inferior | 22.00 | 11.87 | 12.70 | 10 Φ 1/2" | No | 23.42 | CUMPLE |
| Centro | superior | 0.00 | 4.55 | 5.08 | 4 Φ 1/2" | No | 10.16 | CUMPLE |
| Apoyo derecho (cara) | superior | 27.91 | 14.95 | 15.21 | 3 Φ 1" | No | 28.35 | CUMPLE |
| Apoyo derecho (cara) (*) | inferior | 14.60 | 7.42 | 7.92 | 4 Φ 5/8" | No | 15.54 | CUMPLE |


#### Detalle: Apoyo derecho (cara) — fibra superior (Mu de diseño = 27.91 t·m)

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Apoyo derecho (cara) | Fibra diseñada | superior |
| Mu (t·m) | 27.910 | d (cm) | 53.78 |
| As mínimo (cm²) | 4.499 | As máximo (cm²) | 29.141 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 49.796 |
| As calculado (cm²) | 14.953 | As requerido (cm²) | 14.953 |
| As colocado (cm²) | 15.210 | Varillas | 3 Φ 1" |
| ¿Doble refuerzo? | No | As' requerido (cm²) | — |
| As' colocado (cm²) | — | Varillas de compresión | — |
| a (cm) | 8.947 | c (cm) | 10.526 |
| εt | 0.01233 | φ | 0.900 |
| Mn (t·m) | 31.496 | φMn (t·m) | 28.347 |
| As colocado / requerido | 1.02 | Estado | CUMPLE |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 280 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(280/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02833
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√280/4200 · 30.0 · 53.78 = 4.499 cm²
→ As,min = 4.499 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(34.283; 29.141; 40.333) = 29.141 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 17.142 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 49.796 t·m
```

**E.060 10.2.2**
```text
Armadura superior
Mu− produce tracción en la cara superior; d se mide desde el borde superior.
d = h − r − Øe − Ø/2 = 60.0 − ... = 53.78 cm
→ d = 53.78 cm
```

**E.060 10.3.1**
```text
Ecuación de flexión simple
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
27.910·10⁵ = 0.90·As·4200·(53.78 − As·4200/(2·0.85·280·30.0))
→ As = 14.953 cm²  (discriminante = 3.569e+10)
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 15.210·4200/(0.85·280·30.0) = 8.947 cm; c = 10.526 cm
→ a = 8.947 cm; c = 10.526 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(53.78 − 10.526)/10.526 = 0.01233
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 15.210·4200·(53.78 − 8.947/2)/10⁵
→ Mn = 31.496 t·m; φMn = 28.347 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
3 Φ 1" → As,prov = 15.210 cm² ≥ 14.953 cm²
→ 3 Φ 1"  (d = 53.78 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 15.210 cm² | As,min = 4.499 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.00943 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Límite de armadura simple (ductilidad) | As = 15.210 cm² | As,max = 29.141 cm² | CUMPLE | E.060 10.3.5 / 9.3.2.1 | El límite asegura εt ≥ 0.005 y φ = 0.90. |
| Control de ductilidad | εt = 0.01233 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.01233) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 28.347 t·m | Mu = 27.910 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 6.24 cm | s ≥ máx(Ø; 2.5 cm) = 2.54 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 3 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 6.22 cm | y ≤ h/2 = 30.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


#### Detalle: Centro — fibra inferior (Mu de diseño = 22.00 t·m)

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Centro | Fibra diseñada | inferior |
| Mu (t·m) | 22.000 | d (cm) | 52.53 |
| As mínimo (cm²) | 4.395 | As máximo (cm²) | 28.463 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 47.508 |
| As calculado (cm²) | 11.869 | As requerido (cm²) | 11.869 |
| As colocado (cm²) | 12.700 | Varillas | 10 Φ 1/2" |
| ¿Doble refuerzo? | No | As' requerido (cm²) | — |
| As' colocado (cm²) | — | Varillas de compresión | — |
| a (cm) | 7.471 | c (cm) | 8.789 |
| εt | 0.01493 | φ | 0.900 |
| Mn (t·m) | 26.026 | φMn (t·m) | 23.423 |
| As colocado / requerido | 1.07 | Estado | CUMPLE |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 280 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(280/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02833
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√280/4200 · 30.0 · 52.53 = 4.395 cm²
→ As,min = 4.395 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(33.486; 28.463; 39.396) = 28.463 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 16.743 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 47.508 t·m
```

**E.060 10.3.1**
```text
Ecuación de flexión simple
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
22.000·10⁵ = 0.90·As·4200·(52.53 − As·4200/(2·0.85·280·30.0))
→ As = 11.869 cm²  (discriminante = 3.659e+10)
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 12.700·4200/(0.85·280·30.0) = 7.471 cm; c = 8.789 cm
→ a = 7.471 cm; c = 8.789 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(52.53 − 8.789)/8.789 = 0.01493
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 12.700·4200·(52.53 − 7.471/2)/10⁵
→ Mn = 26.026 t·m; φMn = 23.423 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
10 Φ 1/2" → As,prov = 12.700 cm² ≥ 11.869 cm²
→ 10 Φ 1/2"  (d = 52.53 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 12.700 cm² | As,min = 4.395 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.00806 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Límite de armadura simple (ductilidad) | As = 12.700 cm² | As,max = 28.463 cm² | CUMPLE | E.060 10.3.5 / 9.3.2.1 | El límite asegura εt ≥ 0.005 y φ = 0.90. |
| Control de ductilidad | εt = 0.01493 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.01493) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 23.423 t·m | Mu = 22.000 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 3.44 cm | s ≥ máx(Ø; 2.5 cm) = 2.50 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 10 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 7.47 cm | y ≤ h/2 = 30.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


#### Detalle: Apoyo izquierdo (cara) — fibra inferior (Mu de diseño = 14.60 t·m) — ampliada por Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4); demanda ETABS = 0.00 t·m

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Apoyo izquierdo (cara) | Fibra diseñada | inferior |
| Mu (t·m) | 14.599 | d (cm) | 54.25 |
| As mínimo (cm²) | 4.539 | As máximo (cm²) | 29.399 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 50.682 |
| As calculado (cm²) | 7.417 | As requerido (cm²) | 7.417 |
| As colocado (cm²) | 7.920 | Varillas | 4 Φ 5/8" |
| ¿Doble refuerzo? | No | As' requerido (cm²) | — |
| As' colocado (cm²) | — | Varillas de compresión | — |
| a (cm) | 4.659 | c (cm) | 5.481 |
| εt | 0.02670 | φ | 0.900 |
| Mn (t·m) | 17.272 | φMn (t·m) | 15.545 |
| As colocado / requerido | 1.07 | Estado | CUMPLE |
| Motivo de ampliación | Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4) | Demanda ETABS (t·m) | 0.000 |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 280 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(280/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02833
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√280/4200 · 30.0 · 54.25 = 4.539 cm²
→ As,min = 4.539 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(34.587; 29.399; 40.690) = 29.399 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 17.293 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 50.682 t·m
```

**E.060 10.3.1**
```text
Ecuación de flexión simple
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
14.599·10⁵ = 0.90·As·4200·(54.25 − As·4200/(2·0.85·280·30.0))
→ As = 7.417 cm²  (discriminante = 4.391e+10)
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 7.920·4200/(0.85·280·30.0) = 4.659 cm; c = 5.481 cm
→ a = 4.659 cm; c = 5.481 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(54.25 − 5.481)/5.481 = 0.02670
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 7.920·4200·(54.25 − 4.659/2)/10⁵
→ Mn = 17.272 t·m; φMn = 15.545 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
4 Φ 5/8" → As,prov = 7.920 cm² ≥ 7.417 cm²
→ 4 Φ 5/8"  (d = 54.25 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 7.920 cm² | As,min = 4.539 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.00487 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Límite de armadura simple (ductilidad) | As = 7.920 cm² | As,max = 29.399 cm² | CUMPLE | E.060 10.3.5 / 9.3.2.1 | El límite asegura εt ≥ 0.005 y φ = 0.90. |
| Control de ductilidad | εt = 0.02670 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.02670) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 15.545 t·m | Mu = 14.599 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 4.58 cm | s ≥ máx(Ø; 2.5 cm) = 2.50 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 4 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 5.75 cm | y ≤ h/2 = 30.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


#### Detalle: Apoyo derecho (cara) — fibra inferior (Mu de diseño = 14.60 t·m) — ampliada por Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4); demanda ETABS = 0.00 t·m

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Apoyo derecho (cara) | Fibra diseñada | inferior |
| Mu (t·m) | 14.599 | d (cm) | 54.25 |
| As mínimo (cm²) | 4.539 | As máximo (cm²) | 29.399 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 50.682 |
| As calculado (cm²) | 7.417 | As requerido (cm²) | 7.417 |
| As colocado (cm²) | 7.920 | Varillas | 4 Φ 5/8" |
| ¿Doble refuerzo? | No | As' requerido (cm²) | — |
| As' colocado (cm²) | — | Varillas de compresión | — |
| a (cm) | 4.659 | c (cm) | 5.481 |
| εt | 0.02670 | φ | 0.900 |
| Mn (t·m) | 17.272 | φMn (t·m) | 15.545 |
| As colocado / requerido | 1.07 | Estado | CUMPLE |
| Motivo de ampliación | Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4) | Demanda ETABS (t·m) | 0.000 |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 280 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(280/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02833
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√280/4200 · 30.0 · 54.25 = 4.539 cm²
→ As,min = 4.539 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(34.587; 29.399; 40.690) = 29.399 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 17.293 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 50.682 t·m
```

**E.060 10.3.1**
```text
Ecuación de flexión simple
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
14.599·10⁵ = 0.90·As·4200·(54.25 − As·4200/(2·0.85·280·30.0))
→ As = 7.417 cm²  (discriminante = 4.391e+10)
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 7.920·4200/(0.85·280·30.0) = 4.659 cm; c = 5.481 cm
→ a = 4.659 cm; c = 5.481 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(54.25 − 5.481)/5.481 = 0.02670
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 7.920·4200·(54.25 − 4.659/2)/10⁵
→ Mn = 17.272 t·m; φMn = 15.545 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
4 Φ 5/8" → As,prov = 7.920 cm² ≥ 7.417 cm²
→ 4 Φ 5/8"  (d = 54.25 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 7.920 cm² | As,min = 4.539 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.00487 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Límite de armadura simple (ductilidad) | As = 7.920 cm² | As,max = 29.399 cm² | CUMPLE | E.060 10.3.5 / 9.3.2.1 | El límite asegura εt ≥ 0.005 y φ = 0.90. |
| Control de ductilidad | εt = 0.02670 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.02670) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 15.545 t·m | Mu = 14.599 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 4.58 cm | s ≥ máx(Ø; 2.5 cm) = 2.50 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 4 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 5.75 cm | y ≤ h/2 = 30.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


### Resumen de acero teórico vs. acero colocado

| Sección | Fibra | Mu (t·m) | As teórico (cm²) | As colocado (cm²) | Varillas comerciales | φMn (t·m) | Doble |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Apoyo izquierdo (cara) | superior | 26.99 | 14.41 | 15.21 | 3 Φ 1" | 28.35 | No |
| Apoyo izquierdo (cara) | inferior | 14.60 | 7.42 | 7.92 | 4 Φ 5/8" | 15.54 | No |
| Centro | inferior | 22.00 | 11.87 | 12.70 | 10 Φ 1/2" | 23.42 | No |
| Centro | superior | 0.00 | 4.55 | 5.08 | 4 Φ 1/2" | 10.16 | No |
| Apoyo derecho (cara) | superior | 27.91 | 14.95 | 15.21 | 3 Φ 1" | 28.35 | No |
| Apoyo derecho (cara) | inferior | 14.60 | 7.42 | 7.92 | 4 Φ 5/8" | 15.54 | No |


### Armado longitudinal propuesto

| Zona | Armadura superior | Armadura inferior | Mu− (t·m) | Mu+ (t·m) |
| --- | --- | --- | --- | --- |
| Apoyo izquierdo (cara) | 3 Φ 1" | 4 Φ 5/8" | 26.99 | 14.60 |
| Centro | 4 Φ 1/2" | 10 Φ 1/2" | 0.00 | 22.00 |
| Apoyo derecho (cara) | 3 Φ 1" | 4 Φ 5/8" | 27.91 | 14.60 |

> **Nota:** Se disponen como mínimo dos barras continuas superior e inferior en toda la longitud de la viga (E.060 21.5.2.1). El armado de la memoria es una propuesta de diseño; el despiece final debe compatibilizarse con longitudes de desarrollo, traslapes y detalles del proyecto.


### Diseño por cortante

El cortante de diseño se determinó por capacidad, sumando el cortante asociado a las resistencias probables en flexión Mpr = 1.25·Mn en los extremos y el cortante gravitacional (E.060 21.5.4.1). Se comparó con la envolvente de ETABS y se adoptó el mayor. En la zona de confinamiento se aplicó la reducción de Vc a cero cuando el sismo aporta al menos la mitad del cortante y la carga axial es baja (E.060 21.5.4.2).

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| d de cortante (cm) | 52.53 | ln (m) | 6.900 |
| Mpr,i (t·m) | 39.76 | Mpr,j (t·m) | 39.76 |
| Ve = ΣMpr/ln (t) | 8.90 | Vg caras i/j (t) | 18.40 / 18.40 |
| Vu,i (t) | 27.30 | Vu,j (t) | 27.30 |
| Vu de diseño (t) | 27.30 | V envolvente ETABS (t) | 28.00 |
| Vc (t) | 13.98 | Vc zona confinada (t) | 13.98 |
| φ cortante | 0.85 | Vs req izquierdo (t) | 18.14 |
| Vs req derecho (t) | 18.14 | s req izquierdo (cm) | 17.27 |
| s req derecho (cm) | 17.27 | s conf. izquierdo (cm) | 10.00 |
| s conf. derecho (cm) | 10.00 | s central (cm) | 26.00 |
| s máx. confinamiento (cm) | 10.16 | s máx. central (cm) | 26.26 |
| Av (cm²) | 1.42 | Ramas por estribo | 2 |
| Estribo | Φ 3/8" | L zona confinada (m) | 1.20 |

Fórmulas aplicadas:

**E.060 21.5.4.1**
```text
Resistencia probable a flexión en los extremos
Mpr = 1.25·Mn (con el acero realmente colocado)
Mpr−,izq = 1.25·31.809 = 39.762; Mpr+,izq = 1.25·17.315 = 21.644; Mpr−,der = 1.25·31.809 = 39.762; Mpr+,der = 1.25·17.315 = 21.644 t·m
→ ΣMpr gobierna = 61.406 t·m
```

**E.060 21.5.4.1**
```text
Cortante por capacidad
Ve = (Mpr,i + Mpr,j)/ln
Ve = máx[(39.762+21.644)/6.90; (21.644+39.762)/6.90]
→ Ve = 8.899 t
```

**E.060 21.5.4.1**
```text
Cortante de diseño
Vu = máx(Ve + Vg; V_ETABS)
Vu,izq = máx(27.299; 25.760) = 27.299 t; Vu,der = máx(27.299; 25.760) = 27.299 t; Vu,centro = máx(8.899; 0.000) = 8.899 t
→ Vu,gobierna = 27.299 t
```

**E.060 11.3.1.1**
```text
Resistencia del concreto
Vc = 0.53·√(f'c)·b·d
Vc = 0.53·√280·30.0·52.53/1000
→ Vc = 13.975 t
```

**E.060 11.5.7.2**
```text
Cortante del refuerzo requerido
Vs,req = Vu/φ − Vc
Vs,req,izq = 27.299/0.85 − 13.975 = 18.142 t; Vs,req,der = 18.142 t
→ Vs,req = 18.142 t
```

**E.060 11.5.7.2**
```text
Espaciamiento requerido
s = Av·fy·d/Vs
s = 1.42·4200·52.53/18141.6
→ s,req = 17.27 cm
```

**E.060 21.5.3.4 / 21.5.3.5**
```text
Límites de espaciamiento
sconf ≤ mín(d/4; 8db,long; 24db,est; 30 cm); scentral ≤ d/2
sconf ≤ mín(13.13; 10.16; 22.86; 30) = 10.16 cm; scentral ≤ 26.26 cm
→ sconf = 10.00/10.00 cm; scentral = 26.00 cm
```

**E.060 11.5.6.3**
```text
Cuantía mínima de estribos
Av,min/s = máx(0.20√(f'c)·b/fy; 3.5·b/fy)
Av,min/s = máx(0.20·√280·30.0/4200; 3.5·30.0/4200) = 0.0250 cm²/cm
→ Av/s provisto = 0.1420 cm²/cm
```


#### Detalle de estribado

| Tramo | Distribución | Separación (m) |
| --- | --- | --- |
| Apoyo izquierdo (zona de confinamiento, 2h) | 1 @ 0.05, 11 @ 0.10 m | 0.10 |
| Tramo central | 18 @ 0.26 m | 0.26 |
| Apoyo derecho (zona de confinamiento, 2h) | 11 @ 0.10, 1 @ 0.05 m | 0.10 |
| Total de estribos | 42 piezas | — |
| Peso aproximado de estribos | 38.21 kg | — |

**Detalle de estribado**
```text
Distribución: 1 @ 0.05, 11 @ 0.10 m | Resto: 18 @ 0.26 m | 11 @ 0.10, 1 @ 0.05 m
Estribo: Φ 3/8" de 2 ramas, Av = 1.42 cm²
Ganchos sísmicos a 135° con extensión ≥ 8db y ≥ 75 mm (E.060 7.1.3.c).
```

Verificaciones de cortante:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Cortante resistente en apoyo izquierdo | φVn = 38.507 t | Vu = 27.299 t | CUMPLE | E.060 11.5.7.2 / 21.5.4.1 |  |
| Cortante resistente en apoyo derecho | φVn = 38.507 t | Vu = 27.299 t | CUMPLE | E.060 11.5.7.2 / 21.5.4.1 |  |
| Cortante resistente en el centro | φVn = 22.121 t | Vu = 8.899 t | CUMPLE | E.060 11.5.7.2 / 21.5.4.1 |  |
| Máximo cortante del refuerzo | Vs,req = 18.142 t | Vs,max = 55.374 t | CUMPLE | E.060 11.5.6.9 | El límite se aplica al cortante usado en el diseño (Vs,req), no a la capacidad nominal de un estribado más cerrado que el requerido. |
| Espaciamiento en confinamiento | s = 10.00 cm | s,max = 10.16 cm | CUMPLE | E.060 21.5.3.4 |  |
| Espaciamiento central | s = 26.00 cm | s,max = 26.26 cm | CUMPLE | E.060 21.5.3.5 / 11.5.5.1 |  |
| Cuantía mínima de estribos (confinamiento) | Av/s = 0.1420 cm²/cm | Av,min/s = 0.0250 cm²/cm | CUMPLE | E.060 11.5.6.3 |  |
| Cuantía mínima de estribos (tramo central) | Av/s = 0.0546 cm²/cm | Av,min/s = 0.0250 cm²/cm | CUMPLE | E.060 11.5.6.3 |  |
| Separación entre ramas | 20.1/(2 − 1) = 20.09 cm | ≤ 30 cm | CUMPLE | E.060 21.5.3.6 |  |
| Primer estribo | 0.05 m desde la cara del apoyo | ≤ 0.05 m | CUMPLE | E.060 21.5.3.3 |  |
| Diámetro mínimo del estribo | Φ 3/8" | ≥ 3/8" | CUMPLE | E.060 21.5.3.2 |  |


### Verificaciones globales de la viga

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Luz libre mínima | ln = 690.0 cm | ln ≥ 4h = 240.0 cm | CUMPLE | E.060 21.5.1.1 |  |
| Ancho mínimo relativo | b = 30.0 cm | b ≥ 0.25h = 15.0 cm | CUMPLE | E.060 21.5.1.3 |  |
| Ancho mínimo absoluto | b = 30.0 cm | b ≥ 25.0 cm | CUMPLE | E.060 21.5.1.3 |  |
| Relación de momentos en apoyo izquierdo | Mn+ = 17.27 t·m | Mn+ ≥ Mn−/2 = 15.75 t·m | CUMPLE | E.060 21.5.2.3 |  |
| Relación de momentos en apoyo derecho | Mn+ = 17.27 t·m | Mn+ ≥ Mn−/2 = 15.75 t·m | CUMPLE | E.060 21.5.2.3 |  |
| Momento mínimo a lo largo de la viga | Mn,mín = 11.29 t·m | Mn ≥ Mn,max/4 = 7.87 t·m | CUMPLE | E.060 21.5.2.4 |  |
| Refuerzo continuo mínimo | superior: 3 barras; inferior: 4 barras | ≥ 2 barras en cada cara | CUMPLE | E.060 21.5.2.1 |  |


#### Observaciones

- Algunas secciones se diseñaron con un momento mayor que el de la envolvente para cumplir los mínimos de continuidad del capítulo 21.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 11.29 a 17.27 t·m.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 11.29 a 17.27 t·m.


---


## 4.3 Viga V-301 — Piso 1

Elemento V-301 de sección VP-25x50, ubicado en Piso 1 (Eje C-C / D). Diseño según E.060 para f'c = 210 kgf/cm² y fy = 4200 kgf/cm².


### Identificación del elemento

| Identificación | Valor | Identificación | Valor |
| --- | --- | --- | --- |
| ID de la viga | V-301 | Nombre ETABS | V-301 |
| Piso (Story) | Piso 1 | Eje / ubicación | Eje C-C / D |
| Sección | VP-25x50 | Material | Concreto f'c = 210 kgf/cm² |
| Nudo I | V-301-I | Nudo J | V-301-J |
| Coordenada I (m) | (0.00; 0.00; 3.00) | Coordenada J (m) | (5.00; 0.00; 3.00) |
| L entre ejes (m) | 5.000 | Luz libre ln (m) | 4.400 |
| Apoyos detectados | COL-1 / COL-2 | Recubrimiento libre r (cm) | 4.00 |


### Propiedades de materiales y geometría

| Parámetro | Símbolo | Valor | Unidad | Referencia |
| --- | --- | --- | --- | --- |
| Resistencia del concreto | f'c | 210.0 | kgf/cm² | E.060 4.2 / 5 |
| Fluencia del acero longitudinal | fy | 4200 | kgf/cm² | E.060 4.3 |
| Fluencia del acero transversal | fyt | 4200 | kgf/cm² | E.060 4.3 |
| Módulo de elasticidad del acero | Es | 2000000 | kgf/cm² | E.060 10.2.4 |
| Factor del bloque rectangular | β1 | 0.850 | — | E.060 10.2.7.3 |
| Cuantía balanceada | ρb | 0.02125 | — | E.060 10.3.2 |
| Ancho | b | 25.0 | cm | — |
| Peralte total | h | 50.0 | cm | — |
| Peralte efectivo estimado | d | 44.09 | cm | E.060 10.2.2 |
| Recubrimiento libre al estribo | r | 4.00 | cm | E.060 7.6.1 |
| Diámetro de estribo | Øe | 0.953 | cm | E.060 21.5.3.2 |
| Área bruta | Ag | 1250.0 | cm² | — |
| Longitud entre ejes | L | 5.000 | m | — |
| Luz libre | ln | 4.400 | m | E.060 21.5.1.1 |

> **Nota:** ETABS reporta un recubrimiento al centroide de la armadura de 6.00 cm. El valor de r usado en el diseño es el recubrimiento libre al estribo (4.00 cm).


### Resumen de cargas y momentos críticos de ETABS

| Estación | x (m) | M3 máx (t·m) | M3 mín (t·m) | \|V2\| máx (t) | P mín / máx (t) | \|T\| máx (t·m) | Combo M3 mín |
| --- | --- | --- | --- | --- | --- | --- | --- |
| I-End | 0.000 | -7.00 | -30.00 | 30.00 | -3.00 / -1.00 | 0.00 | E060-1.25(D+L)+1.25SISMOX |
| Cara-I | 0.300 | -4.65 | -21.14 | 26.40 | -3.00 / -1.00 | 0.00 | E060-1.25(D+L)+1.25SISMOX |
| Centro | 2.500 | 12.00 | 4.00 | 0.00 | -3.00 / -1.00 | 0.00 | E060-0.9D-1.25SISMOX |
| Cara-J | 4.700 | -5.53 | -22.02 | 26.40 | -3.00 / -1.00 | 0.00 | E060-1.25(D+L)+1.25SISMOX |
| J-End | 5.000 | -8.00 | -31.00 | 30.00 | -3.00 / -1.00 | 0.00 | E060-1.25(D+L)+1.25SISMOX |

| Máximo global | Valor | Estación (m) | Combinación |
| --- | --- | --- | --- |
| Momento positivo M+ | 12.00 t·m | 2.500 | E060-1.25(D+L)+1.25SISMOX |
| Momento negativo M− | 31.00 t·m | 5.000 | E060-1.25(D+L)+1.25SISMOX |
| Cortante \|V2\| | 30.00 t | 0.000 | E060-1.25(D+L)+1.25SISMOX |
| Torsión \|T\| | 0.00 t·m | — | — |
| Compresión máxima P | 3.00 t | — | — |
| Cortante gravitacional en caras | 19.36 / 19.36 t | — | E060-1.4D+1.7L |

> **Nota:** Convención: M3 positivo produce tracción en la fibra inferior (momento positivo o sagging); M3 negativo produce tracción en la fibra superior (momento negativo o hogging). V2 y P se presentan en valor absoluto y con signo según ETABS, respectivamente. Verifique los ejes locales del elemento si el modelo tiene rotaciones distintas de la vertical.


### Diseño por flexión

Se diseñaron las secciones críticas de apoyo y centro, además de las estaciones donde la envolvente global alcanza sus máximos dentro de la luz libre (los valores en el eje de la columna no son secciones de diseño). El acero mínimo se verificó en todas las secciones (E.060 10.5.1) y la cuantía máxima se limitó a 0.025 (E.060 21.5.2.2). El factor φ se recalcula a partir de la deformación εt (E.060 9.3.2). Las secciones marcadas con (*) se ampliaron para cumplir los mínimos de continuidad Mn+ ≥ Mn−/2 y Mn ≥ Mn,max/4 (E.060 21.5.2.3 y 21.5.2.4).

| Sección | Fibra | Mu (t·m) | As req (cm²) | As prov (cm²) | Varillas | Doble | φMn (t·m) | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Apoyo izquierdo (cara) | superior | 21.14 | 15.08 | 15.21 | 3 Φ 1" | Sí | 21.70 | CUMPLE |
| Apoyo izquierdo (cara) (*) | inferior | 11.17 | 7.59 | 7.62 | 6 Φ 1/2" | No | 11.22 | CUMPLE |
| Centro | inferior | 12.00 | 7.82 | 7.92 | 4 Φ 5/8" | No | 12.13 | CUMPLE |
| Centro | superior | 0.00 | 2.68 | 3.81 | 3 Φ 1/2" | No | 6.14 | CUMPLE |
| Apoyo derecho (cara) | superior | 22.02 | 16.37 | 17.10 | 6 Φ 3/4" | Sí | 22.12 | CUMPLE |
| Apoyo derecho (cara) (*) | inferior | 11.70 | 7.61 | 7.92 | 4 Φ 5/8" | No | 12.13 | CUMPLE |


#### Detalle: Apoyo derecho (cara) — fibra superior (Mu de diseño = 22.02 t·m)

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Apoyo derecho (cara) | Fibra diseñada | superior |
| Mu (t·m) | 22.015 | d (cm) | 41.89 |
| As mínimo (cm²) | 2.530 | As máximo (cm²) | 14.188 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 18.886 |
| As calculado (cm²) | 16.366 | As requerido (cm²) | 16.366 |
| As colocado (cm²) | 17.100 | Varillas | 6 Φ 3/4" |
| ¿Doble refuerzo? | Sí | As' requerido (cm²) | 2.312 |
| As' colocado (cm²) | 2.540 | Varillas de compresión | 2 Φ 1/2" |
| a (cm) | 13.850 | c (cm) | 16.294 |
| εt | 0.00471 | φ | 0.876 |
| Mn (t·m) | 25.248 | φMn (t·m) | 22.119 |
| As colocado / requerido | 1.04 | Estado | CUMPLE |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 210 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(210/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02125
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√210/4200 · 25.0 · 41.89 = 2.530 cm²
→ As,min = 2.530 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(16.692; 14.188; 26.183) = 14.188 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 13.353 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 18.886 t·m
```

**E.060 10.2.2**
```text
Armadura superior
Mu− produce tracción en la cara superior; d se mide desde el borde superior.
d = h − r − Øe − Ø/2 = 50.0 − ... = 41.89 cm
→ d = 41.89 cm
```

**E.060 9.3.2.1 / 10.2.7**
```text
Profundidad del eje neutro para φ = 0.90
c = 0.375·d;  a = β1·c
c = 0.375·41.89 = 15.71 cm; a = 0.850·15.71 = 13.35 cm
→ c = 15.71 cm; a = 13.35 cm
```

**E.060 10.2.7**
```text
Fuerza y momento del bloque de concreto
Cc = 0.85·f'c·b·a;  M1 = Cc·(d − a/2)
Cc = 0.85·210·25.0·13.35 = 59588.8 kgf; M1 = 59588.8·(41.89 − 13.35/2)
→ M1 = 20.985 t·m
```

**E.060 10.3.4**
```text
Acero de compresión requerido
As' = [Mu/φ − Cc·(d − a/2)] / [f's·(d − d')]
As' = [22.015·10⁵/0.90 − 2098472] / [3745·(41.89 − 5.90)]
→ As' = 2.312 cm²; f's = 3744.7 kgf/cm²
```

**E.060 10.3.1**
```text
Acero de tracción requerido
As = (Cc + As'·f's)/fy
As = (59588.8 + 2.312·3745)/4200
→ As = 16.366 cm²
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 17.100·4200/(0.85·210·25.0) = 13.850 cm; c = 16.294 cm
→ a = 13.850 cm; c = 16.294 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(41.89 − 16.294)/16.294 = 0.00471
→ φ = 0.876
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 17.100·4200·(41.89 − 13.850/2)/10⁵
→ Mn = 25.248 t·m; φMn = 22.119 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
6 Φ 3/4" → As,prov = 17.100 cm² ≥ 16.366 cm²
→ 6 Φ 3/4"  (d = 41.89 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 17.100 cm² | As,min = 2.530 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.01633 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Armadura de compresión | As' = 2.540 cm² | As' > 0 y fluye o se evalúa f's | CUMPLE | E.060 10.3.4 / 21.5.2 | f's = 3942.5 kgf/cm² |
| Control de ductilidad | εt = 0.00471 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.876 (εt = 0.00471) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección en transición: φ se redujo según εt; la resistencia se verifica con φMn ≥ Mu. |
| Resistencia a flexión | φMn = 22.119 t·m | Mu = 22.015 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 4.69 cm | s ≥ máx(Ø; 2.5 cm) = 2.50 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 6 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 8.11 cm | y ≤ h/2 = 25.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


#### Detalle: Centro — fibra inferior (Mu de diseño = 12.00 t·m)

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Centro | Fibra diseñada | inferior |
| Mu (t·m) | 12.000 | d (cm) | 44.25 |
| As mínimo (cm²) | 2.672 | As máximo (cm²) | 14.988 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 21.075 |
| As calculado (cm²) | 7.825 | As requerido (cm²) | 7.825 |
| As colocado (cm²) | 7.920 | Varillas | 4 Φ 5/8" |
| ¿Doble refuerzo? | No | As' requerido (cm²) | — |
| As' colocado (cm²) | — | Varillas de compresión | — |
| a (cm) | 7.454 | c (cm) | 8.770 |
| εt | 0.01214 | φ | 0.900 |
| Mn (t·m) | 13.481 | φMn (t·m) | 12.133 |
| As colocado / requerido | 1.01 | Estado | CUMPLE |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 210 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(210/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02125
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√210/4200 · 25.0 · 44.25 = 2.672 cm²
→ As,min = 2.672 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(17.632; 14.988; 27.659) = 14.988 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 14.106 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 21.075 t·m
```

**E.060 10.3.1**
```text
Ecuación de flexión simple
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
12.000·10⁵ = 0.90·As·4200·(44.25 − As·4200/(2·0.85·210·25.0))
→ As = 7.825 cm²  (discriminante = 2.400e+10)
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 7.920·4200/(0.85·210·25.0) = 7.454 cm; c = 8.770 cm
→ a = 7.454 cm; c = 8.770 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(44.25 − 8.770)/8.770 = 0.01214
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 7.920·4200·(44.25 − 7.454/2)/10⁵
→ Mn = 13.481 t·m; φMn = 12.133 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
4 Φ 5/8" → As,prov = 7.920 cm² ≥ 7.825 cm²
→ 4 Φ 5/8"  (d = 44.25 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 7.920 cm² | As,min = 2.672 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.00716 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Límite de armadura simple (ductilidad) | As = 7.920 cm² | As,max = 14.988 cm² | CUMPLE | E.060 10.3.5 / 9.3.2.1 | El límite asegura εt ≥ 0.005 y φ = 0.90. |
| Control de ductilidad | εt = 0.01214 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.01214) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 12.133 t·m | Mu = 12.000 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 2.92 cm | s ≥ máx(Ø; 2.5 cm) = 2.50 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 4 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 5.75 cm | y ≤ h/2 = 25.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


#### Detalle: Apoyo izquierdo (cara) — fibra superior (Mu de diseño = 21.14 t·m)

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Apoyo izquierdo (cara) | Fibra diseñada | superior |
| Mu (t·m) | 21.135 | d (cm) | 43.78 |
| As mínimo (cm²) | 2.643 | As máximo (cm²) | 14.826 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 20.624 |
| As calculado (cm²) | 15.080 | As requerido (cm²) | 15.080 |
| As colocado (cm²) | 15.210 | Varillas | 3 Φ 1" |
| ¿Doble refuerzo? | Sí | As' requerido (cm²) | 0.159 |
| As' colocado (cm²) | 2.540 | Varillas de compresión | 2 Φ 1/2" |
| a (cm) | 12.227 | c (cm) | 14.384 |
| εt | 0.00613 | φ | 0.900 |
| Mn (t·m) | 24.110 | φMn (t·m) | 21.699 |
| As colocado / requerido | 1.01 | Estado | CUMPLE |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 210 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(210/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02125
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√210/4200 · 25.0 · 43.78 = 2.643 cm²
→ As,min = 2.643 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(17.443; 14.826; 27.361) = 14.826 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 13.954 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 20.624 t·m
```

**E.060 10.2.2**
```text
Armadura superior
Mu− produce tracción en la cara superior; d se mide desde el borde superior.
d = h − r − Øe − Ø/2 = 50.0 − ... = 43.78 cm
→ d = 43.78 cm
```

**E.060 9.3.2.1 / 10.2.7**
```text
Profundidad del eje neutro para φ = 0.90
c = 0.375·d;  a = β1·c
c = 0.375·43.78 = 16.42 cm; a = 0.850·16.42 = 13.95 cm
→ c = 16.42 cm; a = 13.95 cm
```

**E.060 10.2.7**
```text
Fuerza y momento del bloque de concreto
Cc = 0.85·f'c·b·a;  M1 = Cc·(d − a/2)
Cc = 0.85·210·25.0·13.95 = 62270.1 kgf; M1 = 62270.1·(43.78 − 13.95/2)
→ M1 = 22.916 t·m
```

**E.060 10.3.4**
```text
Acero de compresión requerido
As' = [Mu/φ − Cc·(d − a/2)] / [f's·(d − d')]
As' = [21.135·10⁵/0.90 − 2291567] / [3842·(43.78 − 5.90)]
→ As' = 0.159 cm²; f's = 3841.8 kgf/cm²
```

**E.060 10.3.1**
```text
Acero de tracción requerido
As = (Cc + As'·f's)/fy
As = (62270.1 + 0.159·3842)/4200
→ As = 15.080 cm²
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 15.210·4200/(0.85·210·25.0) = 12.227 cm; c = 14.384 cm
→ a = 12.227 cm; c = 14.384 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(43.78 − 14.384)/14.384 = 0.00613
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 15.210·4200·(43.78 − 12.227/2)/10⁵
→ Mn = 24.110 t·m; φMn = 21.699 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
3 Φ 1" → As,prov = 15.210 cm² ≥ 15.080 cm²
→ 3 Φ 1"  (d = 43.78 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 15.210 cm² | As,min = 2.643 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.01390 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Armadura de compresión | As' = 2.540 cm² | As' > 0 y fluye o se evalúa f's | CUMPLE | E.060 10.3.4 / 21.5.2 | f's = 3669.4 kgf/cm² |
| Control de ductilidad | εt = 0.00613 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.00613) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 21.699 t·m | Mu = 21.135 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 3.74 cm | s ≥ máx(Ø; 2.5 cm) = 2.54 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 3 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 6.22 cm | y ≤ h/2 = 25.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


#### Detalle: Apoyo izquierdo (cara) — fibra inferior (Mu de diseño = 11.17 t·m) — ampliada por Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4); demanda ETABS = 0.00 t·m

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Apoyo izquierdo (cara) | Fibra diseñada | inferior |
| Mu (t·m) | 11.175 | d (cm) | 42.53 |
| As mínimo (cm²) | 2.568 | As máximo (cm²) | 14.403 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 19.463 |
| As calculado (cm²) | 7.589 | As requerido (cm²) | 7.589 |
| As colocado (cm²) | 7.620 | Varillas | 6 Φ 1/2" |
| ¿Doble refuerzo? | No | As' requerido (cm²) | — |
| As' colocado (cm²) | — | Varillas de compresión | — |
| a (cm) | 7.172 | c (cm) | 8.437 |
| εt | 0.01212 | φ | 0.900 |
| Mn (t·m) | 12.463 | φMn (t·m) | 11.217 |
| As colocado / requerido | 1.00 | Estado | CUMPLE |
| Motivo de ampliación | Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4) | Demanda ETABS (t·m) | 0.000 |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 210 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(210/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02125
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√210/4200 · 25.0 · 42.53 = 2.568 cm²
→ As,min = 2.568 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(16.945; 14.403; 26.580) = 14.403 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 13.556 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 19.463 t·m
```

**E.060 10.3.1**
```text
Ecuación de flexión simple
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
11.175·10⁵ = 0.90·As·4200·(42.53 − As·4200/(2·0.85·210·25.0))
→ As = 7.589 cm²  (discriminante = 2.209e+10)
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 7.620·4200/(0.85·210·25.0) = 7.172 cm; c = 8.437 cm
→ a = 7.172 cm; c = 8.437 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(42.53 − 8.437)/8.437 = 0.01212
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 7.620·4200·(42.53 − 7.172/2)/10⁵
→ Mn = 12.463 t·m; φMn = 11.217 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
6 Φ 1/2" → As,prov = 7.620 cm² ≥ 7.589 cm²
→ 6 Φ 1/2"  (d = 42.53 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 7.620 cm² | As,min = 2.568 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.00717 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Límite de armadura simple (ductilidad) | As = 7.620 cm² | As,max = 14.403 cm² | CUMPLE | E.060 10.3.5 / 9.3.2.1 | El límite asegura εt ≥ 0.005 y φ = 0.90. |
| Control de ductilidad | εt = 0.01212 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.01212) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 11.217 t·m | Mu = 11.175 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 5.64 cm | s ≥ máx(Ø; 2.5 cm) = 2.50 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 6 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 7.47 cm | y ≤ h/2 = 25.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


#### Detalle: Apoyo derecho (cara) — fibra inferior (Mu de diseño = 11.70 t·m) — ampliada por Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4); demanda ETABS = 0.00 t·m

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| Ubicación | Apoyo derecho (cara) | Fibra diseñada | inferior |
| Mu (t·m) | 11.702 | d (cm) | 44.25 |
| As mínimo (cm²) | 2.672 | As máximo (cm²) | 14.988 |
| Criterio de As máximo | εt = 0.005 (φ = 0.90) | Mu máximo simple (t·m) | 21.075 |
| As calculado (cm²) | 7.612 | As requerido (cm²) | 7.612 |
| As colocado (cm²) | 7.920 | Varillas | 4 Φ 5/8" |
| ¿Doble refuerzo? | No | As' requerido (cm²) | — |
| As' colocado (cm²) | — | Varillas de compresión | — |
| a (cm) | 7.454 | c (cm) | 8.770 |
| εt | 0.01214 | φ | 0.900 |
| Mn (t·m) | 13.481 | φMn (t·m) | 12.133 |
| As colocado / requerido | 1.04 | Estado | CUMPLE |
| Motivo de ampliación | Mn+ ≥ Mn−/2 (E.060 21.5.2.3); Mn ≥ Mn,max/4 (E.060 21.5.2.4) | Demanda ETABS (t·m) | 0.000 |

**E.060 10.2.7.3**
```text
Factor β1 del bloque rectangular
β1 = 0.85
f'c = 210 kgf/cm² ≤ 280 → β1 = 0.85
→ β1 = 0.8500
```

**E.060 10.3.2**
```text
Cuantía balanceada
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
ρb = 0.85·0.8500·(210/4200)·[0.003/(0.003 + 4200/2000000)]
→ ρb = 0.02125
```

**E.060 10.5.1**
```text
Acero mínimo a flexión
As,min = 0.7·√(f'c)/fy · b·d
As,min = 0.7·√210/4200 · 25.0 · 44.25 = 2.672 cm²
→ As,min = 2.672 cm²
```

**E.060 21.5.2.2 / 9.3.2.1**
```text
Acero máximo y momento máximo con armadura simple
As,max = mín(fracción·ρb·b·d; 0.85·f'c·b·a(εt=0.005)/fy; 0.025·b·d)
As,max = mín(17.632; 14.988; 27.659) = 14.988 cm² (gobierna: εt = 0.005 (φ = 0.90))
→ a_max = 14.106 cm; Mu,max = φ·As,max·fy·(d − a_max/2)/10⁵ = 21.075 t·m
```

**E.060 10.3.1**
```text
Ecuación de flexión simple
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
11.702·10⁵ = 0.90·As·4200·(44.25 − As·4200/(2·0.85·210·25.0))
→ As = 7.612 cm²  (discriminante = 2.427e+10)
```

**E.060 10.2.7**
```text
Profundidad real del bloque y eje neutro
a = As·fy/(0.85·f'c·b);  c = a/β1
a = 7.920·4200/(0.85·210·25.0) = 7.454 cm; c = 8.770 cm
→ a = 7.454 cm; c = 8.770 cm
```

**E.060 9.3.2**
```text
Deformación y factor φ
εt = 0.003·(d − c)/c;  φ = f(εt)
εt = 0.003·(44.25 − 8.770)/8.770 = 0.01214
→ φ = 0.900
```

**E.060 10.3.1 / 9.3.2.1**
```text
Resistencia nominal y de diseño
Mn = As·fy·(d − a/2);  φMn = φ·Mn
Mn = 7.920·4200·(44.25 − 7.454/2)/10⁵
→ Mn = 13.481 t·m; φMn = 12.133 t·m
```

**E.060 7.6 / 21.5.2**
```text
Selección comercial
As,prov ≥ As,req
4 Φ 5/8" → As,prov = 7.920 cm² ≥ 7.612 cm²
→ 4 Φ 5/8"  (d = 44.25 cm)
```

Verificaciones de la sección:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Acero mínimo | As = 7.920 cm² | As,min = 2.672 cm² | CUMPLE | E.060 10.5.1 |  |
| Cuantía máxima sísmica | ρ = 0.00716 | ρ ≤ 0.025 | CUMPLE | E.060 21.5.2.2 |  |
| Límite de armadura simple (ductilidad) | As = 7.920 cm² | As,max = 14.988 cm² | CUMPLE | E.060 10.3.5 / 9.3.2.1 | El límite asegura εt ≥ 0.005 y φ = 0.90. |
| Control de ductilidad | εt = 0.01214 | εt ≥ 0.004 | CUMPLE | E.060 10.3.5 |  |
| Factor de reducción φ | φ = 0.900 (εt = 0.01214) | φ = 0.65 + 0.25·(εt − 0.002)/0.003 ≤ 0.90 | CUMPLE | E.060 9.3.2.2 | Sección controlada por tracción (φ = 0.90). |
| Resistencia a flexión | φMn = 12.133 t·m | Mu = 11.702 t·m | CUMPLE | E.060 9.3.2.1 |  |
| Separación libre entre barras | s = 2.92 cm | s ≥ máx(Ø; 2.5 cm) = 2.50 cm | CUMPLE | E.060 7.6.1 |  |
| Número mínimo de barras | 4 barras | ≥ 2 barras | CUMPLE | E.060 21.5.2.1 |  |
| Colocación en la sección | y = 5.75 cm | y ≤ h/2 = 25.00 cm | CUMPLE | E.060 7.6 / 7.7 |  |


### Resumen de acero teórico vs. acero colocado

| Sección | Fibra | Mu (t·m) | As teórico (cm²) | As colocado (cm²) | Varillas comerciales | φMn (t·m) | Doble |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Apoyo izquierdo (cara) | superior | 21.14 | 15.08 | 15.21 | 3 Φ 1" | 21.70 | Sí |
| Apoyo izquierdo (cara) | inferior | 11.17 | 7.59 | 7.62 | 6 Φ 1/2" | 11.22 | No |
| Centro | inferior | 12.00 | 7.82 | 7.92 | 4 Φ 5/8" | 12.13 | No |
| Centro | superior | 0.00 | 2.68 | 3.81 | 3 Φ 1/2" | 6.14 | No |
| Apoyo derecho (cara) | superior | 22.02 | 16.37 | 17.10 | 6 Φ 3/4" | 22.12 | Sí |
| Apoyo derecho (cara) | inferior | 11.70 | 7.61 | 7.92 | 4 Φ 5/8" | 12.13 | No |


### Armado longitudinal propuesto

| Zona | Armadura superior | Armadura inferior | Mu− (t·m) | Mu+ (t·m) |
| --- | --- | --- | --- | --- |
| Apoyo izquierdo (cara) | 3 Φ 1" | 6 Φ 1/2" | 21.14 | 11.17 |
| Centro | 3 Φ 1/2" | 4 Φ 5/8" | 0.00 | 12.00 |
| Apoyo derecho (cara) | 6 Φ 3/4" | 4 Φ 5/8" | 22.02 | 11.70 |

> **Nota:** Se disponen como mínimo dos barras continuas superior e inferior en toda la longitud de la viga (E.060 21.5.2.1). El armado de la memoria es una propuesta de diseño; el despiece final debe compatibilizarse con longitudes de desarrollo, traslapes y detalles del proyecto.


### Diseño por cortante

El cortante de diseño se determinó por capacidad, sumando el cortante asociado a las resistencias probables en flexión Mpr = 1.25·Mn en los extremos y el cortante gravitacional (E.060 21.5.4.1). Se comparó con la envolvente de ETABS y se adoptó el mayor. En la zona de confinamiento se aplicó la reducción de Vc a cero cuando el sismo aporta al menos la mitad del cortante y la carga axial es baja (E.060 21.5.4.2).

| Parámetro | Valor | Parámetro | Valor |
| --- | --- | --- | --- |
| d de cortante (cm) | 41.89 | ln (m) | 4.400 |
| Mpr,i (t·m) | 30.32 | Mpr,j (t·m) | 32.76 |
| Ve = ΣMpr/ln (t) | 10.99 | Vg caras i/j (t) | 19.36 / 19.36 |
| Vu,i (t) | 30.35 | Vu,j (t) | 30.35 |
| Vu de diseño (t) | 30.35 | V envolvente ETABS (t) | 30.00 |
| Vc (t) | 8.04 | Vc zona confinada (t) | 8.04 |
| φ cortante | 0.85 | Vs req izquierdo (t) | 27.66 |
| Vs req derecho (t) | 27.66 | s req izquierdo (cm) | 9.03 |
| s req derecho (cm) | 9.03 | s conf. izquierdo (cm) | 9.00 |
| s conf. derecho (cm) | 9.00 | s central (cm) | 20.00 |
| s máx. confinamiento (cm) | 10.16 | s máx. central (cm) | 20.95 |
| Av (cm²) | 1.42 | Ramas por estribo | 2 |
| Estribo | Φ 3/8" | L zona confinada (m) | 1.00 |

Fórmulas aplicadas:

**E.060 21.5.4.1**
```text
Resistencia probable a flexión en los extremos
Mpr = 1.25·Mn (con el acero realmente colocado)
Mpr−,izq = 1.25·24.253 = 30.316; Mpr+,izq = 1.25·12.477 = 15.596; Mpr−,der = 1.25·26.207 = 32.759; Mpr+,der = 1.25·13.464 = 16.830 t·m
→ ΣMpr gobierna = 48.355 t·m
```

**E.060 21.5.4.1**
```text
Cortante por capacidad
Ve = (Mpr,i + Mpr,j)/ln
Ve = máx[(30.316+16.830)/4.40; (15.596+32.759)/4.40]
→ Ve = 10.990 t
```

**E.060 21.5.4.1**
```text
Cortante de diseño
Vu = máx(Ve + Vg; V_ETABS)
Vu,izq = máx(30.350; 26.400) = 30.350 t; Vu,der = máx(30.350; 26.400) = 30.350 t; Vu,centro = máx(10.990; 0.000) = 10.990 t
→ Vu,gobierna = 30.350 t
```

**E.060 11.3.1.1**
```text
Resistencia del concreto
Vc = 0.53·√(f'c)·b·d
Vc = 0.53·√210·25.0·41.89/1000
→ Vc = 8.044 t
```

**E.060 11.5.7.2**
```text
Cortante del refuerzo requerido
Vs,req = Vu/φ − Vc
Vs,req,izq = 30.350/0.85 − 8.044 = 27.662 t; Vs,req,der = 27.662 t
→ Vs,req = 27.662 t
```

**E.060 11.5.7.2**
```text
Espaciamiento requerido
s = Av·fy·d/Vs
s = 1.42·4200·41.89/27661.8
→ s,req = 9.03 cm
```

**E.060 21.5.3.4 / 21.5.3.5**
```text
Límites de espaciamiento
sconf ≤ mín(d/4; 8db,long; 24db,est; 30 cm); scentral ≤ d/2
sconf ≤ mín(10.47; 10.16; 22.86; 30) = 10.16 cm; scentral ≤ 20.95 cm
→ sconf = 9.00/9.00 cm; scentral = 20.00 cm
```

**E.060 11.5.6.3**
```text
Cuantía mínima de estribos
Av,min/s = máx(0.20√(f'c)·b/fy; 3.5·b/fy)
Av,min/s = máx(0.20·√210·25.0/4200; 3.5·25.0/4200) = 0.0208 cm²/cm
→ Av/s provisto = 0.1578 cm²/cm
```


#### Detalle de estribado

| Tramo | Distribución | Separación (m) |
| --- | --- | --- |
| Apoyo izquierdo (zona de confinamiento, 2h) | 1 @ 0.05, 10 @ 0.09 m | 0.09 |
| Tramo central | 13 @ 0.20 m | 0.20 |
| Apoyo derecho (zona de confinamiento, 2h) | 10 @ 0.09, 1 @ 0.05 m | 0.09 |
| Total de estribos | 35 piezas | — |
| Peso aproximado de estribos | 25.99 kg | — |

**Detalle de estribado**
```text
Distribución: 1 @ 0.05, 10 @ 0.09 m | Resto: 13 @ 0.20 m | 10 @ 0.09, 1 @ 0.05 m
Estribo: Φ 3/8" de 2 ramas, Av = 1.42 cm²
Ganchos sísmicos a 135° con extensión ≥ 8db y ≥ 75 mm (E.060 7.1.3.c).
```

Verificaciones de cortante:

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Cortante resistente en apoyo izquierdo | φVn = 30.434 t | Vu = 30.350 t | CUMPLE | E.060 11.5.7.2 / 21.5.4.1 |  |
| Cortante resistente en apoyo derecho | φVn = 30.434 t | Vu = 30.350 t | CUMPLE | E.060 11.5.7.2 / 21.5.4.1 |  |
| Cortante resistente en el centro | φVn = 17.456 t | Vu = 10.990 t | CUMPLE | E.060 11.5.7.2 / 21.5.4.1 |  |
| Máximo cortante del refuerzo | Vs,req = 27.662 t | Vs,max = 31.872 t | CUMPLE | E.060 11.5.6.9 | El límite se aplica al cortante usado en el diseño (Vs,req), no a la capacidad nominal de un estribado más cerrado que el requerido. |
| Espaciamiento en confinamiento | s = 9.00 cm | s,max = 10.16 cm | CUMPLE | E.060 21.5.3.4 |  |
| Espaciamiento central | s = 20.00 cm | s,max = 20.95 cm | CUMPLE | E.060 21.5.3.5 / 11.5.5.1 |  |
| Cuantía mínima de estribos (confinamiento) | Av/s = 0.1578 cm²/cm | Av,min/s = 0.0208 cm²/cm | CUMPLE | E.060 11.5.6.3 |  |
| Cuantía mínima de estribos (tramo central) | Av/s = 0.0710 cm²/cm | Av,min/s = 0.0208 cm²/cm | CUMPLE | E.060 11.5.6.3 |  |
| Separación entre ramas | 15.1/(2 − 1) = 15.10 cm | ≤ 30 cm | CUMPLE | E.060 21.5.3.6 |  |
| Primer estribo | 0.05 m desde la cara del apoyo | ≤ 0.05 m | CUMPLE | E.060 21.5.3.3 |  |
| Diámetro mínimo del estribo | Φ 3/8" | ≥ 3/8" | CUMPLE | E.060 21.5.3.2 |  |


### Verificaciones globales de la viga

| Verificación | Valor | Límite / criterio | Estado | Referencia | Observación |
| --- | --- | --- | --- | --- | --- |
| Luz libre mínima | ln = 440.0 cm | ln ≥ 4h = 200.0 cm | CUMPLE | E.060 21.5.1.1 |  |
| Ancho mínimo relativo | b = 25.0 cm | b ≥ 0.25h = 12.5 cm | CUMPLE | E.060 21.5.1.3 |  |
| Ancho mínimo absoluto | b = 25.0 cm | b ≥ 25.0 cm | CUMPLE | E.060 21.5.1.3 |  |
| Relación de momentos en apoyo izquierdo | Mn+ = 12.46 t·m | Mn+ ≥ Mn−/2 = 12.05 t·m | CUMPLE | E.060 21.5.2.3 |  |
| Relación de momentos en apoyo derecho | Mn+ = 13.48 t·m | Mn+ ≥ Mn−/2 = 12.62 t·m | CUMPLE | E.060 21.5.2.3 |  |
| Momento mínimo a lo largo de la viga | Mn,mín = 6.82 t·m | Mn ≥ Mn,max/4 = 6.31 t·m | CUMPLE | E.060 21.5.2.4 |  |
| Refuerzo continuo mínimo | superior: 3 barras; inferior: 4 barras | ≥ 2 barras en cada cara | CUMPLE | E.060 21.5.2.1 |  |


#### Observaciones

- Algunas secciones se diseñaron con un momento mayor que el de la envolvente para cumplir los mínimos de continuidad del capítulo 21.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 6.82 a 12.46 t·m.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 6.82 a 13.48 t·m.


---


# 5. CONCLUSIONES Y RECOMENDACIONES

Todas las vigas procesadas cumplen las verificaciones de resistencia y detalle implementadas en esta memoria.

- Verificar en obra el recubrimiento, la posición de las barras y los ganchos sísmicos a 135°.
- Revisar las longitudes de desarrollo y los traslapes en la etapa de despiece; no forman parte del alcance de este cálculo.
- Si la torsión reportada por ETABS es significativa, realizar el diseño por torsión según E.060 11.6.
- Actualizar la memoria si cambian las combinaciones, el modelo ETABS o las propiedades de los materiales.


---


# ANEXO A. FORMULACIÓN Y REFERENCIAS


## A.1 Flexión

**E.060 10.2.7, 10.3, 10.5.1, 21.5.2.2, 9.3.2**
```text
β1 = 0.85                                          si f'c ≤ 280 kgf/cm²
β1 = 0.85 − 0.05(f'c − 280)/70                     si f'c > 280 kgf/cm²
ρb = 0.85·β1·(f'c/fy)·[0.003/(0.003 + fy/Es)]
As,min = 0.7·√(f'c)/fy · b·d
As,max = mín(0.75ρb·b·d; As(εt=0.005); 0.025·b·d)
Mu = φ·As·fy·(d − a/2),  a = As·fy/(0.85·f'c·b)
As' = [Mu/φ − Cc(d − a/2)]/[f's(d − d')],  Cc = 0.85·f'c·b·a
εt = 0.003(d − c)/c,  c = a/β1
```


## A.2 Cortante

**E.060 11.3.1.1, 11.5.5, 11.5.6, 11.5.7, 21.5.3, 21.5.4**
```text
Vc = 0.53·√(f'c)·b·d
Vs = Av·fy·d/s
Vu = φ(Vc + Vs)
s ≤ d/2 ≤ 60 cm
Av,min/s = máx(0.20√(f'c)·b/fy; 3.5·b/fy)
Vs ≤ 2.1·√(f'c)·b·d
Vu,capacidad = (Mpr,i + Mpr,j)/ln + Vg,  Mpr = 1.25·Mn
sconf ≤ mín(d/4; 8db,long; 24db,est; 30 cm);  scentral ≤ d/2
```


## A.3 Tabla de artículos aplicados

| Tema | Artículo E.060 | Aplicación en el programa |
| --- | --- | --- |
| Combinaciones de carga | 9.2.1, 9.2.3 | Generación y verificación de combos |
| Factor φ flexión | 9.3.2.1 / 9.3.2.2 | φ = 0.90 si εt ≥ 0.005; interpolación |
| Factor φ cortante | 9.3.2.3 | φ = 0.85 |
| Bloque rectangular | 10.2.7 | β1, a = As fy/(0.85 f'c b) |
| Cuantía balanceada | 10.3.2 | ρb y límite 0.75ρb |
| Ductilidad | 10.3.5 | εt ≥ 0.004 |
| Acero mínimo | 10.5.1 | As,min = 0.7√f'c b d/fy |
| Cortante del concreto | 11.3.1.1 | Vc = 0.53√f'c b d |
| Estribos mínimos | 11.5.6.3 | Av,min/s |
| Espaciamiento | 11.5.5.1 | s ≤ d/2 ≤ 60 cm |
| Vigas sísmicas: geometría | 21.5.1 | ln ≥ 4h; b ≥ 0.25h; b ≥ 25 cm |
| Refuerzo longitudinal | 21.5.2 | 2 barras continuas; ρ ≤ 0.025; Mn+/Mn− |
| Confinamiento | 21.5.3 | 2h; primer estribo 5 cm; sconf |
| Cortante por capacidad | 21.5.4 | Mpr = 1.25Mn; Vc = 0 |
| Recubrimiento | 7.6.1 | r = 4 cm (configurable) |
| Ganchos sísmicos | 7.1.3 | 135°, 8db ≥ 75 mm |


---


# ANEXO B. SUPUESTOS, ALCANCE Y TRAZABILIDAD


## B.1 Supuestos

- Secciones rectangulares de concreto armado, sin participación de losa.
- Flexión uniaxial alrededor del eje local 3 (M3) y cortante en V2.
- No se considera carga axial significativa en la viga; P se informa y se usa solo para la condición Vc = 0 de 21.5.4.2.
- El acero longitudinal fluye en tracción (fy = 4200 kgf/cm²).
- La armadura de compresión se evalúa con compatibilidad de deformaciones y puede no fluir; se reporta f's.
- El cortante por capacidad se calcula con Mpr = 1.25Mn de la armadura colocada, en ambas direcciones de sway.
- La luz libre se estima a partir de las columnas conectadas; si no se detectan, se usa la longitud entre ejes.


## B.2 Trazabilidad ETABS

| Dato | Valor |
| --- | --- |
| Versión ETABS | v23 (datos sintéticos) |
| Modelo | demo_vigas.edb |
| Ruta | — |
| API | ETABSv1 — comtypes/pywin32 |
| Unidades de trabajo | kgf_m (eUnits = 8) con conversión interna |
| Funciones usadas | GetAllFrames, GetRectangle, GetOConcrete, GetLabelFromName, FrameForce |


## B.3 Limitaciones y advertencias

Esta memoria no sustituye la revisión profesional ni el despiece. Los resultados deben contrastarse con el modelo ETABS, las cargas de proyecto y los requisitos particulares de la E.030 y del expediente técnico.


---


# ANEXO C. REGISTRO DE OBSERVACIONES


### Viga V-101

- Algunas secciones se diseñaron con un momento mayor que el de la envolvente para cumplir los mínimos de continuidad del capítulo 21.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 6.82 a 8.97 t·m.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 6.82 a 8.97 t·m.


### Viga V-201

- Algunas secciones se diseñaron con un momento mayor que el de la envolvente para cumplir los mínimos de continuidad del capítulo 21.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 11.29 a 17.27 t·m.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 11.29 a 17.27 t·m.


### Viga V-301

- Algunas secciones se diseñaron con un momento mayor que el de la envolvente para cumplir los mínimos de continuidad del capítulo 21.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 6.82 a 12.46 t·m.
- Se aumentó el acero para cumplir Mn+ ≥ Mn−/2 (E.060 21.5.2.3) y Mn ≥ Mn,max/4 (E.060 21.5.2.4): Mn pasó de 6.82 a 13.48 t·m.

Documento generado el 20/10/2026. Revisión A.
