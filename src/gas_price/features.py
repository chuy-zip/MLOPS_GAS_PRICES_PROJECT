"""Tablas de oro: serie diaria, variables semanales del modelo y referencia vigente.

Trabaja con DataFrames de pandas con la forma de las tablas de plata:
1. `precios_oficiales`: fecha, combustible, precio_gtq_galon, tipo_cambio, regimen_fiscal.
2. `precios_internacionales`: fecha, serie, precio_usd_galon.

Lo usan el notebook de oro, el de entrenamiento y `scripts/evaluar_modelo.py`.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from gas_price import eia, mem

UMBRAL_CAMBIO = 0.10  # quetzales por galón. Un cambio menor cuenta como "igual"
DIA_DE_CAMBIO = "W-MON"  # semanas que terminan en lunes, el día en que cambia casi siempre el precio
MARGEN_NORMAL = 1.00  # diferencia normal entre estaciones, según el análisis de negocio

# Combustible del MEM y serie de la EIA que sigue.
SERIE_INTERNACIONAL = {
    combustible: serie for serie, config in eia.SERIES.items() for combustible in config["combustibles"]
}

VARIABLES_NUMERICAS = [
    "cambio_l1",
    "cambio_l2",
    "cambio_l3",
    "cambio_l4",
    "tendencia_4",
    "tendencia_8",
    "tipo_cambio_cambio",
    "mes",
    "otro_super_l1",
    "otro_regular_l1",
    "otro_diesel_l1",
    "intl_cambio_1",
    "intl_cambio_2",
    "intl_cambio_3",
    "brecha_vs_8",
]
VARIABLES = ["combustible", *VARIABLES_NUMERICAS]


def etiquetar(cambio: pd.Series) -> pd.Series:
    """Convierte un cambio de precio en "sube", "baja" o "igual". Un cambio desconocido queda nulo."""
    etiqueta = pd.Series(
        np.select([cambio >= UMBRAL_CAMBIO, cambio <= -UMBRAL_CAMBIO], ["sube", "baja"], "igual"),
        index=cambio.index,
        dtype=object,
    )
    etiqueta[cambio.isna()] = None
    return etiqueta


def precios_diarios(precios_oficiales: pd.DataFrame) -> pd.DataFrame:
    """Un día por fila y combustible, sin huecos. Es `gold.precios_diarios` sin la columna de fotos.

    Un día sin publicación toma el último precio conocido y queda marcado con `es_imputado`.
    """
    partes = []
    for combustible, grupo in precios_oficiales.groupby("combustible"):
        serie = grupo.set_index(pd.to_datetime(grupo["fecha"])).sort_index()
        calendario = pd.date_range(serie.index.min(), serie.index.max(), freq="D")
        completa = serie[["precio_gtq_galon", "tipo_cambio"]].reindex(calendario)
        completa["es_imputado"] = completa["precio_gtq_galon"].isna()
        completa = completa.ffill()
        completa["fecha"] = completa.index.date
        completa["combustible"] = combustible
        completa["regimen_fiscal"] = completa["fecha"].map(mem.regimen_fiscal)
        partes.append(completa)

    columnas = ["fecha", "combustible", "precio_oficial", "es_imputado", "tipo_cambio", "regimen_fiscal"]
    diarios = pd.concat(partes, ignore_index=True).rename(columns={"precio_gtq_galon": "precio_oficial"})
    return diarios[columnas].sort_values(["fecha", "combustible"]).reset_index(drop=True)


def _internacional_antes_del_lunes(precios_internacionales: pd.DataFrame, lunes: pd.DatetimeIndex) -> pd.DataFrame:
    """Promedio de los 7 días anteriores a cada lunes, sin incluirlo. Solo usa lo que ya se sabía ese día."""
    ancho = precios_internacionales.pivot(index="fecha", columns="serie", values="precio_usd_galon")
    ancho.index = pd.to_datetime(ancho.index)
    diario = ancho.asfreq("D").ffill()
    return diario.rolling(7, min_periods=3).mean().shift(1).reindex(lunes)


def features_semanales(diarios: pd.DataFrame, precios_internacionales: pd.DataFrame) -> pd.DataFrame:
    """Una fila por lunes y combustible con las variables y la etiqueta. Es `gold.features_semanales`.

    La fila del lunes t describe lo que se sabía ese lunes. La etiqueta es la dirección
    del cambio entre el lunes t y el lunes siguiente. La última semana no tiene etiqueta.
    """
    ancho = diarios.pivot(index="fecha", columns="combustible", values="precio_oficial")
    ancho.index = pd.to_datetime(ancho.index)
    tipo_cambio = diarios.groupby("fecha")["tipo_cambio"].first()
    tipo_cambio.index = pd.to_datetime(tipo_cambio.index)

    # Si el último dato no es lunes, resample crea una semana que todavía no termina,
    # con el precio de un día que no es lunes. Se descarta para no inventar un cambio.
    ultimo_dia = ancho.index.max()
    semanal = ancho.resample(DIA_DE_CAMBIO).last()
    semanal = semanal[semanal.index <= ultimo_dia]
    tc_semanal = tipo_cambio.resample(DIA_DE_CAMBIO).last()
    tc_semanal = tc_semanal[tc_semanal.index <= ultimo_dia]
    internacional = _internacional_antes_del_lunes(precios_internacionales, semanal.index)

    partes = []
    for combustible in mem.COMBUSTIBLES:
        precio = semanal[combustible]
        cambio = precio.diff()
        f = pd.DataFrame(index=semanal.index)
        f["combustible"] = combustible
        f["precio"] = precio
        for k in range(1, 5):
            f[f"cambio_l{k}"] = cambio.shift(k - 1)
        f["tendencia_4"] = precio - precio.rolling(4).mean()
        f["tendencia_8"] = precio - precio.rolling(8).mean()
        f["tipo_cambio_cambio"] = tc_semanal.diff()
        f["mes"] = semanal.index.month
        for otro in mem.COMBUSTIBLES:
            f[f"otro_{otro}_l1"] = semanal[otro].diff()

        intl_quetzales = internacional[SERIE_INTERNACIONAL[combustible]] * tc_semanal
        f["intl_cambio_1"] = intl_quetzales.diff()
        f["intl_cambio_2"] = intl_quetzales.diff().shift(1)
        f["intl_cambio_3"] = intl_quetzales.diff().shift(2)
        brecha = precio - intl_quetzales
        f["brecha_vs_8"] = brecha - brecha.rolling(8).mean()

        f["cambio_siguiente"] = cambio.shift(-1)
        f["etiqueta"] = etiquetar(f["cambio_siguiente"])
        partes.append(f)

    tabla = pd.concat(partes)
    tabla = tabla.dropna(subset=VARIABLES_NUMERICAS)
    tabla.insert(0, "semana", tabla.index.date)
    return tabla.sort_values(["semana", "combustible"]).reset_index(drop=True)


def referencia_actual(diarios: pd.DataFrame) -> pd.DataFrame:
    """El último precio oficial por combustible y el rango de "buen precio". Es `gold.referencia_actual`.

    1. Igual o debajo de `precio_referencia`: buen precio.
    2. Hasta `limite_normal`: precio normal.
    3. Arriba de `limite_normal`: caro.
    """
    ultimos = diarios.sort_values("fecha").groupby("combustible").tail(1).copy()
    ultimos["limite_normal"] = ultimos["precio_oficial"] + MARGEN_NORMAL
    ultima_fecha = ultimos["fecha"].max()
    dias_al_lunes = (7 - ultima_fecha.weekday()) % 7 or 7
    ultimos["proximo_cambio"] = ultima_fecha + dt.timedelta(days=dias_al_lunes)
    columnas = ["combustible", "fecha", "precio_oficial", "limite_normal", "tipo_cambio", "regimen_fiscal", "proximo_cambio"]
    return (
        ultimos[columnas]
        .rename(columns={"fecha": "fecha_referencia", "precio_oficial": "precio_referencia"})
        .sort_values("combustible")
        .reset_index(drop=True)
    )
