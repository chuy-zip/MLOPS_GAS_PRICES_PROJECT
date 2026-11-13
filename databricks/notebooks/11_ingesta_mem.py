# Databricks notebook source
# MAGIC %md
# MAGIC # 11 Ingesta del Excel del MEM a bronce
# MAGIC
# MAGIC 1. Descarga el Excel desde el repo público.
# MAGIC 2. Si su huella SHA256 ya está en bronce, termina sin hacer nada.
# MAGIC 3. Si es nuevo, guarda una copia en el volumen `archivos` y agrega sus filas a `bronze.mem_precios`, todo como texto.
# MAGIC
# MAGIC Cada versión del Excel queda en bronce con su huella. Plata usa la más reciente.

# COMMAND ----------

# MAGIC %pip install -q "pandas>=2.2" openpyxl python-calamine

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# En un job, los parámetros llegan como widgets. Los valores por defecto sirven para correrlo a mano.
dbutils.widgets.text("catalogo", "equipo_01")
dbutils.widgets.text("esquema_bronze", "bronze")
dbutils.widgets.text("repo_raw", "https://raw.githubusercontent.com/chuy-zip/equipo-01-gasolina-gt/main")

catalogo = dbutils.widgets.get("catalogo")
esquema_bronze = dbutils.widgets.get("esquema_bronze")
repo_raw = dbutils.widgets.get("repo_raw")

# COMMAND ----------

import hashlib
import io
import os
import sys
import urllib.request

from pyspark.sql import functions as F

# El código compartido vive en src/, dos carpetas arriba de este notebook.
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..", "src")))
from gas_price import mem

RUTA_EN_REPO = "data/mem/precios_promedio_nacionales_diarios.xlsx"
TABLA = f"{catalogo}.{esquema_bronze}.mem_precios"

# COMMAND ----------

url = f"{repo_raw}/{RUTA_EN_REPO}"
with urllib.request.urlopen(url, timeout=60) as respuesta:
    contenido = respuesta.read()
huella = hashlib.sha256(contenido).hexdigest()
print("Archivo:", url)
print("Huella:", huella)

ya_cargado = spark.catalog.tableExists(TABLA) and (
    spark.table(TABLA).filter(F.col("_file_hash") == huella).limit(1).count() > 0
)
if ya_cargado:
    dbutils.notebook.exit("Sin cambios: esta versión del Excel ya está en bronce")

# COMMAND ----------

# Copia del archivo original en el volumen, con la huella en el nombre para no pisar versiones anteriores.
ruta_volumen = f"/Volumes/{catalogo}/{esquema_bronze}/archivos/mem/{huella[:12]}_{os.path.basename(RUTA_EN_REPO)}"
os.makedirs(os.path.dirname(ruta_volumen), exist_ok=True)
with open(ruta_volumen, "wb") as archivo:
    archivo.write(contenido)

crudo = mem.extraer_crudo(mem.leer_hoja(io.BytesIO(contenido)))
crudo["fila_excel"] = crudo["fila_excel"].astype("int32")
crudo["_source_file"] = ruta_volumen
crudo["_source_url"] = url
crudo["_file_hash"] = huella

esquema = """
    fila_excel INT, fecha_texto STRING, tipo_cambio_texto STRING,
    super_texto STRING, regular_texto STRING, diesel_texto STRING,
    _source_file STRING, _source_url STRING, _file_hash STRING
"""
filas = spark.createDataFrame(crudo, schema=esquema).withColumn("_ingestion_timestamp", F.current_timestamp())
# La tabla la define databricks/sql/tablas.sql. insertInto respeta esa definición.
filas.select(*spark.table(TABLA).columns).write.insertInto(TABLA)

print(f"{len(crudo)} filas agregadas a {TABLA}")
dbutils.notebook.exit(f"Cargadas {len(crudo)} filas")
