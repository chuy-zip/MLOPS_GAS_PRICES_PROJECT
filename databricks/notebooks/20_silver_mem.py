# Databricks notebook source
# MAGIC %md
# MAGIC # 20 Excel del MEM a plata
# MAGIC
# MAGIC Toma la versión más reciente del Excel en `bronze.mem_precios` y escribe `silver.precios_oficiales`.
# MAGIC Las reglas de limpieza están en `src/gas_price/mem.py`:
# MAGIC
# MAGIC 1. Un precio en 0 significa que ese día no se publicó, y no genera fila.
# MAGIC 2. Las fechas repetidas con valores idénticos quedan una vez. Si difieren, la tarea falla.
# MAGIC 3. Cada fecha recibe su régimen fiscal: normal, subsidio o exento.
# MAGIC
# MAGIC La tabla se reescribe completa en cada corrida. El Excel siempre trae la historia entera, así que reescribir es idempotente.

# COMMAND ----------

dbutils.widgets.text("catalogo", "gas_price")
dbutils.widgets.text("esquema_bronze", "bronze")
dbutils.widgets.text("esquema_silver", "silver")

catalogo = dbutils.widgets.get("catalogo")
esquema_bronze = dbutils.widgets.get("esquema_bronze")
esquema_silver = dbutils.widgets.get("esquema_silver")

# COMMAND ----------

import os
import sys

from pyspark.sql import functions as F

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..", "src")))
from gas_price import mem

ORIGEN = f"{catalogo}.{esquema_bronze}.mem_precios"
DESTINO = f"{catalogo}.{esquema_silver}.precios_oficiales"

# COMMAND ----------

bronce = spark.table(ORIGEN)
ultima = bronce.orderBy(F.col("_ingestado_en").desc()).select("_hash_archivo", "_archivo_origen").first()
print("Versión usada:", ultima["_archivo_origen"])

crudo = bronce.filter(F.col("_hash_archivo") == ultima["_hash_archivo"]).toPandas().sort_values("fila_excel")
limpio = mem.limpiar(crudo)
largo = mem.a_formato_largo(limpio)
largo["_archivo_origen"] = ultima["_archivo_origen"]

print(f"{len(crudo)} filas en bronce, {len(limpio)} fechas únicas, {len(largo)} filas en plata")
fuera = mem.precios_fuera_de_rango(limpio)
if len(fuera) > 0:
    raise ValueError(f"{len(fuera)} precios fuera de rango:\n{fuera.head()}")

# COMMAND ----------

esquema = """
    fecha DATE, combustible STRING, precio_gtq_galon DOUBLE,
    tipo_cambio DOUBLE, regimen_fiscal STRING, _archivo_origen STRING
"""
# La tabla la define databricks/sql/tablas.sql. insertInto con overwrite reemplaza los datos sin cambiar la definición.
filas = spark.createDataFrame(largo, schema=esquema)
filas.select(*spark.table(DESTINO).columns).write.insertInto(DESTINO, overwrite=True)

display(spark.table(DESTINO).groupBy("combustible").agg(F.count("*").alias("dias"), F.min("fecha"), F.max("fecha")))
