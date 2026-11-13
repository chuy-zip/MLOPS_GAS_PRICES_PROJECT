-- Definición de las tablas del pipeline. Es la fuente de verdad de sus columnas y tipos.
--
-- La corre la tarea 05_crear_tablas al inicio del job. Los marcadores ${catalogo},
-- ${esquema_bronze}, ${esquema_silver} y ${esquema_gold} se reemplazan con los parámetros del job.
--
-- CREATE TABLE IF NOT EXISTS no modifica una tabla que ya existe. Para cambiar el tipo de una
-- columna, hay que borrar la tabla y volver a correr el job, que la recrea y la llena.
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

-- Oro

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.precios_diarios (
  fecha DATE,
  combustible STRING,
  precio_oficial DOUBLE,
  es_imputado BOOLEAN COMMENT 'True si el día no venía en el Excel y tomó el último precio conocido',
  tipo_cambio DOUBLE,
  regimen_fiscal STRING,
  n_fotos INT COMMENT 'Fotos tomadas ese día. 0 si la tabla de fotos no existe'
)
COMMENT 'Calendario completo por combustible, sin huecos';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.features_semanales (
  semana DATE COMMENT 'Lunes de la semana',
  combustible STRING,
  precio DOUBLE,
  cambio_l1 DOUBLE COMMENT 'Cambio de precio de la semana que termina este lunes',
  cambio_l2 DOUBLE,
  cambio_l3 DOUBLE,
  cambio_l4 DOUBLE,
  tendencia_4 DOUBLE COMMENT 'Precio menos su promedio de 4 semanas',
  tendencia_8 DOUBLE COMMENT 'Precio menos su promedio de 8 semanas',
  tipo_cambio_cambio DOUBLE,
  mes INT,
  otro_super_l1 DOUBLE,
  otro_regular_l1 DOUBLE,
  otro_diesel_l1 DOUBLE,
  intl_cambio_1 DOUBLE COMMENT 'Cambio del precio internacional en quetzales, semana anterior',
  intl_cambio_2 DOUBLE,
  intl_cambio_3 DOUBLE,
  brecha_vs_8 DOUBLE COMMENT 'Precio local menos internacional, contra su promedio de 8 semanas',
  cambio_siguiente DOUBLE COMMENT 'Cambio hasta el lunes siguiente. Nulo en la semana actual',
  etiqueta STRING COMMENT 'sube, baja o igual. Nula en la semana actual, que es la que se predice'
)
COMMENT 'Variables y etiqueta del modelo de tendencia, una fila por lunes y combustible';

CREATE TABLE IF NOT EXISTS ${catalogo}.${esquema_gold}.referencia_actual (
  combustible STRING,
  fecha_referencia DATE COMMENT 'Último día con precio oficial',
  precio_referencia DOUBLE COMMENT 'Igual o debajo es buen precio',
  limite_normal DOUBLE COMMENT 'Hasta aquí es precio normal. Arriba es caro',
  tipo_cambio DOUBLE,
  regimen_fiscal STRING,
  proximo_cambio DATE COMMENT 'Lunes en que se espera el próximo cambio'
)
COMMENT 'Precio oficial vigente por combustible. Es lo que consulta la API';
