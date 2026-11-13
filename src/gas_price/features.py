"""Tablas de oro: serie diaria, precio y variación semanal, variables del modelo y referencia vigente.

Trabaja con DataFrames de pandas con la forma de las tablas de plata:
1. `precios_oficiales`: fecha, combustible, precio_q_galon, tipo_cambio, regimen_fiscal.
2. `precios_internacionales`: fecha, serie, precio_usd_galon.
3. `precios` de las fotos: fecha, combustible, precio_q_galon y las demás columnas de `silver.precios`.

Las semanas van de martes a lunes, como los precios de referencia del MEM. Cada semana se
identifica por su martes de inicio, igual que en el ejemplo de la API del enunciado.

Lo usan el notebook de oro, el de entrenamiento y `scripts/evaluar_modelo.py`.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from gas_price import eia, mem

UMBRAL_CAMBIO = 0.10  # quetzales por galón. Un cambio menor cuenta como "se_mantiene"
DIA_DE_CAMBIO = "W-MON"  # agrupa de martes a lunes. pandas etiqueta cada semana con su lunes final
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
    """Convierte un cambio de precio en "sube", "baja" o "se_mantiene". Un cambio desconocido queda nulo."""
    etiqueta = pd.Series(
        np.select([cambio >= UMBRAL_CAMBIO, cambio <= -UMBRAL_CAMBIO], ["sube", "baja"], "se_mantiene"),
        index=cambio.index,
        dtype=object,
    )
    etiqueta[cambio.isna()] = None
    return etiqueta


def inicio_de_semana(fechas) -> pd.Series:
    """Martes en que empieza la semana de cada fecha. Un lunes pertenece a la semana del martes anterior."""
    fechas = pd.to_datetime(pd.Series(fechas))
    dias_desde_martes = (fechas.dt.day_of_week - 1) % 7
    return (fechas - pd.to_timedelta(dias_desde_martes, unit="D")).dt.date


def precios_diarios(precios_oficiales: pd.DataFrame) -> pd.DataFrame:
    """Un día por fila y combustible, sin huecos. Es `gold.precios_diarios` sin la columna de fotos.

    Un día sin publicación toma el último precio conocido y queda marcado con `es_imputado`.
    """
    precios_oficiales = precios_oficiales.assign(
        precio_q_galon=pd.to_numeric(precios_oficiales["precio_q_galon"]).astype(float),
        tipo_cambio=pd.to_numeric(precios_oficiales["tipo_cambio"]).astype(float),
    )
    partes = []
    for combustible, grupo in precios_oficiales.groupby("combustible"):
        serie = grupo.set_index(pd.to_datetime(grupo["fecha"])).sort_index()
        calendario = pd.date_range(serie.index.min(), serie.index.max(), freq="D")
        completa = serie[["precio_q_galon", "tipo_cambio"]].reindex(calendario)
        completa["es_imputado"] = completa["precio_q_galon"].isna()
        completa = completa.ffill()
        completa["fecha"] = completa.index.date
        completa["combustible"] = combustible
        completa["regimen_fiscal"] = completa["fecha"].map(mem.regimen_fiscal)
        partes.append(completa)

    columnas = ["fecha", "combustible", "precio_oficial", "es_imputado", "tipo_cambio", "regimen_fiscal"]
    diarios = pd.concat(partes, ignore_index=True).rename(columns={"precio_q_galon": "precio_oficial"})
    return diarios[columnas].sort_values(["fecha", "combustible"]).reset_index(drop=True)


def _internacional_antes_del_lunes(precios_internacionales: pd.DataFrame, lunes: pd.DatetimeIndex) -> pd.DataFrame:
    """Promedio de los 7 días anteriores a cada lunes, sin incluirlo. Solo usa lo que ya se sabía ese día."""
    ancho = precios_internacionales.pivot(index="fecha", columns="serie", values="precio_usd_galon")
    ancho.index = pd.to_datetime(ancho.index)
    diario = ancho.asfreq("D").ffill()
    return diario.rolling(7, min_periods=3).mean().shift(1).reindex(lunes)


def features_modelo(diarios: pd.DataFrame, precios_internacionales: pd.DataFrame) -> pd.DataFrame:
    """Una fila por semana y combustible con las variables y la etiqueta. Es `gold.features_modelo`.

    La fila de una semana describe lo que se sabía al cerrar esa semana, el lunes. La etiqueta es
    la dirección del cambio de precio de la semana siguiente. La semana actual no tiene etiqueta.
    `semana` es el martes de inicio.
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
    tabla.insert(0, "semana", (tabla.index - pd.Timedelta(days=6)).date)
    return tabla.sort_values(["semana", "combustible"]).reset_index(drop=True)


def precio_semanal(diarios: pd.DataFrame, precios_fotos: pd.DataFrame | None = None) -> pd.DataFrame:
    """Precio promedio, mínimo y máximo por semana, combustible y fuente. Es `gold.precio_semanal`.

    1. Fuente `mem`: el precio oficial vigente de cada día de la semana.
    2. Fuente `fotos`: los precios extraídos de las fotos de esa semana, si hay.
    """
    partes = []
    mem_semana = diarios.assign(semana=inicio_de_semana(diarios["fecha"]).to_numpy(), fuente="mem")
    partes.append(mem_semana.rename(columns={"precio_oficial": "precio"})[["semana", "combustible", "fuente", "precio"]])
    if precios_fotos is not None and len(precios_fotos) > 0:
        fotos_semana = precios_fotos.assign(
            semana=inicio_de_semana(precios_fotos["fecha"]).to_numpy(),
            fuente="fotos",
            precio=pd.to_numeric(precios_fotos["precio_q_galon"]).astype(float),
        )
        partes.append(fotos_semana[["semana", "combustible", "fuente", "precio"]])

    todos = pd.concat(partes, ignore_index=True)
    agrupado = (
        todos.groupby(["semana", "combustible", "fuente"])["precio"]
        .agg(precio_promedio="mean", precio_minimo="min", precio_maximo="max", n_observaciones="count")
        .reset_index()
    )
    agrupado["n_observaciones"] = agrupado["n_observaciones"].astype("int32")
    return agrupado.sort_values(["semana", "combustible", "fuente"]).reset_index(drop=True)


def variacion_semanal(semanal: pd.DataFrame) -> pd.DataFrame:
    """Variación del precio promedio contra la semana anterior. Es `gold.variacion_semanal`.

    Solo compara semanas consecutivas de la misma fuente y combustible. Si la semana anterior
    no tiene datos, como pasa a menudo con las fotos, la variación queda nula.
    """
    partes = []
    for (_, _), grupo in semanal.groupby(["combustible", "fuente"]):
        grupo = grupo.sort_values("semana").copy()
        anterior = grupo["precio_promedio"].shift(1)
        semana_anterior = pd.to_datetime(grupo["semana"]).shift(1)
        consecutiva = (pd.to_datetime(grupo["semana"]) - semana_anterior) == pd.Timedelta(days=7)
        grupo["precio_anterior"] = anterior.where(consecutiva)
        grupo["variacion_q"] = grupo["precio_promedio"] - grupo["precio_anterior"]
        grupo["variacion_pct"] = grupo["variacion_q"] / grupo["precio_anterior"] * 100
        grupo["direccion"] = etiquetar(grupo["variacion_q"])
        partes.append(grupo)

    columnas = ["semana", "combustible", "fuente", "precio_promedio", "precio_anterior", "variacion_q", "variacion_pct", "direccion"]
    return pd.concat(partes)[columnas].sort_values(["semana", "combustible", "fuente"]).reset_index(drop=True)


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
