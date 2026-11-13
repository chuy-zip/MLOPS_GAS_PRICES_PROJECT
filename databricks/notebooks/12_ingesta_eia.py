# Databricks notebook source
# MAGIC %md
# MAGIC # 12 Ingesta de los precios internacionales de la EIA a bronce
# MAGIC
# MAGIC Lee los archivos de `data/eia` desde el repo público y los carga en `bronze.eia_precios` si su hash cambió.
# MAGIC
# MAGIC Pendiente de implementar en la fase 2. Ver `docs/arquitectura/arquitectura.md`.

# COMMAND ----------

catalogo = dbutils.widgets.get("catalogo")
print("Catálogo:", catalogo)
dbutils.notebook.exit("Pendiente de implementar")
