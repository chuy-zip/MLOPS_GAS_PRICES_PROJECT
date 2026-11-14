import datetime as dt

import pandas as pd

from gas_price import exportar, features, modelo
from test_features import semanales_sinteticas


def test_a_dataframe_convierte_los_tipos_de_databricks():
    columnas = [("semana", "DATE"), ("precio", "DOUBLE"), ("n", "INT"), ("ok", "BOOLEAN"), ("combustible", "STRING"), ("en", "TIMESTAMP")]
    filas = [
        ["2026-11-10", "32.49", "3", "true", "super", "2026-11-13T10:00:00.000Z"],
        ["2026-11-03", None, None, "false", "diesel", None],
    ]
    datos = exportar.a_dataframe(columnas, filas)

    assert datos.loc[0, "semana"] == dt.date(2026, 11, 10)
    assert datos.loc[0, "precio"] == 32.49
    assert pd.isna(datos.loc[1, "precio"])
    assert datos.loc[0, "n"] == 3 and pd.isna(datos.loc[1, "n"])
    assert datos.loc[0, "ok"] is True or datos.loc[0, "ok"] == True  # noqa: E712
    assert datos.loc[1, "combustible"] == "diesel"
    assert datos.loc[0, "en"].year == 2026


def test_a_dataframe_sin_filas_conserva_las_columnas():
    datos = exportar.a_dataframe([("semana", "DATE"), ("precio", "DOUBLE")], [])
    assert list(datos.columns) == ["semana", "precio"]
    assert datos.empty


def test_comparar_detecta_coincidencias_y_diferencias():
    datos = semanales_sinteticas()
    ultima = datos["semana"].max()
    datos.loc[datos["semana"] == ultima, "etiqueta"] = None
    con_etiqueta = modelo.con_etiqueta(datos)
    campeon = modelo.construir_modelo().fit(con_etiqueta[features.VARIABLES], con_etiqueta["etiqueta"])
    filas = modelo.semana_a_predecir(datos)

    guardadas = modelo.predecir(campeon, filas, version_modelo="1")
    assert exportar.comparar_con_predicciones(campeon, filas, guardadas) == []

    alteradas = guardadas.copy()
    alteradas.loc[0, "prediccion"] = "otra"
    diferencias = exportar.comparar_con_predicciones(campeon, filas, alteradas)
    assert len(diferencias) == 1 and "Databricks dice otra" in diferencias[0]

    assert "no hay predicción guardada" in exportar.comparar_con_predicciones(campeon, filas, guardadas.iloc[0:0])[0]
