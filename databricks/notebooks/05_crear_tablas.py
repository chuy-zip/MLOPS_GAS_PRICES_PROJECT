# Databricks notebook source
# MAGIC %md
# MAGIC # 05 Crear las tablas
# MAGIC
# MAGIC Corre `databricks/sql/tablas.sql`, que define las columnas, los tipos y la ubicación de cada tabla del pipeline.
# MAGIC Usa `CREATE TABLE IF NOT EXISTS`: las tablas que ya existen no se modifican.
# MAGIC
# MAGIC Es la única tarea del job `equipo-01-setup` (clave `gas_price_setup` en el bundle), que el CI corre después de cada despliegue.
# MAGIC También se puede correr a mano, por ejemplo después de borrar una tabla.
# MAGIC
# MAGIC **Ubicación.** Las tablas son externas: sus archivos viven en el bucket de su capa, dentro del prefijo del equipo,
# MAGIC por ejemplo `<bucket de oro>/equipo-01/gold/predicciones`. La URL de cada bucket se obtiene al correr con
# MAGIC `DESCRIBE EXTERNAL LOCATION`, así no queda escrita en el repo público.
# MAGIC
# MAGIC Las demás tareas escriben con `insertInto` o `MERGE`, que respetan la definición de la tabla.

# COMMAND ----------

dbutils.widgets.text("catalogo", "equipo_01")
dbutils.widgets.text("esquema_bronze", "bronze")
dbutils.widgets.text("esquema_silver", "silver")
dbutils.widgets.text("esquema_gold", "gold")
dbutils.widgets.text("ubicacion_bronze", "xloc-cusn")
dbutils.widgets.text("ubicacion_silver", "xloc-ag")
dbutils.widgets.text("ubicacion_gold", "xloc-au")
dbutils.widgets.text("prefijo_equipo", "equipo-01")

parametros = {
    nombre: dbutils.widgets.get(nombre)
    for nombre in ["catalogo", "esquema_bronze", "esquema_silver", "esquema_gold"]
}
prefijo = dbutils.widgets.get("prefijo_equipo")

# COMMAND ----------

# Ruta de cada capa: URL del bucket, prefijo del equipo y nombre de la capa.
for capa in ["bronze", "silver", "gold"]:
    ubicacion = dbutils.widgets.get(f"ubicacion_{capa}")
    url = spark.sql(f"DESCRIBE EXTERNAL LOCATION `{ubicacion}`").first()["url"]
    parametros[f"ruta_{capa}"] = f"{url.rstrip('/')}/{prefijo}/{capa}"
    print(f"{capa}: external location {ubicacion}, prefijo {prefijo}/{capa}")

# COMMAND ----------

import os

ruta = os.path.abspath(os.path.join(os.getcwd(), "..", "sql", "tablas.sql"))
with open(ruta, encoding="utf-8") as archivo:
    texto = archivo.read()

for nombre, valor in parametros.items():
    texto = texto.replace("${" + nombre + "}", valor)

# Se quitan las líneas de comentario y se separa por punto y coma.
sin_comentarios = "\n".join(linea for linea in texto.splitlines() if not linea.strip().startswith("--"))
sentencias = [s.strip() for s in sin_comentarios.split(";") if s.strip()]

tablas = []
for sentencia in sentencias:
    spark.sql(sentencia)
    tabla = sentencia.split("EXISTS", 1)[1].split("(", 1)[0].strip()
    ubicacion_esperada = sentencia.split("LOCATION '", 1)[1].split("'", 1)[0]
    tablas.append((tabla, ubicacion_esperada))
    print("OK", tabla)

# COMMAND ----------

# Una tabla creada antes de la migración sigue en el almacenamiento por defecto, porque
# CREATE TABLE IF NOT EXISTS no la modifica. Se avisa para borrarla y que se recree en el bucket.
fuera_del_bucket = []
for tabla, ubicacion_esperada in tablas:
    ubicacion_real = spark.sql(f"DESCRIBE DETAIL {tabla}").first()["location"]
    if ubicacion_real.rstrip("/") != ubicacion_esperada.rstrip("/"):
        fuera_del_bucket.append(tabla)

if fuera_del_bucket:
    print("ATENCIÓN: estas tablas no están en su bucket. Bórralas con DROP TABLE y vuelve a correr este job:")
    for tabla in fuera_del_bucket:
        print("   ", tabla)
else:
    print(f"Las {len(tablas)} tablas están en su bucket")
