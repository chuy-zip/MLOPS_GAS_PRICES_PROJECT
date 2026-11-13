# Databricks notebook source
# MAGIC %md
# MAGIC # 10 Ingesta de fotos a bronce
# MAGIC
# MAGIC Lee las fotos por la external location con `binaryFile` o Auto Loader y escribe `bronze.fotos_precios`,
# MAGIC con el contenido, `path`, `modificationTime`, `length`, `_ingestion_timestamp` y `_source_file`.
# MAGIC Carga incremental: una segunda corrida no duplica fotos.
# MAGIC
# MAGIC Pendiente de implementar. Lo que pide el enunciado está en `docs/datos/fuentes_de_datos.md`,
# MAGIC sección "Qué pide el enunciado para las fotos".

# COMMAND ----------

catalogo = dbutils.widgets.get("catalogo")
print("Catálogo:", catalogo)
dbutils.notebook.exit("Pendiente de implementar")
