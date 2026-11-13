-- Definición de las tablas del pipeline. Es la fuente de verdad de sus columnas y tipos.
--
-- La corre el job gas_price_setup, con el notebook 05_crear_tablas. El CI lo lanza después de
-- cada despliegue. Los marcadores ${catalogo}, ${esquema_bronze}, ${esquema_silver} y
-- ${esquema_gold} se reemplazan con los parámetros del job.
--
-- CREATE TABLE IF NOT EXISTS no modifica una tabla que ya existe. Para cambiar una tabla
-- existente, seguir la guía "Cómo cambiar una tabla" en docs/datos/esquemas_medallion.md.
--
-- Las sentencias se separan con punto y coma. No usar punto y coma dentro de los comentarios.

-- Bronce

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_bronze}.mem_precios (
  fila_excel INT COMMENT 'Fila del Excel original',
  fecha_texto STRING,
  tipo_cambio_texto STRING,
  super_texto STRING,
  regular_texto STRING,
  diesel_texto STRING,
  _archivo_origen STRING COMMENT 'Copia del archivo en el volumen archivos',
  _url_origen STRING COMMENT 'URL del repo de donde se descargó',
  _hash_archivo STRING COMMENT 'Huella SHA256 del archivo. Identifica cada versión',
  _ingestado_en TIMESTAMP
)
COMMENT 'Filas del Excel del MEM como texto, sin interpretar. Una versión por cada archivo distinto';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_bronze}.eia_precios (
  serie STRING COMMENT 'gasolina o diesel',
  fecha_texto STRING,
  precio_texto STRING,
  _archivo_origen STRING COMMENT 'Copia del archivo en el volumen archivos',
  _url_origen STRING COMMENT 'URL del repo de donde se descargó',
  _hash_archivo STRING COMMENT 'Huella SHA256 del archivo. Identifica cada versión',
  _ingestado_en TIMESTAMP
)
COMMENT 'Precios internacionales de la EIA como texto, sin interpretar. Una versión por cada archivo distinto';

-- Plata

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_silver}.precios_oficiales (
  fecha DATE,
  combustible STRING COMMENT 'super, regular o diesel',
  precio_gtq_galon DOUBLE,
  tipo_cambio DOUBLE COMMENT 'Quetzales por dólar',
  regimen_fiscal STRING COMMENT 'normal, subsidio o exento',
  _archivo_origen STRING
)
COMMENT 'Precio oficial del MEM por fecha y combustible. Los días sin publicación no tienen fila';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_silver}.precios_internacionales (
  fecha DATE,
  serie STRING COMMENT 'gasolina o diesel',
  precio_usd_galon DOUBLE,
  _archivo_origen STRING
)
COMMENT 'Precio spot de la EIA por día de mercado y serie';

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
COMMENT 'Calendario completo por combustible, sin huecos. Base de las variables semanales';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.features_semanales (
  semana DATE COMMENT 'Lunes de la semana. Las semanas van de martes a lunes',
  combustible STRING COMMENT 'super, regular o diesel',
  precio DOUBLE COMMENT 'Precio oficial vigente ese lunes, en quetzales por galón',
  cambio_l1 DOUBLE COMMENT 'Cambio de precio de la semana que termina este lunes, en quetzales',
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
  cambio_siguiente DOUBLE COMMENT 'Cambio hasta el lunes siguiente. Nulo en la semana actual',
  etiqueta STRING COMMENT 'sube, baja o se_mantiene con umbral de Q0.10. Nula en la semana actual, que es la que se predice'
)
COMMENT 'Variables y etiqueta del modelo de tendencia, una fila por lunes y combustible';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.referencia_actual (
  combustible STRING COMMENT 'super, regular o diesel',
  fecha_referencia DATE COMMENT 'Último día con precio oficial',
  precio_referencia DOUBLE COMMENT 'Último precio oficial en quetzales por galón. Igual o debajo es buen precio',
  limite_normal DOUBLE COMMENT 'Referencia más Q1.00. Hasta aquí es precio normal y arriba es caro',
  tipo_cambio DOUBLE COMMENT 'Quetzales por dólar del último día',
  regimen_fiscal STRING COMMENT 'normal, subsidio o exento',
  proximo_cambio DATE COMMENT 'Lunes en que se espera el próximo cambio'
)
COMMENT 'Precio oficial vigente por combustible. La API lo usa para /precios/actual';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.predicciones (
  semana DATE COMMENT 'Lunes con los datos usados para predecir',
  semana_objetivo DATE COMMENT 'Lunes cuyo cambio de precio se predice. Es una semana después',
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
COMMENT 'Una fila por semana y combustible con la predicción. La API la usa para /prediccion';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.metricas_modelo (
  version_modelo STRING COMMENT 'Versión registrada del modelo',
  entrenado_en TIMESTAMP COMMENT 'Fecha y hora del entrenamiento',
  inicio_prueba DATE COMMENT 'Primer lunes del periodo de prueba. Se entrena solo con semanas anteriores',
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
COMMENT 'Métricas de cada versión del modelo contra la línea base. La API la usa para /modelo/metricas';
