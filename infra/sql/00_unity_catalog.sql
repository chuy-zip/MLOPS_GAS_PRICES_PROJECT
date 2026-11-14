-- Objetos de Unity Catalog del proyecto.
-- Lo corre un administrador una sola vez en el SQL Editor de Databricks.
-- Se puede volver a correr sin problema: no borra ni reemplaza nada.
--
-- Los esquemas no tienen ubicación propia. Cada tabla es externa y declara su ruta en el bucket
-- de su capa, en databricks/sql/tablas.sql. El volumen archivos se queda en Databricks.
-- Ver docs/infraestructura/databricks.md, sección "Estado final".

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
