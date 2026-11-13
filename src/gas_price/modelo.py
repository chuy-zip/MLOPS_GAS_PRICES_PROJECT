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
    return np.select([cambio >= UMBRAL_CAMBIO, cambio <= -UMBRAL_CAMBIO], ["sube", "baja"], "igual")


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
