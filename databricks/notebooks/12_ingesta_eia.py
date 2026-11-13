# Databricks notebook source
# MAGIC %md
# MAGIC # 12 Ingesta de los precios internacionales de la EIA a bronce
# MAGIC
# MAGIC Para cada serie de `data/eia`:
# MAGIC
# MAGIC 1. Descarga el archivo desde el repo público.
# MAGIC 2. Si su huella SHA256 ya está en bronce, la salta.
# MAGIC 3. Si es nueva, guarda una copia en el volumen `archivos` y agrega sus filas a `bronze.eia_precios`, todo como texto.

# COMMAND ----------

# MAGIC %pip install -q "pandas>=2.2" python-calamine

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalogo", "gas_price")
dbutils.widgets.text("esquema_bronze", "bronze")
dbutils.widgets.text("repo_raw", "https://raw.githubusercontent.com/chuy-zip/MLOPS_GAS_PRICES_PROJECT/main")

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

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..", "src")))
from gas_price import eia

TABLA = f"{catalogo}.{esquema_bronze}.eia_precios"
ESQUEMA = """
    serie STRING, fecha_texto STRING, precio_texto STRING,
    _archivo_origen STRING, _url_origen STRING, _hash_archivo STRING
"""

# COMMAND ----------

resumen = []
for serie, config in eia.SERIES.items():
    url = f"{repo_raw}/data/eia/{config['archivo']}"
    with urllib.request.urlopen(url, timeout=60) as respuesta:
        contenido = respuesta.read()
    huella = hashlib.sha256(contenido).hexdigest()

    ya_cargado = spark.catalog.tableExists(TABLA) and (
        spark.table(TABLA).filter((F.col("serie") == serie) & (F.col("_hash_archivo") == huella)).limit(1).count() > 0
    )
    if ya_cargado:
        resumen.append(f"{serie}: sin cambios")
        continue

    ruta_volumen = f"/Volumes/{catalogo}/{esquema_bronze}/archivos/eia/{huella[:12]}_{config['archivo']}"
    os.makedirs(os.path.dirname(ruta_volumen), exist_ok=True)
    with open(ruta_volumen, "wb") as archivo:
        archivo.write(contenido)

    crudo = eia.extraer_crudo(io.BytesIO(contenido))
    crudo.insert(0, "serie", serie)
    crudo["_archivo_origen"] = ruta_volumen
    crudo["_url_origen"] = url
    crudo["_hash_archivo"] = huella

    filas = spark.createDataFrame(crudo, schema=ESQUEMA).withColumn("_ingestado_en", F.current_timestamp())
    # La tabla la define databricks/sql/tablas.sql. insertInto respeta esa definición.
    filas.select(*spark.table(TABLA).columns).write.insertInto(TABLA)
    resumen.append(f"{serie}: {len(crudo)} filas")

print("\n".join(resumen))
dbutils.notebook.exit(". ".join(resumen))
