# Databricks notebook source
# MAGIC %md
# MAGIC # 50 Predicción de la semana siguiente
# MAGIC
# MAGIC 1. Carga el modelo `champion` desde Unity Catalog.
# MAGIC 2. Predice la dirección del cambio de la semana siguiente para cada combustible, con los datos de la semana más reciente.
# MAGIC    Las semanas van de martes a lunes y se identifican por su martes de inicio.
# MAGIC 3. Guarda la predicción en `gold.predicciones`. Si esa semana ya tenía predicción, la actualiza.
# MAGIC 4. Completa la dirección real y el acierto de las predicciones pasadas, cuando ya se conocen.
# MAGIC
# MAGIC Las predicciones se acumulan semana a semana. Así se puede medir el acierto del modelo en semanas
# MAGIC que no usó para entrenar. La lógica está en `src/gas_price/modelo.py`.

# COMMAND ----------

dbutils.widgets.text("catalogo", "equipo_01")
dbutils.widgets.text("esquema_gold", "gold")

catalogo = dbutils.widgets.get("catalogo")
esquema_gold = dbutils.widgets.get("esquema_gold")

# COMMAND ----------

import os
import sys

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
from pyspark.sql import functions as F

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..", "src")))
from gas_price import modelo

oro = f"{catalogo}.{esquema_gold}"
NOMBRE_MODELO = f"{oro}.modelo_tendencia_precio"
ALIAS = "champion"
TABLA = f"{oro}.predicciones"

mlflow.set_registry_uri("databricks-uc")

# COMMAND ----------

version = MlflowClient().get_model_version_by_alias(NOMBRE_MODELO, ALIAS).version
# sklearn y no pyfunc, porque pyfunc solo devuelve la clase y aquí también se necesitan las probabilidades.
campeon = mlflow.sklearn.load_model(f"models:/{NOMBRE_MODELO}@{ALIAS}")
print(f"Modelo {NOMBRE_MODELO} versión {version}")

semanales = spark.table(f"{oro}.features_modelo").toPandas()
filas = modelo.semana_a_predecir(semanales)
if filas.empty:
    dbutils.notebook.exit("No hay una semana sin etiqueta para predecir")

nuevas = modelo.predecir(campeon, filas, version_modelo=version)
display(nuevas)

# COMMAND ----------

# Guarda o actualiza la predicción de la semana. No toca las semanas que ya tienen dirección real.
(
    spark.createDataFrame(nuevas)
    .withColumn("predicho_en", F.current_timestamp())
    .createOrReplaceTempView("nuevas_predicciones")
)
spark.sql(f"""
    MERGE INTO {TABLA} AS t
    USING nuevas_predicciones AS s
    ON t.semana = s.semana AND t.combustible = s.combustible
    WHEN MATCHED AND t.direccion_real IS NULL THEN UPDATE SET
        semana_objetivo = s.semana_objetivo,
        prediccion = s.prediccion,
        probabilidad = s.probabilidad,
        prob_sube = s.prob_sube,
        prob_baja = s.prob_baja,
        prob_se_mantiene = s.prob_se_mantiene,
        version_modelo = s.version_modelo,
        predicho_en = s.predicho_en
    WHEN NOT MATCHED THEN INSERT (
        semana, semana_objetivo, combustible, prediccion, probabilidad,
        prob_sube, prob_baja, prob_se_mantiene, version_modelo, predicho_en
    ) VALUES (
        s.semana, s.semana_objetivo, s.combustible, s.prediccion, s.probabilidad,
        s.prob_sube, s.prob_baja, s.prob_se_mantiene, s.version_modelo, s.predicho_en
    )
""")

# COMMAND ----------

# La etiqueta de una semana en features_modelo es justo la dirección real que se predijo para ella.
spark.sql(f"""
    MERGE INTO {TABLA} AS t
    USING (
        SELECT semana, combustible, etiqueta
        FROM {oro}.features_modelo
        WHERE etiqueta IS NOT NULL
    ) AS s
    ON t.semana = s.semana AND t.combustible = s.combustible
    WHEN MATCHED AND t.direccion_real IS NULL THEN UPDATE SET
        direccion_real = s.etiqueta,
        acierto = (t.prediccion = s.etiqueta)
""")

display(spark.table(TABLA).orderBy(F.col("semana").desc(), "combustible"))
