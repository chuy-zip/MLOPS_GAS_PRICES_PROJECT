# Databricks notebook source
# MAGIC %md
# MAGIC # 21 Imágenes a plata
# MAGIC
# MAGIC Extrae EXIF y lecturas de OCR, aplica correcciones manuales y escribe las tablas de plata de imágenes.
# MAGIC
# MAGIC Pendiente de implementar en la fase 3. Ver `docs/arquitectura/arquitectura.md`.

# COMMAND ----------

catalogo = dbutils.widgets.get("catalogo")
print("Catálogo:", catalogo)
dbutils.notebook.exit("Pendiente de implementar")
