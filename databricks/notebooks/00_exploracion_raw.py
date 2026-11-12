# Databricks notebook source
# MAGIC %md
# MAGIC # 00 Exploración del bucket raw
# MAGIC
# MAGIC Notebook de investigación. No es parte del pipeline y no escribe nada.
# MAGIC
# MAGIC Responde estas preguntas antes de diseñar la carga a bronce:
# MAGIC
# MAGIC 1. ¿Cuántos archivos hay y de qué tipo?
# MAGIC 2. ¿Cómo están organizados en carpetas?
# MAGIC 3. ¿De qué fechas, dispositivos y lugares son las fotos?
# MAGIC 4. ¿Las fotos se parecen entre sí?
# MAGIC
# MAGIC La URL del bucket se obtiene de la external location, así no queda escrita en el repo.

# COMMAND ----------

# MAGIC %pip install pillow-heif

# COMMAND ----------

import base64
import io

import pandas as pd
from pyspark.sql import functions as F

EXTERNAL_LOCATION = "xloc-raw"
EXTENSIONES_IMAGEN = ["heic", "heif", "jpg", "jpeg", "png"]
MINIATURAS = 6

url_raw = spark.sql(f"DESCRIBE EXTERNAL LOCATION `{EXTERNAL_LOCATION}`").collect()[0]["url"]
if not url_raw.endswith("/"):
    url_raw += "/"
print("Raw:", url_raw)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Inventario de archivos

# COMMAND ----------

# Solo se seleccionan metadatos, así Spark no lee el contenido de los archivos.
archivos_df = (
    spark.read.format("binaryFile")
    .option("recursiveFileLookup", "true")
    .load(url_raw)
    .select("path", "length", "modificationTime")
)
inventario = archivos_df.toPandas()
if inventario.empty:
    dbutils.notebook.exit("El bucket raw está vacío.")

inventario["relativa"] = inventario["path"].str.split(url_raw.rstrip("/") + "/", n=1).str[-1]
inventario["nombre"] = inventario["relativa"].str.rsplit("/", n=1).str[-1]
inventario["tamano_mb"] = inventario["length"] / 1e6
inventario["modificado"] = pd.to_datetime(inventario["modificationTime"])
inventario["extension"] = (
    inventario["nombre"].str.extract(r"\.([^.]+)$", expand=False).str.lower().fillna("(sin extension)")
)
inventario["carpeta"] = inventario["relativa"].apply(lambda r: r.rsplit("/", 1)[0] if "/" in r else "(raiz)")

print("Archivos:", len(inventario))
print("Tamaño total (MB):", round(inventario["tamano_mb"].sum(), 1))
print("Fecha de carga:", inventario["modificado"].min(), "a", inventario["modificado"].max())

# COMMAND ----------

display(
    inventario.groupby("extension")
    .agg(archivos=("nombre", "count"), total_mb=("tamano_mb", "sum"), promedio_mb=("tamano_mb", "mean"))
    .reset_index()
    .sort_values("archivos", ascending=False)
)

# COMMAND ----------

display(
    inventario.groupby("carpeta")
    .agg(archivos=("nombre", "count"))
    .reset_index()
    .sort_values("archivos", ascending=False)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Metadatos EXIF de las fotos
# MAGIC
# MAGIC Fecha y hora de la toma, dispositivo, tamaño y GPS. Se leen en paralelo con Spark, sin bajar las fotos al driver.

# COMMAND ----------

ESQUEMA_EXIF = (
    "ruta string, fecha_hora_original string, modelo string, ancho int, alto int, "
    "latitud double, longitud double, error string"
)


def a_grados(valor, referencia):
    if not valor:
        return None
    grados, minutos, segundos = (float(x) for x in valor)
    decimal = grados + minutos / 60 + segundos / 3600
    return -decimal if referencia in ("S", "W") else decimal


def extraer_exif(lotes):
    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    for lote in lotes:
        filas = []
        for ruta, contenido in zip(lote["path"], lote["content"]):
            fila = {"ruta": ruta, "fecha_hora_original": None, "modelo": None, "ancho": None,
                    "alto": None, "latitud": None, "longitud": None, "error": None}
            try:
                with Image.open(io.BytesIO(contenido)) as imagen:
                    fila["ancho"], fila["alto"] = imagen.size
                    exif = imagen.getexif()
                    fila["modelo"] = exif.get(0x0110)
                    fila["fecha_hora_original"] = exif.get_ifd(0x8769).get(0x9003) or exif.get(0x0132)
                    gps = exif.get_ifd(0x8825)
                    if gps:
                        fila["latitud"] = a_grados(gps.get(2), gps.get(1))
                        fila["longitud"] = a_grados(gps.get(4), gps.get(3))
            except Exception as e:
                fila["error"] = f"{type(e).__name__}: {e}"[:200]
            filas.append(fila)
        yield pd.DataFrame(filas, columns=["ruta", "fecha_hora_original", "modelo", "ancho", "alto",
                                           "latitud", "longitud", "error"])


imagenes_df = (
    spark.read.format("binaryFile")
    .option("recursiveFileLookup", "true")
    .load(url_raw)
    .withColumn("extension", F.lower(F.regexp_extract("path", r"\.([^.]+)$", 1)))
    .filter(F.col("extension").isin(EXTENSIONES_IMAGEN))
)

metadata = imagenes_df.select("path", "content").mapInPandas(extraer_exif, schema=ESQUEMA_EXIF).toPandas()
metadata["fecha"] = pd.to_datetime(metadata["fecha_hora_original"], format="%Y:%m:%d %H:%M:%S", errors="coerce")

print("Fotos:", len(metadata))
print("Con fecha EXIF:", metadata["fecha"].notna().sum())
print("Con GPS:", metadata["latitud"].notna().sum())
print("No se pudieron abrir:", metadata["error"].notna().sum())
print("Fecha de toma:", metadata["fecha"].min(), "a", metadata["fecha"].max())

# COMMAND ----------

display(metadata.sort_values("fecha"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Fotos por mes y por dispositivo

# COMMAND ----------

display(metadata.assign(mes=metadata["fecha"].dt.strftime("%Y-%m")).groupby("mes", dropna=False).size().rename("fotos").reset_index())

# COMMAND ----------

display(metadata.groupby("modelo", dropna=False).size().rename("fotos").reset_index())

# COMMAND ----------

# MAGIC %md
# MAGIC ### Lugares aproximados
# MAGIC
# MAGIC Las coordenadas se redondean a 3 decimales, unos 100 metros. Cada lugar distinto es probablemente una estación distinta.

# COMMAND ----------

con_gps = metadata[metadata["latitud"].notna()].copy()
con_gps["lugar"] = con_gps["latitud"].round(3).astype(str) + ", " + con_gps["longitud"].round(3).astype(str)
display(con_gps.groupby("lugar").agg(fotos=("ruta", "count"), primera=("fecha", "min"), ultima=("fecha", "max")).reset_index().sort_values("fotos", ascending=False))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Muestra visual
# MAGIC
# MAGIC Miniaturas repartidas a lo largo del rango de fechas, para ver si todas las fotos se parecen.

# COMMAND ----------

from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()

ordenadas = metadata.sort_values("fecha", na_position="last").reset_index(drop=True)
paso = max(1, len(ordenadas) // MINIATURAS)
rutas_muestra = ordenadas["ruta"].iloc[::paso].head(MINIATURAS).tolist()

html = ""
for fila in imagenes_df.filter(F.col("path").isin(rutas_muestra)).select("path", "content").collect():
    with Image.open(io.BytesIO(fila["content"])) as imagen:
        imagen = ImageOps.exif_transpose(imagen)
        imagen.thumbnail((360, 360))
        buffer = io.BytesIO()
        imagen.convert("RGB").save(buffer, format="JPEG", quality=80)
    codificada = base64.b64encode(buffer.getvalue()).decode()
    nombre = fila["path"].rsplit("/", 1)[-1]
    html += (
        f'<figure style="display:inline-block;margin:6px;text-align:center">'
        f'<img src="data:image/jpeg;base64,{codificada}"/>'
        f'<figcaption style="font-size:11px">{nombre}</figcaption></figure>'
    )
displayHTML(html)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Conclusiones
# MAGIC
# MAGIC Completar después de correr el notebook y copiar al documento `docs/datos/fuentes_de_datos.md`:
# MAGIC
# MAGIC 1. Cantidad de fotos y formatos.
# MAGIC 2. Rango de fechas de toma.
# MAGIC 3. Cantidad de lugares distintos.
# MAGIC 4. Si las fotos son parecidas entre sí o hay varios tipos de dispensador.
# MAGIC 5. Archivos que no son fotos y qué contienen.
