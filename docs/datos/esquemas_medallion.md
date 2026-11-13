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
| _archivo_origen | STRING | Ruta de la copia en el volumen `archivos` |
| _commit_origen | STRING | Commit del repo de donde vino el archivo |
| _hash_archivo | STRING | Si no cambió, no se vuelve a cargar |
| _ingestado_en | TIMESTAMP | |

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

**`silver.precios_oficiales`**: formato largo, una fila por fecha y combustible. Columnas: fecha, combustible, precio_gtq_galon, tipo_cambio, regimen_fiscal y _archivo_origen. Sin fechas duplicadas.

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

**`gold.features_semanales`**: una fila por semana y combustible, con el cambio de la semana, rezagos, tendencia, tipo de cambio, régimen fiscal y la etiqueta del cambio de la semana siguiente.

**`gold.referencia_actual`**: el último precio de referencia por combustible y el rango de "buen precio". Es lo que consulta la API.

**Modelo:** `modelo_tendencia_precio` en el esquema de oro, por ejemplo `gas_price.gold.modelo_tendencia_precio`, con alias `champion`.
