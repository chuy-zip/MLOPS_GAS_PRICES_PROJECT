# Databricks notebook source
# MAGIC %md
# MAGIC # 10 Ingesta de imágenes a bronce
# MAGIC
# MAGIC Lee las fotos de raw con Auto Loader y las guarda en `bronze.imagenes`.
# MAGIC
# MAGIC Pendiente de implementar en la fase 2. Ver `docs/arquitectura/arquitectura.md`.

# COMMAND ----------

catalogo = dbutils.widgets.get("catalogo")
print("Catálogo:", catalogo)
dbutils.notebook.exit("Pendiente de implementar")
