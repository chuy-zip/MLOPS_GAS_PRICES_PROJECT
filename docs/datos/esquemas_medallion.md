# Capas y esquemas

## Qué va en cada capa

| Capa | External location | Qué guarda | Quién escribe |
|---|---|---|---|
| Raw | xloc-raw | Las fotos tal como las dejó el catedrático | Nadie del equipo. Es solo de lectura |
| Bronce | xloc-cusn | Los datos de raw y del Excel como tablas, sin interpretar. También la copia del Excel que viene del repo | Tareas de ingesta |
| Plata | xloc-ag | Datos interpretados, validados y con un esquema común | Tareas de limpieza |
| Oro | xloc-au | Series diarias completas, variables del modelo, referencia vigente y el modelo | Tareas de agregación y entrenamiento |

**Raw contra bronce.** Raw es la zona de aterrizaje de los archivos originales y nunca se modifica. Bronce guarda esos mismos datos como tablas Delta, sin limpiarlos, más columnas de control: cuándo se cargaron, de qué archivo vienen y su hash. Si una regla de limpieza cambia, plata y oro se reconstruyen desde bronce sin volver a leer todo raw.

**Nombres.** Los buckets tienen nombres de metales y no se pueden renombrar. El estándar se pone en Unity Catalog. La tabla de arriba es el mapeo.

## Organización en Unity Catalog

Un esquema por capa. Cada esquema usa su bucket como ubicación administrada, así sus tablas quedan físicamente en ese bucket. Un esquema solo puede tener una ubicación, por eso hay uno por capa. Los conceptos y los permisos están explicados en [databricks.md](../infraestructura/databricks.md).

**Catálogo propio `gas_price`, ya creado.** Separa el proyecto del resto del workspace, permite dar permisos al catálogo completo y los esquemas no necesitan prefijo.

| Esquema | Ubicación administrada | Contenido |
|---|---|---|
| `gas_price.bronze` | xloc-cusn | Tablas de bronce y el volumen `archivos` |
| `gas_price.silver` | xloc-ag | Tablas de plata |
| `gas_price.gold` | xloc-au | Tablas de oro y el modelo |

1. Raw no tiene esquema. Las fotos se leen por ruta.
2. El volumen administrado `archivos` del esquema de bronce guarda la copia del Excel que viene del repo y los checkpoints de Auto Loader.
3. Guardar las tablas en los buckets requiere `CREATE MANAGED STORAGE` sobre las external locations de bronce, plata y oro.
4. **Estado actual:** `xloc-cusn` y `xloc-ag` son de solo lectura. Solo `xloc-au` permite escritura. Se pidió al catedrático habilitar la escritura en bronce y plata.
5. **Mientras tanto:** los tres esquemas se crean sin ubicación y usan el almacenamiento por defecto. Como `xloc-au` sí permite escritura, una tarea final copia las tablas de oro como Delta por ruta a su bucket. Cuando llegue el permiso, se recrean los esquemas con su ubicación y se vuelve a correr el pipeline.
6. El catálogo y los nombres de los esquemas son parámetros del bundle. Cambiarlos no requiere cambiar los notebooks.

En el resto de los documentos, `bronze.tabla` abrevia la tabla en el esquema de bronce, y lo mismo para plata y oro.

## Definición de las tablas

Las columnas y los tipos de todas las tablas están en `databricks/sql/tablas.sql`. Es la fuente de verdad, y las tablas de este documento la resumen.

1. El job `gas_price_setup` corre ese archivo con `CREATE TABLE IF NOT EXISTS`. Lo lanza el CI después de cada despliegue, así que las tablas nuevas existen apenas se hace merge.
2. Las tareas del pipeline escriben con `insertInto`, que respeta la definición de la tabla. Si una tarea produce columnas distintas, la escritura falla en lugar de cambiar la tabla.
3. El test `tests/test_tablas_sql.py` compara el archivo con las columnas que produce el código de `src/`. Si no coinciden, el PR queda en rojo.
4. `CREATE TABLE IF NOT EXISTS` no modifica una tabla que ya existe. Los cambios a tablas existentes se aplican a mano, con los pasos de la siguiente sección.

## Cómo cambiar una tabla

**Importante:** entre el merge y el paso manual en Databricks, la tarea que escribe esa tabla falla, porque el código y la tabla no coinciden. Hacer el paso manual apenas termine el despliegue, y avisar al equipo que no corra el pipeline mientras tanto.

### Agregar una columna

Funciona en cualquier capa y no borra datos. Ejemplo: agregar `region STRING` a `gold.precios_diarios`.

1. Crear una rama.
2. Cambiar el código para que produzca la columna. Agregarla **al final** de las columnas que ya existen.
3. Agregarla también **al final** de esa tabla en `databricks/sql/tablas.sql`, con su tipo y un comentario:

   ```sql
     n_fotos INT COMMENT '...',
     region STRING COMMENT 'Región de la estación'
   ```

4. Correr `pytest`. `tests/test_tablas_sql.py` revisa que el archivo y el código tengan las mismas columnas en el mismo orden.
5. Abrir el PR, esperar `plan` y `tests` en verde y hacer merge.
6. Cuando termine el despliegue, en el SQL Editor:

   ```sql
   ALTER TABLE gas_price.gold.precios_diarios
     ADD COLUMNS (region STRING COMMENT 'Región de la estación');
   ```

7. Correr `gas_price_pipeline`.

Las filas que ya existían quedan con la columna nueva en nulo. En plata y oro no importa, porque se reescriben completas en el paso 7. En bronce, las versiones anteriores de los archivos quedan con nulo en esa columna.

### Cambiar el tipo, renombrar o quitar una columna

Unity Catalog no deja hacer estos cambios sin reescribir la tabla, así que se borra y se recrea.

1. Pasos 1 a 5 de la sección anterior, con el cambio que corresponda.
2. Cuando termine el despliegue, en el SQL Editor: `DROP TABLE gas_price.<esquema>.<tabla>;`
3. Correr el job `gas_price_setup`, que la recrea con la definición nueva.
4. Correr `gas_price_pipeline`, que la llena.

**En plata y oro** no se pierde nada, porque el pipeline las reconstruye en unos 2 minutos. **En bronce** se pierden las versiones anteriores de los archivos: al recrearla solo vuelve la versión actual del repo. Antes de borrar una tabla de bronce, consultarlo con el equipo.

### Agregar una tabla nueva

Por ejemplo, las tablas de fotos.

1. Agregar su `CREATE TABLE IF NOT EXISTS` en `databricks/sql/tablas.sql`, con columnas, tipos y comentarios.
2. Escribir en ella con `insertInto` o `MERGE`, nunca con `saveAsTable`. `saveAsTable` puede cambiar la definición de la tabla.
3. Agregar la tabla en `tests/test_tablas_sql.py`: en la lista de `test_estan_las_siete_tablas` y, si su código está en `src/`, en un test que compare sus columnas.
4. Hacer merge. El despliegue corre `gas_price_setup` y la tabla queda creada sin pasos manuales.

## Bronce

**`bronze.imagenes`**: una fila por foto.

| Columna | Tipo | Nota |
|---|---|---|
| image_id | STRING | Hash SHA256 del contenido. Evita duplicados aunque cambie el nombre |
| ruta | STRING | Ruta en raw |
| nombre_archivo | STRING | |
| tamano_bytes | BIGINT | |
| modificado_en | TIMESTAMP | Fecha del archivo en el bucket |
| contenido | BINARY | Bytes originales |
| _ingestado_en | TIMESTAMP | |

**`bronze.mem_precios`**: una fila por fila del Excel, todo como texto.

| Columna | Tipo | Nota |
|---|---|---|
| fila_excel | INT | Posición original |
| fecha_texto | STRING | |
| tipo_cambio_texto | STRING | |
| super_texto, regular_texto, diesel_texto | STRING | |
| _archivo_origen | STRING | Ruta de la copia en el volumen `archivos`, con la huella en el nombre |
| _url_origen | STRING | URL del repo de donde se descargó |
| _hash_archivo | STRING | Huella SHA256 del archivo. Si ya está en la tabla, no se vuelve a cargar |
| _ingestado_en | TIMESTAMP | |

Cada versión nueva del Excel se agrega a la tabla, sin borrar las anteriores. Plata usa la más reciente.

**`bronze.eia_precios`**: una fila por fila de cada archivo de la EIA, todo como texto. Columnas: serie, fecha_texto, precio_texto, _archivo_origen, _url_origen, _hash_archivo y _ingestado_en. Funciona igual que `bronze.mem_precios`, con una versión por serie.

## Plata

**`silver.imagenes_metadata`**: una fila por foto.

| Columna | Tipo | Nota |
|---|---|---|
| image_id | STRING | Huella SHA256, la misma de bronce |
| fecha_hora_local | TIMESTAMP | De `DateTimeOriginal`, presente en las 110 fotos |
| zona_horaria | STRING | De `OffsetTimeOriginal`, por ejemplo `-06:00` |
| fecha | DATE | Fecha local de la foto |
| latitud, longitud | DOUBLE | |
| altitud_m | DOUBLE | |
| error_gps_m | DOUBLE | De `GPSHPositioningError` |
| lugar | STRING | Coordenadas redondeadas a unos 100 metros, para agrupar por estación |
| modelo_camara | STRING | |
| orientacion | INT | |

No se usa la hora del GPS como fecha: `GPSTimeStamp` solo está en el 83 % de las fotos.

Si se decide sacar más datos de las imágenes, sus tablas se agregan aquí. Ver el tema abierto en [fuentes_de_datos.md](fuentes_de_datos.md).

**`silver.precios_oficiales`**: formato largo, una fila por fecha y combustible. Columnas: fecha, combustible, precio_gtq_galon, tipo_cambio, regimen_fiscal y _archivo_origen.

1. `combustible` toma los valores `super`, `regular` y `diesel`.
2. Los días con precio en 0 no tienen fila, porque ese día no hubo publicación.
3. Las fechas repetidas con valores idénticos quedan una sola vez.
4. `regimen_fiscal` vale `normal`, `subsidio` o `exento`, según las notas del Excel.

**`silver.precios_internacionales`**: una fila por día de mercado y serie. Columnas: fecha, serie (`gasolina` o `diesel`), precio_usd_galon y _archivo_origen. Los fines de semana y feriados no tienen fila. Oro los rellena con el último precio conocido.

## Oro

**`gold.precios_diarios`**: un día por fila y combustible, sin huecos en el calendario.

| Columna | Tipo | Nota |
|---|---|---|
| fecha | DATE | |
| combustible | STRING | |
| precio_oficial | DOUBLE | |
| es_imputado | BOOLEAN | True si el día no venía en el Excel |
| tipo_cambio | DOUBLE | |
| regimen_fiscal | STRING | |
| n_fotos | INT | Cantidad de fotos tomadas ese día |

**Regla de relleno:** el precio oficial se mantiene igual entre un cambio y el siguiente. Un día faltante toma el último precio conocido y queda marcado con `es_imputado`. Las fotos nunca rellenan el precio oficial.

**`gold.features_semanales`**: una fila por lunes y combustible.

| Columnas | Contenido |
|---|---|
| semana, combustible, precio | El lunes, el combustible y su precio ese día |
| cambio_l1 a cambio_l4 | Cambio de precio de cada una de las 4 semanas anteriores |
| tendencia_4, tendencia_8 | Precio menos su promedio de 4 y de 8 semanas |
| tipo_cambio_cambio, mes | Cambio semanal del tipo de cambio y mes del año |
| otro_super_l1, otro_regular_l1, otro_diesel_l1 | Último cambio semanal de cada combustible |
| intl_cambio_1 a intl_cambio_3 | Cambio del precio internacional en quetzales en las 3 semanas anteriores |
| brecha_vs_8 | Precio local menos internacional, comparado con su promedio de 8 semanas |
| cambio_siguiente, etiqueta | Cambio hasta el lunes siguiente y su dirección: `sube`, `baja` o `igual`. La última semana no tiene etiqueta |

El precio internacional de cada lunes es el promedio de los 7 días anteriores, para usar solo lo que ya se sabía ese día.

**`gold.referencia_actual`**: una fila por combustible. Es lo que consulta la API.

| Columna | Contenido |
|---|---|
| combustible, fecha_referencia, precio_referencia | Último precio oficial |
| limite_normal | Precio de referencia más Q1.00, la diferencia normal entre estaciones según el análisis de negocio |
| tipo_cambio, regimen_fiscal | Del último día |
| proximo_cambio | El lunes siguiente, cuando se espera el próximo cambio |

Un precio igual o menor que la referencia es buen precio. Hasta `limite_normal` es normal. Arriba de eso es caro.

**Modelo:** `modelo_tendencia_precio` en el esquema de oro, por ejemplo `gas_price.gold.modelo_tendencia_precio`, con alias `champion`.
