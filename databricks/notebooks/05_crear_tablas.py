# Databricks notebook source
# MAGIC %md
# MAGIC # 05 Crear las tablas
# MAGIC
# MAGIC Corre `databricks/sql/tablas.sql`, que define las columnas y los tipos de cada tabla del pipeline.
# MAGIC Usa `CREATE TABLE IF NOT EXISTS`: las tablas que ya existen no se modifican.
# MAGIC
# MAGIC Es la única tarea del job `equipo-01-setup` (clave `gas_price_setup` en el bundle), que el CI corre después de cada despliegue.
# MAGIC También se puede correr a mano, por ejemplo después de borrar una tabla.
# MAGIC
# MAGIC Las demás tareas escriben con `insertInto`, que respeta la definición de la tabla.
# MAGIC Si una tarea produce columnas distintas a las de este archivo, la escritura falla.

# COMMAND ----------

dbutils.widgets.text("catalogo", "equipo_01")
dbutils.widgets.text("esquema_bronze", "bronze")
dbutils.widgets.text("esquema_silver", "silver")
dbutils.widgets.text("esquema_gold", "gold")

parametros = {
    nombre: dbutils.widgets.get(nombre)
    for nombre in ["catalogo", "esquema_bronze", "esquema_silver", "esquema_gold"]
}

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

for sentencia in sentencias:
    spark.sql(sentencia)
    tabla = sentencia.split("EXISTS", 1)[1].split("(", 1)[0].strip()
    print("OK", tabla)
