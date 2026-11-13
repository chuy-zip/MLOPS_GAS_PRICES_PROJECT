# Databricks notebook source
# MAGIC %md
# MAGIC # 21 Fotos a plata
# MAGIC
# MAGIC Extrae el precio de cada foto con OCR o un modelo de visión y escribe `silver.precios`.
# MAGIC Aplica al menos 3 reglas de calidad. Lo que falla va a `silver.precios_rejected` con el motivo.
# MAGIC Escribe con `MERGE` por fecha, ubicación, combustible y modalidad.
# MAGIC
# MAGIC Pendiente de implementar. Lo que pide el enunciado está en `docs/datos/fuentes_de_datos.md`,
# MAGIC sección "Qué pide el enunciado para las fotos".

# COMMAND ----------

catalogo = dbutils.widgets.get("catalogo")
print("Catálogo:", catalogo)
dbutils.notebook.exit("Pendiente de implementar")
