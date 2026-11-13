# Databricks notebook source
# MAGIC %md
# MAGIC # 22 Precios internacionales de la EIA a plata
# MAGIC
# MAGIC Toma la versión más reciente de cada serie en `bronze.eia_precios` y escribe `silver.precios_internacionales`.
# MAGIC Las reglas de limpieza están en `src/gas_price/eia.py`. Los fines de semana y feriados no tienen fila: oro los rellena.
# MAGIC
# MAGIC La tabla se reescribe completa en cada corrida, porque cada archivo trae la serie entera.

# COMMAND ----------

dbutils.widgets.text("catalogo", "equipo_01")
dbutils.widgets.text("esquema_bronze", "bronze")
dbutils.widgets.text("esquema_silver", "silver")

catalogo = dbutils.widgets.get("catalogo")
esquema_bronze = dbutils.widgets.get("esquema_bronze")
esquema_silver = dbutils.widgets.get("esquema_silver")

# COMMAND ----------

import os
import sys

import pandas as pd
from pyspark.sql import Window
from pyspark.sql import functions as F

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..", "src")))
from gas_price import eia

ORIGEN = f"{catalogo}.{esquema_bronze}.eia_precios"
DESTINO = f"{catalogo}.{esquema_silver}.precios_internacionales"

# COMMAND ----------

bronce = spark.table(ORIGEN)
# Versión más reciente de cada serie.
reciente = Window.partitionBy("serie").orderBy(F.col("_ingestion_timestamp").desc())
ultimas = (
    bronce.select("serie", "_file_hash", "_source_file", "_ingestion_timestamp")
    .distinct()
    .withColumn("orden", F.row_number().over(reciente))
    .filter("orden = 1")
    .collect()
)

partes = []
for ultima in ultimas:
    crudo = bronce.filter(
        (F.col("serie") == ultima["serie"]) & (F.col("_file_hash") == ultima["_file_hash"])
    ).toPandas()
    limpio = eia.limpiar(crudo)
    fuera = eia.precios_fuera_de_rango(limpio)
    if len(fuera) > 0:
        raise ValueError(f"{ultima['serie']}: {len(fuera)} precios fuera de rango:\n{fuera.head()}")
    limpio.insert(1, "serie", ultima["serie"])
    limpio["_source_file"] = ultima["_source_file"]
    partes.append(limpio)
    print(f"{ultima['serie']}: {len(limpio)} días, de {limpio['fecha'].min()} a {limpio['fecha'].max()}")

# COMMAND ----------

esquema = "fecha DATE, serie STRING, precio_usd_galon DOUBLE, _source_file STRING"
# La tabla la define databricks/sql/tablas.sql. insertInto con overwrite reemplaza los datos sin cambiar la definición.
filas = spark.createDataFrame(pd.concat(partes, ignore_index=True), schema=esquema)
filas.select(*spark.table(DESTINO).columns).write.insertInto(DESTINO, overwrite=True)

display(spark.table(DESTINO).groupBy("serie").agg(F.count("*").alias("dias"), F.min("fecha"), F.max("fecha")))
