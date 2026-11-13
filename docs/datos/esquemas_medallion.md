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

**Convención del enunciado.** Cada equipo usa un catálogo o esquemas con el prefijo `equipo_XX`, y en cada bucket escribe solo dentro de su prefijo `equipo-XX/`. Para este equipo: catálogo `equipo_01` y prefijo `equipo-01/`.

## Organización en Unity Catalog

Un esquema por capa. Cada esquema usa su bucket como ubicación administrada, así sus tablas quedan físicamente en ese bucket. Un esquema solo puede tener una ubicación, por eso hay uno por capa. Los conceptos y los permisos están explicados en [databricks.md](../infraestructura/databricks.md).

**Catálogo propio `equipo_01`.** Sigue la convención del enunciado, separa el proyecto del resto del workspace y permite dar permisos al catálogo completo. Lo crea `infra/sql/00_unity_catalog.sql`. Hasta el 2026-11-13 el catálogo se llamaba `gas_price`.

| Esquema | Ubicación administrada | Contenido |
|---|---|---|
| `equipo_01.bronze` | xloc-cusn, prefijo `equipo-01/` | Tablas de bronce y el volumen `archivos` |
| `equipo_01.silver` | xloc-ag, prefijo `equipo-01/` | Tablas de plata |
| `equipo_01.gold` | xloc-au, prefijo `equipo-01/` | Tablas de oro y el modelo |

1. Raw no tiene esquema. Las fotos se leen por ruta.
2. El volumen administrado `archivos` del esquema de bronce guarda la copia del Excel que viene del repo y los checkpoints de Auto Loader.
3. Guardar las tablas en los buckets requiere `CREATE MANAGED STORAGE` sobre las external locations de bronce, plata y oro.
4. **Estado actual:** `xloc-cusn` y `xloc-ag` son de solo lectura. Solo `xloc-au` permite escritura. Se pidió al catedrático habilitar la escritura en bronce y plata.
5. **Mientras tanto:** los tres esquemas se crean sin ubicación y usan el almacenamiento por defecto. Cuando llegue el permiso, se cambia su ubicación con `ALTER SCHEMA ... SET MANAGED LOCATION`, se recrean las tablas y se vuelve a correr el pipeline.
6. El catálogo y los nombres de los esquemas son parámetros del bundle. Cambiarlos no requiere cambiar los notebooks.

En el resto de los documentos, `bronze.tabla` abrevia la tabla en el esquema de bronce, y lo mismo para plata y oro.

## Definición de las tablas

Las columnas y los tipos de todas las tablas están en `databricks/sql/tablas.sql`. Es la fuente de verdad, y las tablas de este documento la resumen.

1. El job `equipo-01-setup` corre ese archivo con `CREATE TABLE IF NOT EXISTS`. Lo lanza el CI después de cada despliegue, así que las tablas nuevas existen apenas se hace merge.
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
   ALTER TABLE equipo_01.gold.precios_diarios
     ADD COLUMNS (region STRING COMMENT 'Región de la estación');
   ```

7. Correr `equipo-01-pipeline`.

Las filas que ya existían quedan con la columna nueva en nulo. En plata y oro no importa, porque se reescriben completas en el paso 7. En bronce, las versiones anteriores de los archivos quedan con nulo en esa columna.

### Cambiar el tipo, renombrar o quitar una columna

Unity Catalog no deja hacer estos cambios sin reescribir la tabla, así que se borra y se recrea.

1. Pasos 1 a 5 de la sección anterior, con el cambio que corresponda.
2. Cuando termine el despliegue, en el SQL Editor: `DROP TABLE gas_price.<esquema>.<tabla>;`
3. Correr el job `equipo-01-setup`, que la recrea con la definición nueva.
4. Correr `equipo-01-pipeline`, que la llena.

**En plata y oro** no se pierde nada, porque el pipeline las reconstruye en unos 2 minutos. **En bronce** se pierden las versiones anteriores de los archivos: al recrearla solo vuelve la versión actual del repo. Antes de borrar una tabla de bronce, consultarlo con el equipo.

### Agregar una tabla nueva

Por ejemplo, las tablas de fotos.

1. Agregar su `CREATE TABLE IF NOT EXISTS` en `databricks/sql/tablas.sql`, con columnas, tipos y comentarios.
2. Escribir en ella con `insertInto` o `MERGE`, nunca con `saveAsTable`. `saveAsTable` puede cambiar la definición de la tabla.
3. Agregar la tabla en `tests/test_tablas_sql.py`: en la lista de `test_estan_todas_las_tablas` y, si su código está en `src/`, en un test que compare sus columnas.
4. Hacer merge. El despliegue corre `equipo-01-setup` y la tabla queda creada sin pasos manuales.

## Tablas del enunciado

Todas las tablas que pide el enunciado ya están definidas en `databricks/sql/tablas.sql`, con sus nombres y columnas mínimas, y el despliegue las crea vacías. El equipo de fotos solo tiene que llenarlas.

| Tabla | Columnas | Estado |
|---|---|---|
| `bronze.fotos_precios` | `path`, `modificationTime`, `length`, `content`, `_ingestion_timestamp`, `_source_file` | Vacía. La llena el notebook `10_ingesta_imagenes` |
| `silver.precios` | `fecha`, `combustible`, `precio_q_galon`, `modalidad`, `ubicacion`, `foto_origen` | Vacía. La llena el notebook `21_silver_imagenes` con `MERGE` por fecha, ubicación, combustible y modalidad |
| `silver.precios_rejected` | Las mismas más `motivo` | Vacía. La llena el notebook `21_silver_imagenes` |
| `gold.precio_semanal` | Ver la sección de oro | Con datos del MEM. Las filas de fotos aparecen cuando `silver.precios` tenga datos |
| `gold.variacion_semanal` | Ver la sección de oro | Igual que la anterior |
| `gold.features_modelo` | Ver la sección de oro | Con datos |
| `gold.predicciones` | Ver la sección de oro | Con datos |

**Nombres comunes del enunciado:** las columnas de auditoría de bronce se llaman `_ingestion_timestamp` y `_source_file`, el precio en quetzales por galón es `precio_q_galon` de tipo decimal, y las semanas se identifican por su martes de inicio.

Si el equipo de fotos necesita más columnas, se agregan al final con la guía "Cómo cambiar una tabla".

## Bronce

**`bronze.mem_precios`**: una fila por fila del Excel, todo como texto.

| Columna | Tipo | Nota |
|---|---|---|
| fila_excel | INT | Posición original |
| fecha_texto | STRING | |
| tipo_cambio_texto | STRING | |
| super_texto, regular_texto, diesel_texto | STRING | |
| _source_file | STRING | Ruta de la copia en el volumen `archivos`, con la huella en el nombre |
| _source_url | STRING | URL del repo de donde se descargó |
| _file_hash | STRING | Huella SHA256 del archivo. Si ya está en la tabla, no se vuelve a cargar |
| _ingestion_timestamp | TIMESTAMP | |

Cada versión nueva del Excel se agrega a la tabla, sin borrar las anteriores. Plata usa la más reciente.

**`bronze.eia_precios`**: una fila por fila de cada archivo de la EIA, todo como texto. Columnas: serie, fecha_texto, precio_texto, _source_file, _source_url, _file_hash y _ingestion_timestamp. Funciona igual que `bronze.mem_precios`, con una versión por serie.

## Plata

**`silver.imagenes_metadata`**, opcional: una fila por foto con los metadatos del EXIF. El enunciado no la pide, pero puede servir para sacar la fecha y el lugar de cada foto antes de llenar `silver.precios`.

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

**Conexión con oro.** `gold.precios_diarios` cuenta en `n_fotos` las fotos con precio válido de cada día, desde `silver.precios`. Si esa tabla todavía no existe, `n_fotos` queda en 0.

**`silver.precios_oficiales`**: formato largo, una fila por fecha y combustible. Columnas: fecha, combustible, precio_q_galon, tipo_cambio, regimen_fiscal y _source_file.

1. `combustible` toma los valores `super`, `regular` y `diesel`.
2. Los días con precio en 0 no tienen fila, porque ese día no hubo publicación.
3. Las fechas repetidas con valores idénticos quedan una sola vez.
4. `regimen_fiscal` vale `normal`, `subsidio` o `exento`, según las notas del Excel.

**`silver.precios_internacionales`**: una fila por día de mercado y serie. Columnas: fecha, serie (`gasolina` o `diesel`), precio_usd_galon y _source_file. Los fines de semana y feriados no tienen fila. Oro los rellena con el último precio conocido.

## Oro

**`gold.precio_semanal`**: una fila por semana, combustible y fuente.

| Columna | Contenido |
|---|---|
| semana | Martes de inicio de la semana |
| combustible | `super`, `regular` o `diesel` |
| fuente | `mem` para el precio oficial, `fotos` para los precios extraídos de las fotos |
| precio_promedio, precio_minimo, precio_maximo | Del precio en quetzales por galón durante la semana |
| n_observaciones | Días con precio oficial, o fotos con precio válido |

Las dos fuentes van separadas: el precio oficial es un promedio nacional, y el de las fotos es el de estaciones concretas. El precio internacional de la EIA no va aquí, porque está en dólares y no es un precio local: se usa solo como variable del modelo.

**`gold.variacion_semanal`**: la misma llave más `precio_anterior`, `variacion_q`, `variacion_pct` y `direccion`. Solo compara semanas consecutivas. Si la semana anterior no tiene datos, como pasa a menudo con las fotos, la variación queda nula.

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

**`gold.features_modelo`**: una fila por semana y combustible. Es la tabla `features_modelo` del enunciado.

| Columnas | Contenido |
|---|---|
| semana, combustible, precio | El martes de inicio de la semana, el combustible y el precio vigente al cierre, el lunes |
| cambio_l1 a cambio_l4 | Cambio de precio de cada una de las 4 semanas anteriores |
| tendencia_4, tendencia_8 | Precio menos su promedio de 4 y de 8 semanas |
| tipo_cambio_cambio, mes | Cambio semanal del tipo de cambio y mes del año |
| otro_super_l1, otro_regular_l1, otro_diesel_l1 | Último cambio semanal de cada combustible |
| intl_cambio_1 a intl_cambio_3 | Cambio del precio internacional en quetzales en las 3 semanas anteriores |
| brecha_vs_8 | Precio local menos internacional, comparado con su promedio de 8 semanas |
| cambio_siguiente, etiqueta | Cambio de precio de la semana siguiente y su dirección: `sube`, `baja` o `se_mantiene`. La última semana no tiene etiqueta |

El precio internacional de cada semana es el promedio de los 7 días anteriores a su cierre, el lunes, para usar solo lo que ya se sabía ese día.

**`gold.referencia_actual`**: una fila por combustible. Es lo que consulta la API.

| Columna | Contenido |
|---|---|
| combustible, fecha_referencia, precio_referencia | Último precio oficial |
| limite_normal | Precio de referencia más Q1.00, la diferencia normal entre estaciones según el análisis de negocio |
| tipo_cambio, regimen_fiscal | Del último día |
| proximo_cambio | El lunes siguiente, cuando se espera el próximo cambio |

Un precio igual o menor que la referencia es buen precio. Hasta `limite_normal` es normal. Arriba de eso es caro.

**`gold.predicciones`**: una fila por semana y combustible, escrita por la tarea `50_predicciones`. Es lo que consulta la API en `/prediccion`.

| Columna | Contenido |
|---|---|
| semana, semana_objetivo | El martes de inicio de la semana con los datos usados y el de la semana cuyo cambio se predice |
| combustible | `super`, `regular` o `diesel` |
| prediccion, probabilidad | La dirección predicha y su probabilidad |
| prob_sube, prob_baja, prob_se_mantiene | La probabilidad de cada dirección |
| version_modelo, predicho_en | Qué versión del modelo predijo y cuándo |
| direccion_real, acierto | Lo que realmente pasó y si se acertó. Nulos hasta que llega la semana objetivo |

**`gold.metricas_modelo`**: una fila por versión del modelo, escrita por `40_entrenamiento`. Tiene las métricas del modelo, las de la línea base "se repite la dirección de la semana anterior" y si el modelo la supera. Es lo que consulta la API en `/modelo/metricas`.

**Comentarios.** El enunciado pide un `COMMENT` en cada tabla y columna de oro. Están en `databricks/sql/tablas.sql`, y un test revisa que ninguna columna de oro quede sin comentario.

**Modelo:** `modelo_tendencia_precio` en el esquema de oro, `equipo_01.gold.modelo_tendencia_precio`, con alias `champion`.
