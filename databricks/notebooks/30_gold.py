# Databricks notebook source
# MAGIC %md
# MAGIC # 30 Plata a oro
# MAGIC
# MAGIC Construye las tres tablas de oro con el código de `src/gas_price/features.py`:
# MAGIC
# MAGIC | Tabla | Contenido |
# MAGIC |---|---|
# MAGIC | `gold.precios_diarios` | Un día por fila y combustible, sin huecos, con la cantidad de fotos del día |
# MAGIC | `gold.precio_semanal` | Precio promedio, mínimo y máximo por semana, combustible y fuente: `mem` o `fotos` |
# MAGIC | `gold.variacion_semanal` | Variación contra la semana anterior y su dirección |
# MAGIC | `gold.features_modelo` | Una fila por semana y combustible, con las variables del modelo y la etiqueta |
# MAGIC | `gold.referencia_actual` | El último precio oficial por combustible y el rango de "buen precio" |
# MAGIC
# MAGIC Las semanas van de martes a lunes y se identifican por su martes de inicio.
# MAGIC
# MAGIC Las tablas se reescriben completas en cada corrida. Sus columnas y tipos están en `databricks/sql/tablas.sql`.

# COMMAND ----------

dbutils.widgets.text("catalogo", "equipo_01")
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

# Precios de las fotos, desde silver.precios. Mientras esa tabla esté vacía, todo lo de fotos queda en 0 o sin filas.
precios_fotos = spark.table(f"{plata}.precios").select("fecha", "combustible", "precio_q_galon", "foto_origen").toPandas()
print(f"Precios de fotos en plata: {len(precios_fotos)}")

fotos_por_dia = precios_fotos.groupby("fecha")["foto_origen"].nunique().rename("n_fotos").reset_index()
diarios = diarios.merge(fotos_por_dia, on="fecha", how="left")
diarios["n_fotos"] = diarios["n_fotos"].fillna(0).astype("int32")

semanal = features.precio_semanal(diarios, precios_fotos)
variacion = features.variacion_semanal(semanal)
modelo_features = features.features_modelo(diarios, internacionales)
referencia = features.referencia_actual(diarios)

# COMMAND ----------

escribir(diarios, "precios_diarios")
escribir(semanal, "precio_semanal")
escribir(variacion, "variacion_semanal")
escribir(modelo_features, "features_modelo")
escribir(referencia, "referencia_actual")

# COMMAND ----------

display(spark.table(f"{oro}.referencia_actual"))

# COMMAND ----------

display(
    spark.table(f"{oro}.features_modelo")
    .groupBy("combustible", "etiqueta")
    .count()
    .orderBy("combustible", "etiqueta")
)

# COMMAND ----------

display(spark.table(f"{oro}.variacion_semanal").orderBy(F.col("semana").desc(), "combustible", "fuente").limit(12))
