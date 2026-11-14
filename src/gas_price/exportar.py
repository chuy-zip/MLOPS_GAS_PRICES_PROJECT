"""Lo que necesita la API y cómo convertirlo. Lo usa `scripts/exportar_para_api.py`.

La API no puede leer Databricks ni S3, así que se lleva una copia: el modelo `champion`
y algunas tablas de oro. Aquí se define qué tablas, cómo se convierten las respuestas de
la API de SQL de Databricks a pandas y cómo se verifica que el modelo descargado sea el correcto.
"""

from __future__ import annotations

import pandas as pd

from gas_price import modelo

# Archivo de salida y consulta. {oro} se reemplaza por catálogo.esquema de oro.
TABLAS = {
    "referencia_actual": "SELECT * FROM {oro}.referencia_actual ORDER BY combustible",
    "precio_semanal": "SELECT * FROM {oro}.precio_semanal ORDER BY semana, combustible, fuente",
    "metricas_modelo": "SELECT * FROM {oro}.metricas_modelo ORDER BY entrenado_en DESC",
    "predicciones": "SELECT * FROM {oro}.predicciones ORDER BY semana, combustible",
    # Solo la semana más reciente: es la entrada del modelo para /prediccion.
    "features_modelo": (
        "SELECT * FROM {oro}.features_modelo "
        "WHERE semana = (SELECT MAX(semana) FROM {oro}.features_modelo) ORDER BY combustible"
    ),
}

NOMBRE_MODELO = "{oro}.modelo_tendencia_precio"
ALIAS = "champion"

_ENTEROS = {"INT", "LONG", "SHORT", "BYTE"}
_DECIMALES = {"DOUBLE", "FLOAT", "DECIMAL"}


def a_dataframe(columnas: list[tuple[str, str]], filas: list[list[str | None]]) -> pd.DataFrame:
    """Convierte una respuesta JSON_ARRAY de la API de SQL a pandas con los tipos correctos.

    La API devuelve todos los valores como texto. `columnas` es una lista de (nombre, tipo),
    con el tipo como lo nombra Databricks: DATE, DOUBLE, INT, BOOLEAN, STRING, etc.
    """
    nombres = [nombre for nombre, _ in columnas]
    datos = pd.DataFrame(filas or [], columns=nombres, dtype=object)
    for nombre, tipo in columnas:
        tipo = str(tipo).upper()
        if tipo == "DATE":
            datos[nombre] = pd.to_datetime(datos[nombre]).dt.date
        elif tipo == "TIMESTAMP":
            datos[nombre] = pd.to_datetime(datos[nombre], utc=True)
        elif tipo in _DECIMALES:
            datos[nombre] = pd.to_numeric(datos[nombre]).astype(float)
        elif tipo in _ENTEROS:
            datos[nombre] = pd.to_numeric(datos[nombre]).astype("Int64")
        elif tipo == "BOOLEAN":
            datos[nombre] = datos[nombre].map({"true": True, "false": False})
    return datos


def comparar_con_predicciones(campeon, features_ultima: pd.DataFrame, predicciones: pd.DataFrame) -> list[str]:
    """Predice con el modelo descargado y lo compara con lo que el job guardó en `gold.predicciones`.

    Devuelve una lista de diferencias. Vacía significa que el modelo empaquetado predice lo mismo
    que el modelo de Databricks.
    """
    if features_ultima.empty:
        return ["features_modelo no tiene filas para predecir"]

    locales = modelo.predecir(campeon, features_ultima, version_modelo="local")
    guardadas = predicciones[predicciones["semana"].isin(locales["semana"])].set_index("combustible")
    diferencias = []
    for _, fila in locales.iterrows():
        if fila["combustible"] not in guardadas.index:
            diferencias.append(f"{fila['combustible']}: no hay predicción guardada para la semana {fila['semana']}")
            continue
        esperada = guardadas.loc[fila["combustible"], "prediccion"]
        if fila["prediccion"] != esperada:
            diferencias.append(f"{fila['combustible']}: el modelo descargado dice {fila['prediccion']} y Databricks dice {esperada}")
    return diferencias
