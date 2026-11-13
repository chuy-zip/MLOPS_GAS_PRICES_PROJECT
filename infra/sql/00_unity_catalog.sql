-- Objetos de Unity Catalog del proyecto.
-- Lo corre un administrador una sola vez en el SQL Editor de Databricks.
-- Se puede volver a correr sin problema: no borra ni reemplaza nada.
--
-- Los esquemas se crean sin ubicación administrada, así que usan el almacenamiento por defecto.
-- Cuando el catedrático habilite la escritura en los buckets, se cambia su ubicación con
-- ALTER SCHEMA ... SET MANAGED LOCATION y se recrean las tablas.
-- Ver docs/infraestructura/databricks.md.

CREATE CATALOG IF NOT EXISTS equipo_01
  COMMENT 'Equipo 01. Proyecto final de MLOps: predicción del precio de la gasolina en Guatemala';

CREATE SCHEMA IF NOT EXISTS equipo_01.bronze
  COMMENT 'Datos tal como llegan, sin interpretar, con columnas de control';

CREATE SCHEMA IF NOT EXISTS equipo_01.silver
  COMMENT 'Datos interpretados, validados y con un esquema común';

CREATE SCHEMA IF NOT EXISTS equipo_01.gold
  COMMENT 'Series diarias, variables del modelo, predicciones, métricas y el modelo';

CREATE VOLUME IF NOT EXISTS equipo_01.bronze.archivos
  COMMENT 'Copia del Excel del MEM que viene del repo y checkpoints de Auto Loader';
