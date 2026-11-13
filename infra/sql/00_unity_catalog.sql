-- Objetos de Unity Catalog del proyecto.
-- Lo corre un administrador una sola vez en el SQL Editor de Databricks.
-- Se puede volver a correr sin problema: no borra ni reemplaza nada.
--
-- Los esquemas se crean sin ubicación administrada, así que usan el almacenamiento por defecto.
-- Cuando el catedrático habilite la escritura en los buckets, se recrean con su ubicación.
-- Ver docs/infraestructura/databricks.md.

CREATE CATALOG IF NOT EXISTS gas_price
  COMMENT 'Proyecto final de MLOps: monitoreo del precio de la gasolina';

CREATE SCHEMA IF NOT EXISTS gas_price.bronze
  COMMENT 'Datos tal como llegan, sin interpretar, con columnas de control';

CREATE SCHEMA IF NOT EXISTS gas_price.silver
  COMMENT 'Datos interpretados, validados y con un esquema común';

CREATE SCHEMA IF NOT EXISTS gas_price.gold
  COMMENT 'Series diarias, variables del modelo, referencia vigente y el modelo';

CREATE VOLUME IF NOT EXISTS gas_price.bronze.archivos
  COMMENT 'Copia del Excel del MEM que viene del repo y checkpoints de Auto Loader';
