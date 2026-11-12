# Fuentes de datos

## 1. Precios oficiales del MEM

**Archivo:** `data/mem/precios_promedio_nacionales_diarios.xlsx`. Es la publicación "Precios promedio nacionales diarios" de la Dirección General de Hidrocarburos del MEM, hoja `PUBLICACIÓN WEB`.

**Contenido (versión del 2026-11-10):**

1. 4,359 días con fecha válida, del 8 de febrero de 2013 al 10 de noviembre de 2026.
2. Columnas útiles: fecha, tipo de cambio, Gasolina Superior, Gasolina Regular y Aceite Combustible Diésel. Todas en quetzales por galón, salvo el tipo de cambio.
3. Sin nulos en esas columnas.
4. 3 fechas duplicadas y 668 días faltantes dentro del rango.
5. El precio de la Súper cambió en 798 días: 561 lunes, 180 martes y el resto otros días.
6. Las filas finales son notas de fuente. Una nota explica el subsidio del 28 de abril al 5 de julio de 2026.

**Por qué es la fuente principal:** 13 años de datos diarios dan cientos de cambios semanales de precio. Eso alcanza para entrenar y validar un modelo de series de tiempo. Las fotos no.

**Por qué vive en el repo:** se intentó descargar el Excel de forma automática desde la web del MEM y no funcionó de forma confiable. Versionarlo en el repo deja un historial de cada actualización y permite validarla antes de usarla.

### Cómo se actualiza

```mermaid
flowchart LR
    A["Alguien reemplaza el Excel<br/>en una rama"] --> B["Pull request"]
    B --> C["CI: test de no empeorar"]
    C --> D["Merge a main"]
    D --> E["CI dispara el job"]
    E --> F["Databricks lee el Excel<br/>desde el repo público"]
    F --> G["Copia el archivo a bronce<br/>y carga la tabla"]
```

1. El archivo no se sube a raw porque raw es solo de lectura.
2. Databricks lee el Excel directo del repo público. GitHub Actions no necesita escribir en los buckets.
3. La tarea de ingesta calcula el hash del archivo. Si no cambió, no lo vuelve a cargar.

### Test de "no empeorar"

Corre en cada pull request que cambia el Excel. Compara la versión nueva contra la que está en `main`.

| Regla | Falla si |
|---|---|
| Columnas obligatorias | Falta FECHA, Tipo de Cambio, Gasolina Superior, Gasolina Regular o Aceite Combustible Diésel |
| Sin pérdida de fechas | Una fecha de la versión anterior ya no está |
| Sin cambios silenciosos | Cambia el precio de una fecha que ya existía |
| Sin nulos nuevos | Aparecen nulos donde antes había datos |
| Sin duplicados nuevos | Aparece una fecha repetida que antes no estaba |
| Rango razonable | Un precio queda fuera de Q10 a Q80 por galón |

Si un cambio de precio histórico es intencional, por ejemplo una corrección del MEM, se justifica en el pull request y se aprueba a mano.

## 2. Fotos de dispensadores

**Dónde están:** en el bucket de la external location `xloc-raw`, que es solo de lectura. En el repo del curso hay 5 fotos de prueba, en [Casos-Estudio/Images](https://github.com/SergioAle210/ML-Engineering/tree/main/Casos-Estudio/Images), pero el bucket debería tener más.

**Qué no sabemos todavía:**

1. Cuántas fotos hay.
2. En qué formatos están (HEIC, JPG u otros).
3. De qué fechas son.
4. De cuántas estaciones distintas son.
5. Si todas muestran el mismo tipo de dispensador.

Para responderlo está el notebook `databricks/notebooks/00_exploracion_raw.py`. Es un job de investigación, no forma parte del pipeline y no escribe nada. Lista los archivos, lee el EXIF (fecha, dispositivo y GPS) y muestra algunas miniaturas.

**Qué aporta cada foto** (según el análisis de negocio y la Actividad 2):

1. El total pagado y los galones, en la pantalla principal.
2. Los precios por galón de cada combustible, en las pantallas pequeñas de abajo.
3. Fecha, hora y ubicación, en el EXIF.

**Para qué se usan:**

1. Como entrada del usuario, para leer el precio de una foto.
2. Para medir cuánto se aleja el precio de una estación del promedio nacional del mismo día.

No se usan para rellenar precios oficiales faltantes.

## 3. Correcciones manuales

El OCR falla con reflejos y ángulos difíciles. En la Actividad 2, 2 de 5 fotos necesitaron corrección manual. Las correcciones se guardarán en un CSV versionado en `data/correcciones/`, con el mismo flujo de validación que el Excel.
