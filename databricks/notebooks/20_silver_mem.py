# Databricks notebook source
# MAGIC %md
# MAGIC # 20 Excel del MEM a plata
# MAGIC
# MAGIC Convierte tipos, quita duplicados y escribe `silver.precios_oficiales`.
# MAGIC
# MAGIC Pendiente de implementar en la fase 3. Ver `docs/arquitectura/arquitectura.md`.

# COMMAND ----------

catalogo = dbutils.widgets.get("catalogo")
print("Catálogo:", catalogo)
dbutils.notebook.exit("Pendiente de implementar")
