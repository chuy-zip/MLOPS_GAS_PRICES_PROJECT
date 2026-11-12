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

**Dónde están:** en el bucket de la external location `xloc-raw`, que es solo de lectura.

### Resultado de la exploración (2026-11-12)

Se obtuvo con el job `gas_price_exploracion`, que corre el notebook `databricks/notebooks/00_exploracion_raw.py`. No forma parte del pipeline y no escribe nada.

| Pregunta | Resultado |
|---|---|
| Cantidad | 110 archivos, 169 MB en total |
| Formatos | 109 HEIC y 1 JPG |
| Carpetas | `img/` (38), `img/2025/` (31), `img/2024/` (24) y `img/2023/` (17) |
| Metadatos | Las 110 fotos tienen fecha y GPS en el EXIF. Ninguna falló al abrirse |
| Fechas de toma | Del 14 de diciembre de 2022 al 8 de noviembre de 2026, con 1 a 6 fotos casi todos los meses |
| Dispositivos | iPhone 14 (91) y iPhone XS (19) |
| Lugares | Al menos 13 lugares distintos, redondeando el GPS a unos 100 metros. Uno concentra 63 fotos y otro 17. El resto tiene 6 fotos o menos |
| Perfil de color | Display P3, el de los iPhone. Hay que convertir a sRGB para mostrar las fotos |

**Hallazgos que afectan el diseño:**

1. **La carpeta no indica el año de la foto.** `img/2023/` tiene fotos de diciembre de 2022. La fecha siempre sale del EXIF.
2. **El monto de la carga no es fijo.** Las miniaturas muestran Q100, Q200 y Q300. La Actividad 2 usaba Q150 como valor de referencia para validar el OCR, y eso ya no aplica.
3. **Hay más de un tipo de dispensador.** La mayoría son de la misma marca, pero al menos uno es de otra marca con otra distribución de pantallas. El OCR no puede depender de posiciones fijas.
4. **110 fotos en casi 4 años no alcanzan para entrenar** un modelo semanal. Se confirma que el Excel del MEM es la fuente principal. Las fotos sirven para comparar estaciones contra el promedio nacional, sobre todo la estación con 63 fotos.

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
