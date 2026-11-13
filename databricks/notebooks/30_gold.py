# Databricks notebook source
# MAGIC %md
# MAGIC # 30 Plata a oro
# MAGIC
# MAGIC Construye las tres tablas de oro con el código de `src/gas_price/features.py`:
# MAGIC
# MAGIC | Tabla | Contenido |
# MAGIC |---|---|
# MAGIC | `gold.precios_diarios` | Un día por fila y combustible, sin huecos, con la cantidad de fotos del día |
# MAGIC | `gold.features_semanales` | Una fila por lunes y combustible, con las variables del modelo y la etiqueta |
# MAGIC | `gold.referencia_actual` | El último precio oficial por combustible y el rango de "buen precio" |
# MAGIC
# MAGIC Las tablas se reescriben completas en cada corrida. Sus columnas y tipos están en `databricks/sql/tablas.sql`.

# COMMAND ----------

dbutils.widgets.text("catalogo", "gas_price")
dbutils.widgets.text("esquema_silver", "silver")
dbutils.widgets.text("esquema_gold", "gold")

catalogo = dbutils.widgets.get("catalogo")
esquema_silver = dbutils.widgets.get("esquema_silver")
esquema_gold = dbutils.widgets.get("esquema_gold")

# COMMAND ----------

import os
import sys

from pyspark.sql import functions as F

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..", "src")))
from gas_price import features

plata = f"{catalogo}.{esquema_silver}"
oro = f"{catalogo}.{esquema_gold}"


def escribir(datos, tabla):
    """Reemplaza los datos de una tabla definida en databricks/sql/tablas.sql, sin cambiar su definición.

    Las columnas se ordenan como en la tabla. Si falta alguna o sobra alguna, la escritura falla.
    """
    destino = f"{oro}.{tabla}"
    columnas = spark.table(destino).columns
    sobrantes = set(datos.columns) - set(columnas)
    if sobrantes:
        raise ValueError(f"{destino}: columnas que no están en tablas.sql: {sorted(sobrantes)}")
    spark.createDataFrame(datos[columnas]).write.insertInto(destino, overwrite=True)
    print(f"{destino}: {len(datos)} filas")

# COMMAND ----------

oficiales = spark.table(f"{plata}.precios_oficiales").toPandas()
internacionales = spark.table(f"{plata}.precios_internacionales").toPandas()

diarios = features.precios_diarios(oficiales)

# Las fotos son opcionales: si su tabla de plata todavía no existe, el día queda con 0 fotos.
tabla_fotos = f"{plata}.imagenes_metadata"
if spark.catalog.tableExists(tabla_fotos):
    fotos = spark.table(tabla_fotos).groupBy("fecha").agg(F.count("*").alias("n_fotos")).toPandas()
    diarios = diarios.merge(fotos, on="fecha", how="left")
    diarios["n_fotos"] = diarios["n_fotos"].fillna(0)
else:
    print(f"{tabla_fotos} no existe todavía. n_fotos queda en 0")
    diarios["n_fotos"] = 0
diarios["n_fotos"] = diarios["n_fotos"].astype("int32")

semanales = features.features_semanales(diarios, internacionales)
referencia = features.referencia_actual(diarios)

# COMMAND ----------

escribir(diarios, "precios_diarios")
escribir(semanales, "features_semanales")
escribir(referencia, "referencia_actual")

# COMMAND ----------

display(spark.table(f"{oro}.referencia_actual"))

# COMMAND ----------

display(
    spark.table(f"{oro}.features_semanales")
    .groupBy("combustible", "etiqueta")
    .count()
    .orderBy("combustible", "etiqueta")
)
