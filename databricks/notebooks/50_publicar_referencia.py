# Databricks notebook source
# MAGIC %md
# MAGIC # 50 Publicar la referencia actual
# MAGIC
# MAGIC Exporta la referencia vigente para la API.
# MAGIC
# MAGIC Pendiente de implementar en la fase 5. Ver `docs/arquitectura/arquitectura.md`.

# COMMAND ----------

catalogo = dbutils.widgets.get("catalogo")
print("Catálogo:", catalogo)
dbutils.notebook.exit("Pendiente de implementar")
