"""Modelo de tendencia: construcción, partición temporal y evaluación.

Lo usan el notebook de entrenamiento y `scripts/evaluar_modelo.py`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from gas_price.features import UMBRAL_CAMBIO, VARIABLES, VARIABLES_NUMERICAS

SEMANAS_DE_PRUEBA = 104  # los últimos dos años se reservan para evaluar


def construir_modelo() -> Pipeline:
    """Regresión logística. Recibe las columnas de `VARIABLES`, con el combustible como texto."""
    preparacion = ColumnTransformer(
        [
            ("combustible", OneHotEncoder(handle_unknown="ignore"), ["combustible"]),
            ("numericas", StandardScaler(), VARIABLES_NUMERICAS),
        ]
    )
    clasificador = LogisticRegression(max_iter=3000, class_weight="balanced")
    return Pipeline([("preparacion", preparacion), ("clasificador", clasificador)])


def con_etiqueta(features: pd.DataFrame) -> pd.DataFrame:
    return features[features["etiqueta"].notna()].sort_values(["semana", "combustible"])


def particion_temporal(features: pd.DataFrame, semanas_de_prueba: int = SEMANAS_DE_PRUEBA):
    """Entrena con el pasado y prueba con las últimas semanas. Nunca mezcla fechas."""
    datos = con_etiqueta(features)
    semanas = sorted(datos["semana"].unique())
    corte = semanas[-semanas_de_prueba]
    entrenamiento = datos[datos["semana"] < corte]
    prueba = datos[datos["semana"] >= corte]
    return entrenamiento, prueba


def repetir_semana_pasada(features: pd.DataFrame) -> np.ndarray:
    """Regla de comparación: predice la misma dirección que el último cambio."""
    cambio = features["cambio_l1"]
    return np.select([cambio >= UMBRAL_CAMBIO, cambio <= -UMBRAL_CAMBIO], ["sube", "baja"], "se_mantiene")


def metricas(real, predicho, prefijo: str = "") -> dict:
    real = np.asarray(real)
    predicho = np.asarray(predicho)
    con_movimiento = np.isin(real, ["sube", "baja"]) & np.isin(predicho, ["sube", "baja"])
    return {
        f"{prefijo}balanced_accuracy": balanced_accuracy_score(real, predicho),
        f"{prefijo}f1_macro": f1_score(real, predicho, average="macro"),
        f"{prefijo}direccion_con_movimiento": float(np.mean(real[con_movimiento] == predicho[con_movimiento]))
        if con_movimiento.any()
        else float("nan"),
    }


def evaluar(features: pd.DataFrame, semanas_de_prueba: int = SEMANAS_DE_PRUEBA) -> tuple[Pipeline, dict]:
    """Entrena con el pasado y devuelve el modelo y las métricas del modelo y de la regla de comparación."""
    entrenamiento, prueba = particion_temporal(features, semanas_de_prueba)
    modelo = construir_modelo().fit(entrenamiento[VARIABLES], entrenamiento["etiqueta"])
    resultado = {
        **metricas(prueba["etiqueta"], modelo.predict(prueba[VARIABLES]), "modelo_"),
        **metricas(prueba["etiqueta"], repetir_semana_pasada(prueba), "regla_"),
        "filas_entrenamiento": len(entrenamiento),
        "filas_prueba": len(prueba),
        "inicio_prueba": str(prueba["semana"].min()),
    }
    return modelo, resultado


def semana_a_predecir(features: pd.DataFrame) -> pd.DataFrame:
    """Las filas de la semana más reciente: todavía no tienen etiqueta, porque la semana siguiente no termina."""
    ultima = features["semana"].max()
    return features[(features["semana"] == ultima) & features["etiqueta"].isna()]


def predecir(modelo, filas: pd.DataFrame, version_modelo: str) -> pd.DataFrame:
    """Una fila por combustible con la predicción, su probabilidad y la de cada clase.

    Es la base de `gold.predicciones`. `semana` es el martes de inicio de la semana con los datos
    usados, y `semana_objetivo` el martes de inicio de la semana cuyo cambio se predice.
    """
    probabilidades = modelo.predict_proba(filas[VARIABLES])
    clases = list(modelo.classes_)
    resultado = pd.DataFrame(
        {
            "semana": filas["semana"].to_numpy(),
            "semana_objetivo": (pd.to_datetime(filas["semana"]) + pd.Timedelta(days=7)).dt.date.to_numpy(),
            "combustible": filas["combustible"].to_numpy(),
            "prediccion": [clases[i] for i in probabilidades.argmax(axis=1)],
            "probabilidad": probabilidades.max(axis=1),
        }
    )
    for clase in ["sube", "baja", "se_mantiene"]:
        resultado[f"prob_{clase}"] = probabilidades[:, clases.index(clase)] if clase in clases else 0.0
    resultado["version_modelo"] = str(version_modelo)
    return resultado.sort_values("combustible").reset_index(drop=True)


def fila_de_metricas(resultado: dict, version_modelo: str) -> pd.DataFrame:
    """Convierte el resultado de `evaluar` en una fila de `gold.metricas_modelo`, sin la fecha de entrenamiento."""
    fila = {
        "version_modelo": str(version_modelo),
        "inicio_prueba": pd.Timestamp(resultado["inicio_prueba"]).date(),
        "filas_entrenamiento": int(resultado["filas_entrenamiento"]),
        "filas_prueba": int(resultado["filas_prueba"]),
    }
    metricas_nombres = ["balanced_accuracy", "f1_macro", "direccion_con_movimiento"]
    for metrica in metricas_nombres:
        fila[f"modelo_{metrica}"] = float(resultado[f"modelo_{metrica}"])
    for metrica in metricas_nombres:
        fila[f"linea_base_{metrica}"] = float(resultado[f"regla_{metrica}"])
    fila["supera_linea_base"] = fila["modelo_balanced_accuracy"] > fila["linea_base_balanced_accuracy"]
    return pd.DataFrame([fila])
