# Ejemplo de memoria de cálculo

`ejemplo_memoria_E060.md` y `ejemplo_memoria_E060.docx` se generaron con:

```bash
python main.py --demo --salida salidas --formato ambos
```

Los datos son **sintéticos** (tres vigas de un edificio de demostración) y
sirven para revisar el formato y el nivel de detalle de la memoria. No
corresponden a un proyecto real ni sustituyen la verificación de un ingeniero
estructural.

Contenido:

- Portada con datos del proyecto y descargo de responsabilidad.
- Verificación de las combinaciones E.060 frente a las del modelo.
- Resumen global de las tres vigas.
- Memoria por viga: identificación, materiales, geometría, fuerzas de ETABS,
  flexión paso a paso, cortante y estribado, verificaciones del capítulo 21.
- Anexos de formulación, trazabilidad y observaciones.

Para generar una memoria con un modelo ETABS real, abra ETABS con el modelo
analizado y ejecute, por ejemplo:

```bash
python main.py --proyecto "Edificio A" --ubicacion "Cusco, Perú" \
  --caso-muerta DEAD --caso-viva LIVE --caso-sismo "SISMO X,SISMO Y" \
  --seccion VP-25x50 --formato ambos
```
