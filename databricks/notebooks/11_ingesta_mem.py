# Databricks notebook source
# MAGIC %md
# MAGIC # 11 Ingesta del Excel del MEM a bronce
# MAGIC
# MAGIC Lee el Excel desde el repo público y lo carga en `bronze.mem_precios` si su hash cambió.
# MAGIC
# MAGIC Pendiente de implementar en la fase 2. Ver `docs/arquitectura/arquitectura.md`.

# COMMAND ----------

catalogo = dbutils.widgets.get("catalogo")
print("Catálogo:", catalogo)
dbutils.notebook.exit("Pendiente de implementar")
