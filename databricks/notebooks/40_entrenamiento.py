# Databricks notebook source
# MAGIC %md
# MAGIC # 40 Entrenamiento del modelo de tendencia
# MAGIC
# MAGIC 1. Lee `gold.features_modelo`. Si esos datos ya se usaron en una corrida anterior, termina sin entrenar,
# MAGIC    salvo que el parámetro `forzar_entrenamiento` valga `true`.
# MAGIC 2. Evalúa con partición temporal: entrena con el pasado y prueba con los últimos dos años.
# MAGIC    Registra las métricas del modelo y de la regla "repetir la semana pasada", para comparar.
# MAGIC 3. Entrena el modelo final con todas las semanas que tienen etiqueta.
# MAGIC 4. Lo registra en Unity Catalog con firma y le asigna el alias `champion`.
# MAGIC 5. Agrega una fila a `gold.metricas_modelo` con las métricas del modelo y de la línea base, para la API.
# MAGIC
# MAGIC El modelo y la evaluación están en `src/gas_price/modelo.py`. No hay un mínimo de desempeño para registrarlo.
# MAGIC La línea base del enunciado es "se repite la dirección de la semana anterior".

# COMMAND ----------

dbutils.widgets.text("catalogo", "equipo_01")
dbutils.widgets.text("esquema_gold", "gold")
dbutils.widgets.text("experimento", "/Shared/equipo-01-tendencia")
dbutils.widgets.text("forzar_entrenamiento", "false")

catalogo = dbutils.widgets.get("catalogo")
esquema_gold = dbutils.widgets.get("esquema_gold")
experimento = dbutils.widgets.get("experimento")
forzar = dbutils.widgets.get("forzar_entrenamiento").strip().lower() == "true"

# COMMAND ----------

import hashlib
import os
import sys

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..", "src")))
from gas_price import features, modelo

NOMBRE_MODELO = f"{catalogo}.{esquema_gold}.modelo_tendencia_precio"
ALIAS = "champion"

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(experimento)

# COMMAND ----------

semanales = spark.table(f"{catalogo}.{esquema_gold}.features_modelo").toPandas()
datos = modelo.con_etiqueta(semanales)

# Huella de los datos de entrenamiento. Si ya hay una corrida con la misma huella para el mismo modelo,
# no se vuelve a entrenar. Filtrar también por modelo hace que un catálogo nuevo siempre entrene.
columnas = [*features.VARIABLES, "etiqueta"]
huella = hashlib.sha256(pd.util.hash_pandas_object(datos[columnas], index=False).values.tobytes()).hexdigest()
previas = mlflow.search_runs(
    filter_string=f"tags.huella_datos = '{huella}' and tags.modelo = '{NOMBRE_MODELO}'", max_results=1
)
if len(previas) > 0 and not forzar:
    dbutils.notebook.exit(f"Sin cambios: estos datos ya se usaron en la corrida {previas.iloc[0]['run_id']}")

print(f"{len(datos)} filas con etiqueta, de {datos['semana'].min()} a {datos['semana'].max()}")

# COMMAND ----------

with mlflow.start_run(run_name="logistica_mem_eia") as corrida:
    _, resultado = modelo.evaluar(semanales)
    mlflow.log_metrics({k: v for k, v in resultado.items() if isinstance(v, float)})
    mlflow.log_params(
        {
            "modelo": "LogisticRegression",
            "semanas_de_prueba": modelo.SEMANAS_DE_PRUEBA,
            "umbral_cambio": features.UMBRAL_CAMBIO,
            "filas_entrenamiento": resultado["filas_entrenamiento"],
            "filas_prueba": resultado["filas_prueba"],
            "inicio_prueba": resultado["inicio_prueba"],
            "variables": ",".join(features.VARIABLES),
        }
    )
    mlflow.set_tags({"huella_datos": huella, "modelo": NOMBRE_MODELO, "fuentes": "mem,eia"})

    # El modelo final aprende de todas las semanas. Las métricas de arriba vienen de la evaluación con el pasado.
    final = modelo.construir_modelo().fit(datos[features.VARIABLES], datos["etiqueta"])
    firma = infer_signature(datos[features.VARIABLES], final.predict(datos[features.VARIABLES]))
    info = mlflow.sklearn.log_model(
        sk_model=final,
        name="model",
        signature=firma,
        input_example=datos[features.VARIABLES].head(3),
        serialization_format="cloudpickle",
        registered_model_name=NOMBRE_MODELO,
    )

print("Corrida:", corrida.info.run_id)
print(pd.Series(resultado).to_string())

# COMMAND ----------

# Se usa la versión que devolvió el registro. Buscar "la más reciente" justo después de registrar
# puede no encontrarla todavía, y el alias se quedaría en la versión anterior.
version = info.registered_model_version
MlflowClient().set_registered_model_alias(NOMBRE_MODELO, ALIAS, version)
print(f"{NOMBRE_MODELO}@{ALIAS} apunta a la versión {version}")

# COMMAND ----------

# Métricas para la API. La tabla la define databricks/sql/tablas.sql.
TABLA_METRICAS = f"{catalogo}.{esquema_gold}.metricas_modelo"
from pyspark.sql import functions as F

metricas = spark.createDataFrame(modelo.fila_de_metricas(resultado, version)).withColumn(
    "entrenado_en", F.current_timestamp()
)
metricas.select(*spark.table(TABLA_METRICAS).columns).write.insertInto(TABLA_METRICAS)
display(spark.table(TABLA_METRICAS).orderBy(F.col("entrenado_en").desc()))

# COMMAND ----------

# Prueba como lo haría un consumidor: cargar por alias y predecir la semana más reciente.
cargado = mlflow.pyfunc.load_model(f"models:/{NOMBRE_MODELO}@{ALIAS}")
ultima_semana = semanales[semanales["semana"] == semanales["semana"].max()]
display(ultima_semana[["semana", "combustible", "precio"]].assign(prediccion=cargado.predict(ultima_semana[features.VARIABLES])))
