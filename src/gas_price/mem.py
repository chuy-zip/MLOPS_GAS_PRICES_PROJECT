"""Lectura, limpieza y validación del Excel de precios del MEM.

Lo usan los notebooks de Databricks y los tests del CI, así las reglas viven en un solo lugar.

El Excel no tiene un formato de tabla estándar:
1. Arriba hay títulos. El encabezado está en la fila cuya primera celda dice "FECHA".
2. Debajo del encabezado hay una fila de unidades.
3. Al final hay notas de fuente.
4. Un precio en 0 significa que ese día no se publicó precio. Pasa sobre todo de 2017 a 2019.
5. Algunas fechas vienen repetidas en filas idénticas.
"""

from __future__ import annotations

import datetime as dt
import unicodedata

import numpy as np
import pandas as pd

HOJA = "PUBLICACIÓN WEB"

# Encabezado del Excel, ya normalizado, y el nombre que usamos en el proyecto.
COLUMNAS = {
    "fecha": "fecha",
    "tipo de cambio": "tipo_cambio",
    "gasolina superior": "super",
    "gasolina regular": "regular",
    "aceite combustible diesel": "diesel",
}
COMBUSTIBLES = ["super", "regular", "diesel"]

PRECIO_MINIMO = 10.0
PRECIO_MAXIMO = 80.0

# Tomado de la nota al pie del Excel.
SUBSIDIO_INICIO = dt.date(2026, 4, 28)
SUBSIDIO_FIN = dt.date(2026, 7, 5)
EXENCION_INICIO = dt.date(2026, 10, 1)


def _normalizar(texto) -> str:
    """Quita tildes, espacios de más y mayúsculas para comparar encabezados."""
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def _a_texto(valor) -> str | None:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return None
    if isinstance(valor, (dt.datetime, pd.Timestamp)):
        return valor.strftime("%Y-%m-%d")
    return str(valor)


def leer_hoja(fuente) -> pd.DataFrame:
    """Lee la hoja tal cual, sin encabezado. `fuente` puede ser una ruta, una URL o bytes."""
    return pd.read_excel(fuente, sheet_name=HOJA, header=None, dtype=object, engine="openpyxl")


def extraer_crudo(hoja: pd.DataFrame) -> pd.DataFrame:
    """Recorta la hoja a las filas de datos y deja todo como texto. Es lo que guarda bronce."""
    primera = hoja.iloc[:, 0].map(_normalizar)
    filas_encabezado = primera.index[primera == "fecha"]
    if len(filas_encabezado) == 0:
        raise ValueError("No se encontró la fila de encabezado con 'FECHA'")
    fila_encabezado = filas_encabezado[0]

    encabezado = hoja.iloc[fila_encabezado].map(_normalizar)
    posiciones = {}
    for nombre_excel, nombre in COLUMNAS.items():
        coincidencias = encabezado.index[encabezado == nombre_excel]
        if len(coincidencias) == 0:
            raise ValueError(f"Falta la columna obligatoria '{nombre_excel}'")
        posiciones[nombre] = coincidencias[0]

    cuerpo = hoja.iloc[fila_encabezado + 1 :]
    es_dato = cuerpo.iloc[:, posiciones["fecha"]].map(
        lambda v: isinstance(v, (dt.datetime, dt.date, pd.Timestamp))
    )
    cuerpo = cuerpo[es_dato]

    crudo = pd.DataFrame({"fila_excel": cuerpo.index + 1})
    for nombre, posicion in posiciones.items():
        crudo[f"{nombre}_texto"] = cuerpo.iloc[:, posicion].map(_a_texto).to_numpy()
    return crudo.reset_index(drop=True)


def _a_numero(texto) -> float:
    if texto is None:
        return np.nan
    limpio = str(texto).replace("\xa0", " ").strip()
    return float(limpio) if limpio else np.nan


def limpiar(crudo: pd.DataFrame) -> pd.DataFrame:
    """Convierte los textos de bronce a tipos, una fila por fecha. Es la base de plata.

    Reglas:
    1. Un precio en 0 se vuelve nulo, porque significa que ese día no hubo publicación.
    2. Las fechas repetidas con valores idénticos se dejan una sola vez.
    3. Las fechas repetidas con valores distintos detienen el proceso.
    """
    limpio = pd.DataFrame(
        {
            "fecha": pd.to_datetime(crudo["fecha_texto"]).dt.date,
            "tipo_cambio": crudo["tipo_cambio_texto"].map(_a_numero),
        }
    )
    for combustible in COMBUSTIBLES:
        limpio[combustible] = crudo[f"{combustible}_texto"].map(_a_numero).replace(0.0, np.nan)

    limpio = limpio.drop_duplicates()
    conflictos = limpio["fecha"][limpio["fecha"].duplicated()]
    if len(conflictos) > 0:
        fechas = ", ".join(str(f) for f in sorted(set(conflictos)))
        raise ValueError(f"Fechas repetidas con valores distintos: {fechas}")

    return limpio.sort_values("fecha").reset_index(drop=True)


def regimen_fiscal(fecha: dt.date) -> str:
    if SUBSIDIO_INICIO <= fecha <= SUBSIDIO_FIN:
        return "subsidio"
    if fecha >= EXENCION_INICIO:
        return "exento"
    return "normal"


def a_formato_largo(limpio: pd.DataFrame) -> pd.DataFrame:
    """Una fila por fecha y combustible, sin los días sin precio. Es `silver.precios_oficiales`."""
    largo = limpio.melt(
        id_vars=["fecha", "tipo_cambio"],
        value_vars=COMBUSTIBLES,
        var_name="combustible",
        value_name="precio_gtq_galon",
    ).dropna(subset=["precio_gtq_galon"])
    largo["regimen_fiscal"] = largo["fecha"].map(regimen_fiscal)
    columnas = ["fecha", "combustible", "precio_gtq_galon", "tipo_cambio", "regimen_fiscal"]
    return largo[columnas].sort_values(["fecha", "combustible"]).reset_index(drop=True)


def precios_fuera_de_rango(limpio: pd.DataFrame) -> pd.DataFrame:
    precios = limpio.melt(id_vars="fecha", value_vars=COMBUSTIBLES).dropna()
    fuera = (precios["value"] < PRECIO_MINIMO) | (precios["value"] > PRECIO_MAXIMO)
    return precios[fuera]


def comparar_versiones(base: pd.DataFrame, nuevo: pd.DataFrame) -> list[str]:
    """Reglas de "no empeorar" entre dos versiones limpias del Excel.

    Devuelve una lista de problemas. Vacía significa que la versión nueva se puede usar.
    """
    problemas = []

    perdidas = sorted(set(base["fecha"]) - set(nuevo["fecha"]))
    if perdidas:
        problemas.append(f"Se perdieron {len(perdidas)} fechas, por ejemplo {perdidas[:5]}")

    unidas = base.merge(nuevo, on="fecha", suffixes=("_base", "_nuevo"))
    for columna in ["tipo_cambio", *COMBUSTIBLES]:
        antes = unidas[f"{columna}_base"]
        ahora = unidas[f"{columna}_nuevo"]

        nulos_nuevos = unidas["fecha"][antes.notna() & ahora.isna()]
        if len(nulos_nuevos) > 0:
            problemas.append(
                f"{columna}: {len(nulos_nuevos)} fechas quedaron sin dato, por ejemplo {list(nulos_nuevos[:5])}"
            )

        cambiados = unidas["fecha"][antes.notna() & ahora.notna() & ~np.isclose(antes, ahora)]
        if len(cambiados) > 0:
            problemas.append(
                f"{columna}: cambió el valor de {len(cambiados)} fechas existentes, por ejemplo {list(cambiados[:5])}"
            )

    fuera = precios_fuera_de_rango(nuevo)
    if len(fuera) > 0:
        problemas.append(
            f"{len(fuera)} precios fuera del rango de Q{PRECIO_MINIMO:.0f} a Q{PRECIO_MAXIMO:.0f}"
        )

    return problemas
