-- Definición de las tablas del pipeline. Es la fuente de verdad de sus columnas y tipos.
--
-- La corre el job gas_price_setup, con el notebook 05_crear_tablas. El CI lo lanza después de
-- cada despliegue. Los marcadores ${catalogo}, ${esquema_bronze}, ${esquema_silver} y
-- ${esquema_gold} se reemplazan con los parámetros del job.
--
-- CREATE TABLE IF NOT EXISTS no modifica una tabla que ya existe. Para cambiar una tabla
-- existente, seguir la guía "Cómo cambiar una tabla" en docs/datos/esquemas_medallion.md.
--
-- Todas las tablas son externas: sus archivos viven en el bucket de su capa, en
-- ${ruta_bronze}, ${ruta_silver} y ${ruta_gold}. El notebook los reemplaza con la URL de la
-- external location más el prefijo del equipo. Borrar una tabla externa no borra sus archivos.
-- Las tablas de oro desactivan los deletion vectors para que la librería deltalake de Python
-- pueda leerlas fuera de Databricks.
--
-- Las sentencias se separan con punto y coma. No usar punto y coma ni paréntesis dentro de los comentarios.
--
-- Nombres según el enunciado: columnas de auditoría _ingestion_timestamp y _source_file,
-- precio en quetzales por galón como precio_q_galon y semanas identificadas por su martes de inicio.

-- Bronce

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_bronze}.fotos_precios (
  path STRING COMMENT 'Ruta de la foto en el bucket',
  modificationTime TIMESTAMP COMMENT 'Fecha de modificación del archivo en el bucket',
  length BIGINT COMMENT 'Tamaño en bytes',
  content BINARY COMMENT 'Contenido binario original de la foto',
  _ingestion_timestamp TIMESTAMP COMMENT 'Fecha y hora de la carga',
  _source_file STRING COMMENT 'Ruta de la foto de origen'
)
COMMENT 'Fotos de precios tal como llegan, para poder reprocesarlas si cambia la extracción. Lo pide el enunciado'
LOCATION '${ruta_bronze}/fotos_precios';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_bronze}.mem_precios (
  fila_excel INT COMMENT 'Fila del Excel original',
  fecha_texto STRING,
  tipo_cambio_texto STRING,
  super_texto STRING,
  regular_texto STRING,
  diesel_texto STRING,
  _source_file STRING COMMENT 'Copia del archivo en el volumen archivos',
  _source_url STRING COMMENT 'URL del repo de donde se descargó',
  _file_hash STRING COMMENT 'Huella SHA256 del archivo. Identifica cada versión',
  _ingestion_timestamp TIMESTAMP
)
COMMENT 'Filas del Excel del MEM como texto, sin interpretar. Una versión por cada archivo distinto'
LOCATION '${ruta_bronze}/mem_precios';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_bronze}.eia_precios (
  serie STRING COMMENT 'gasolina o diesel',
  fecha_texto STRING,
  precio_texto STRING,
  _source_file STRING COMMENT 'Copia del archivo en el volumen archivos',
  _source_url STRING COMMENT 'URL del repo de donde se descargó',
  _file_hash STRING COMMENT 'Huella SHA256 del archivo. Identifica cada versión',
  _ingestion_timestamp TIMESTAMP
)
COMMENT 'Precios internacionales de la EIA como texto, sin interpretar. Una versión por cada archivo distinto'
LOCATION '${ruta_bronze}/eia_precios';

-- Plata

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_silver}.precios_oficiales (
  fecha DATE,
  combustible STRING COMMENT 'super, regular o diesel',
  precio_q_galon DECIMAL(10,2) COMMENT 'Precio en quetzales por galón',
  tipo_cambio DOUBLE COMMENT 'Quetzales por dólar',
  regimen_fiscal STRING COMMENT 'normal, subsidio o exento',
  _source_file STRING
)
COMMENT 'Precio oficial del MEM por fecha y combustible. Los días sin publicación no tienen fila'
LOCATION '${ruta_silver}/precios_oficiales';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_silver}.precios (
  fecha DATE COMMENT 'Fecha de la foto, tomada de la carpeta o del metadato',
  combustible STRING COMMENT 'super, regular o diesel',
  precio_q_galon DECIMAL(10,2) COMMENT 'Precio extraído de la foto, en quetzales por galón',
  modalidad STRING COMMENT 'Autoservicio o servicio completo, si aparece',
  ubicacion STRING COMMENT 'Estación, municipio o departamento, si aparece',
  foto_origen STRING COMMENT 'Ruta de la foto en bronce'
)
COMMENT 'Precios extraídos de las fotos que pasaron las reglas de calidad. Llave: fecha, ubicacion, combustible y modalidad. Lo pide el enunciado'
LOCATION '${ruta_silver}/precios';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_silver}.precios_rejected (
  fecha DATE COMMENT 'Fecha de la foto, si se pudo obtener',
  combustible STRING COMMENT 'Combustible extraído, si se pudo obtener',
  precio_q_galon DECIMAL(10,2) COMMENT 'Precio extraído, si se pudo obtener',
  modalidad STRING,
  ubicacion STRING,
  foto_origen STRING COMMENT 'Ruta de la foto en bronce',
  motivo STRING COMMENT 'Regla de calidad que falló'
)
COMMENT 'Fotos o filas que no pasaron las reglas de calidad, con el motivo. Lo pide el enunciado'
LOCATION '${ruta_silver}/precios_rejected';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_silver}.precios_internacionales (
  fecha DATE,
  serie STRING COMMENT 'gasolina o diesel',
  precio_usd_galon DOUBLE,
  _source_file STRING
)
COMMENT 'Precio spot de la EIA por día de mercado y serie'
LOCATION '${ruta_silver}/precios_internacionales';

-- Oro. El enunciado pide un comentario en cada tabla y columna de oro.

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.precios_diarios (
  fecha DATE COMMENT 'Día del calendario',
  combustible STRING COMMENT 'super, regular o diesel',
  precio_oficial DOUBLE COMMENT 'Precio oficial del MEM en quetzales por galón',
  es_imputado BOOLEAN COMMENT 'True si el día no venía en el Excel y tomó el último precio conocido',
  tipo_cambio DOUBLE COMMENT 'Quetzales por dólar según el Banco de Guatemala',
  regimen_fiscal STRING COMMENT 'normal, subsidio o exento, según las notas del Excel del MEM',
  n_fotos INT COMMENT 'Fotos con precio válido ese día, según silver.precios. 0 si esa tabla no existe'
)
COMMENT 'Calendario completo por combustible, sin huecos. Base de las variables semanales'
LOCATION '${ruta_gold}/precios_diarios'
TBLPROPERTIES ('delta.enableDeletionVectors' = false);

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.precio_semanal (
  semana DATE COMMENT 'Martes de inicio de la semana. Las semanas van de martes a lunes',
  combustible STRING COMMENT 'super, regular o diesel',
  fuente STRING COMMENT 'mem para el precio oficial, fotos para los precios extraídos de las fotos',
  precio_promedio DOUBLE COMMENT 'Precio promedio de la semana, en quetzales por galón',
  precio_minimo DOUBLE COMMENT 'Precio mínimo de la semana',
  precio_maximo DOUBLE COMMENT 'Precio máximo de la semana',
  n_observaciones INT COMMENT 'Días con precio oficial, o fotos con precio válido, en la semana'
)
COMMENT 'Precio promedio, mínimo y máximo por semana, combustible y fuente. La API lo usa para /precios'
LOCATION '${ruta_gold}/precio_semanal'
TBLPROPERTIES ('delta.enableDeletionVectors' = false);

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.variacion_semanal (
  semana DATE COMMENT 'Martes de inicio de la semana',
  combustible STRING COMMENT 'super, regular o diesel',
  fuente STRING COMMENT 'mem o fotos',
  precio_promedio DOUBLE COMMENT 'Precio promedio de la semana, en quetzales por galón',
  precio_anterior DOUBLE COMMENT 'Precio promedio de la semana anterior. Nulo si esa semana no tiene datos',
  variacion_q DOUBLE COMMENT 'Diferencia contra la semana anterior, en quetzales',
  variacion_pct DOUBLE COMMENT 'Diferencia contra la semana anterior, en porcentaje',
  direccion STRING COMMENT 'sube, baja o se_mantiene con umbral de Q0.10. Nula si no hay semana anterior'
)
COMMENT 'Variación semanal del precio y su dirección, por combustible y fuente'
LOCATION '${ruta_gold}/variacion_semanal'
TBLPROPERTIES ('delta.enableDeletionVectors' = false);

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.features_modelo (
  semana DATE COMMENT 'Martes de inicio de la semana. Los datos son los del cierre, el lunes',
  combustible STRING COMMENT 'super, regular o diesel',
  precio DOUBLE COMMENT 'Precio oficial vigente al cierre de la semana, en quetzales por galón',
  cambio_l1 DOUBLE COMMENT 'Cambio de precio de esta semana, en quetzales',
  cambio_l2 DOUBLE COMMENT 'Cambio de precio de hace 2 semanas',
  cambio_l3 DOUBLE COMMENT 'Cambio de precio de hace 3 semanas',
  cambio_l4 DOUBLE COMMENT 'Cambio de precio de hace 4 semanas',
  tendencia_4 DOUBLE COMMENT 'Precio menos su promedio de 4 semanas',
  tendencia_8 DOUBLE COMMENT 'Precio menos su promedio de 8 semanas',
  tipo_cambio_cambio DOUBLE COMMENT 'Cambio semanal del tipo de cambio',
  mes INT COMMENT 'Mes del año, de 1 a 12',
  otro_super_l1 DOUBLE COMMENT 'Último cambio semanal de la gasolina súper',
  otro_regular_l1 DOUBLE COMMENT 'Último cambio semanal de la gasolina regular',
  otro_diesel_l1 DOUBLE COMMENT 'Último cambio semanal del diésel',
  intl_cambio_1 DOUBLE COMMENT 'Cambio del precio internacional de la EIA en quetzales, semana anterior',
  intl_cambio_2 DOUBLE COMMENT 'Cambio del precio internacional de hace 2 semanas',
  intl_cambio_3 DOUBLE COMMENT 'Cambio del precio internacional de hace 3 semanas',
  brecha_vs_8 DOUBLE COMMENT 'Precio local menos internacional, contra su promedio de 8 semanas. Positivo sugiere baja',
  cambio_siguiente DOUBLE COMMENT 'Cambio de precio de la semana siguiente. Nulo en la semana actual',
  etiqueta STRING COMMENT 'sube, baja o se_mantiene con umbral de Q0.10. Nula en la semana actual, que es la que se predice'
)
COMMENT 'Variables y etiqueta del modelo de tendencia, una fila por semana y combustible. Es la tabla features_modelo del enunciado'
LOCATION '${ruta_gold}/features_modelo'
TBLPROPERTIES ('delta.enableDeletionVectors' = false);

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.referencia_actual (
  combustible STRING COMMENT 'super, regular o diesel',
  fecha_referencia DATE COMMENT 'Último día con precio oficial',
  precio_referencia DOUBLE COMMENT 'Último precio oficial en quetzales por galón. Igual o debajo es buen precio',
  limite_normal DOUBLE COMMENT 'Referencia más Q1.00. Hasta aquí es precio normal y arriba es caro',
  tipo_cambio DOUBLE COMMENT 'Quetzales por dólar del último día',
  regimen_fiscal STRING COMMENT 'normal, subsidio o exento',
  proximo_cambio DATE COMMENT 'Lunes en que se espera el próximo cambio'
)
COMMENT 'Precio oficial vigente por combustible. La API lo usa para /precios/actual'
LOCATION '${ruta_gold}/referencia_actual'
TBLPROPERTIES ('delta.enableDeletionVectors' = false);

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.predicciones (
  semana DATE COMMENT 'Martes de inicio de la semana con los datos usados para predecir',
  semana_objetivo DATE COMMENT 'Martes de inicio de la semana cuyo cambio de precio se predice',
  combustible STRING COMMENT 'super, regular o diesel',
  prediccion STRING COMMENT 'Dirección predicha: sube, baja o se_mantiene',
  probabilidad DOUBLE COMMENT 'Probabilidad de la dirección predicha, de 0 a 1',
  prob_sube DOUBLE COMMENT 'Probabilidad de que suba',
  prob_baja DOUBLE COMMENT 'Probabilidad de que baje',
  prob_se_mantiene DOUBLE COMMENT 'Probabilidad de que se mantenga',
  version_modelo STRING COMMENT 'Versión del modelo champion que hizo la predicción',
  predicho_en TIMESTAMP COMMENT 'Fecha y hora de la predicción',
  direccion_real STRING COMMENT 'Dirección que realmente ocurrió. Nula hasta que llega la semana objetivo',
  acierto BOOLEAN COMMENT 'True si la predicción coincidió con la dirección real. Nulo hasta conocerla'
)
COMMENT 'Una fila por semana y combustible con la predicción. La API la usa para /prediccion'
LOCATION '${ruta_gold}/predicciones'
TBLPROPERTIES ('delta.enableDeletionVectors' = false);

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.metricas_modelo (
  version_modelo STRING COMMENT 'Versión registrada del modelo',
  entrenado_en TIMESTAMP COMMENT 'Fecha y hora del entrenamiento',
  inicio_prueba DATE COMMENT 'Primera semana del periodo de prueba. Se entrena solo con semanas anteriores',
  filas_entrenamiento INT COMMENT 'Filas usadas para entrenar en la evaluación',
  filas_prueba INT COMMENT 'Filas del periodo de prueba',
  modelo_balanced_accuracy DOUBLE COMMENT 'Exactitud balanceada del modelo en la prueba. Al azar sería 0.33',
  modelo_f1_macro DOUBLE COMMENT 'F1 macro del modelo en la prueba',
  modelo_direccion_con_movimiento DOUBLE COMMENT 'Acierto de la dirección en las semanas en que el precio sí se movió',
  linea_base_balanced_accuracy DOUBLE COMMENT 'Lo mismo para la línea base: repetir la dirección de la semana anterior',
  linea_base_f1_macro DOUBLE COMMENT 'F1 macro de la línea base',
  linea_base_direccion_con_movimiento DOUBLE COMMENT 'Acierto de la dirección de la línea base cuando el precio se movió',
  supera_linea_base BOOLEAN COMMENT 'True si la exactitud balanceada del modelo supera a la de la línea base'
)
COMMENT 'Métricas de cada versión del modelo contra la línea base. La API la usa para /modelo/metricas'
LOCATION '${ruta_gold}/metricas_modelo'
TBLPROPERTIES ('delta.enableDeletionVectors' = false);
