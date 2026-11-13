"""Lectura y validación de los precios internacionales de la EIA.

La EIA, la agencia de información energética de EE. UU., publica precios spot diarios
en dólares por galón. Usamos dos series de la Costa del Golfo, el mercado de referencia
para la importación de combustibles a Centroamérica.

Cada archivo es un .xls con una hoja "Data 1": dos filas de títulos, el encabezado
"Date" y una columna de precios. Los días sin mercado, como fines de semana y feriados, no vienen.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HOJA = "Data 1"

# Nombre en el proyecto: archivo en data/eia, serie de la EIA y combustibles del MEM que sigue.
SERIES = {
    "gasolina": {
        "archivo": "gasolina_costa_golfo_diario.xls",
        "serie_eia": "EER_EPMRU_PF4_RGC_DPG",
        "combustibles": ["super", "regular"],
    },
    "diesel": {
        "archivo": "diesel_costa_golfo_diario.xls",
        "serie_eia": "EER_EPD2DXL0_PF4_RGC_DPG",
        "combustibles": ["diesel"],
    },
}

PRECIO_MINIMO_USD = 0.10
PRECIO_MAXIMO_USD = 10.0


def leer(fuente) -> pd.DataFrame:
    """Devuelve una fila por día de mercado con `fecha` y `precio_usd_galon`. `fuente` puede ser ruta, URL o bytes."""
    hoja = pd.read_excel(fuente, sheet_name=HOJA, skiprows=2, engine="calamine")
    if hoja.columns[0] != "Date" or "Dollars per Gallon" not in str(hoja.columns[1]):
        raise ValueError(f"Formato inesperado en el encabezado: {list(hoja.columns[:2])}")

    datos = hoja.iloc[:, :2].copy()
    datos.columns = ["fecha", "precio_usd_galon"]
    datos = datos.dropna(subset=["fecha"])
    datos["fecha"] = pd.to_datetime(datos["fecha"]).dt.date
    datos["precio_usd_galon"] = pd.to_numeric(datos["precio_usd_galon"], errors="coerce")

    datos = datos.drop_duplicates()
    if datos["fecha"].duplicated().any():
        raise ValueError("Hay fechas repetidas con precios distintos")
    return datos.sort_values("fecha").reset_index(drop=True)


def precios_fuera_de_rango(datos: pd.DataFrame) -> pd.DataFrame:
    precio = datos["precio_usd_galon"]
    return datos[(precio < PRECIO_MINIMO_USD) | (precio > PRECIO_MAXIMO_USD)]


def comparar_versiones(base: pd.DataFrame, nuevo: pd.DataFrame) -> list[str]:
    """Reglas de "no empeorar" entre dos versiones de una serie. Vacía significa que se puede usar."""
    problemas = []

    perdidas = sorted(set(base["fecha"]) - set(nuevo["fecha"]))
    if perdidas:
        problemas.append(f"Se perdieron {len(perdidas)} fechas, por ejemplo {perdidas[:5]}")

    unidas = base.merge(nuevo, on="fecha", suffixes=("_base", "_nuevo"))
    antes, ahora = unidas["precio_usd_galon_base"], unidas["precio_usd_galon_nuevo"]

    nulos = unidas["fecha"][antes.notna() & ahora.isna()]
    if len(nulos) > 0:
        problemas.append(f"{len(nulos)} fechas quedaron sin dato, por ejemplo {list(nulos[:5])}")

    cambiados = unidas["fecha"][antes.notna() & ahora.notna() & ~np.isclose(antes, ahora)]
    if len(cambiados) > 0:
        problemas.append(f"Cambió el precio de {len(cambiados)} fechas existentes, por ejemplo {list(cambiados[:5])}")

    fuera = precios_fuera_de_rango(nuevo)
    if len(fuera) > 0:
        problemas.append(
            f"{len(fuera)} precios fuera del rango de {PRECIO_MINIMO_USD} a {PRECIO_MAXIMO_USD} dólares por galón"
        )

    return problemas
