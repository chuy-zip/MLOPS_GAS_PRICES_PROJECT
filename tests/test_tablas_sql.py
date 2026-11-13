"""Revisa que databricks/sql/tablas.sql coincida con las columnas que produce el código.

Si alguien cambia una tabla en src/ y no actualiza tablas.sql, la tarea de Databricks fallaría.
Este test lo detecta antes, en el pull request.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

from gas_price import eia, features, mem

RAIZ = Path(__file__).parents[1]
TABLAS_SQL = RAIZ / "databricks" / "sql" / "tablas.sql"


def sentencias():
    """Separa el archivo igual que el notebook 05_crear_tablas."""
    texto = TABLAS_SQL.read_text(encoding="utf-8")
    sin_comentarios = "\n".join(l for l in texto.splitlines() if not l.strip().startswith("--"))
    return [s.strip() for s in sin_comentarios.split(";") if s.strip()]


def columnas_por_tabla() -> dict[str, list[str]]:
    tablas = {}
    for sentencia in sentencias():
        nombre = re.search(r"EXISTS\s+\S+\.(\w+)\s*\(", sentencia).group(1)
        cuerpo = sentencia.split("(", 1)[1].rsplit(")", 1)[0]
        tablas[nombre] = [linea.strip().split()[0] for linea in cuerpo.splitlines() if linea.strip()]
    return tablas


@pytest.fixture(scope="module")
def tablas():
    return columnas_por_tabla()


@pytest.fixture(scope="module")
def oro():
    oficiales = mem.a_formato_largo(mem.limpiar(mem.extraer_crudo(mem.leer_hoja(RAIZ / "data/mem/precios_promedio_nacionales_diarios.xlsx"))))
    internacionales = pd.concat(
        [eia.leer(RAIZ / "data/eia" / c["archivo"]).assign(serie=s) for s, c in eia.SERIES.items()]
    )
    diarios = features.precios_diarios(oficiales)
    diarios["n_fotos"] = 0
    return {
        "precios_oficiales": oficiales,
        "precios_diarios": diarios,
        "features_semanales": features.features_semanales(diarios, internacionales),
        "referencia_actual": features.referencia_actual(diarios),
    }


def test_cada_sentencia_crea_una_tabla_sin_reemplazar_nada():
    for sentencia in sentencias():
        assert sentencia.startswith("CREATE TABLE IF NOT EXISTS"), sentencia[:60]


def test_estan_las_siete_tablas(tablas):
    assert set(tablas) == {
        "mem_precios", "eia_precios", "precios_oficiales", "precios_internacionales",
        "precios_diarios", "features_semanales", "referencia_actual",
    }


def test_bronce_coincide_con_los_lectores(tablas):
    control = ["_archivo_origen", "_url_origen", "_hash_archivo", "_ingestado_en"]
    crudo_mem = mem.extraer_crudo(mem.leer_hoja(RAIZ / "data/mem/precios_promedio_nacionales_diarios.xlsx"))
    assert tablas["mem_precios"] == [*crudo_mem.columns, *control]
    crudo_eia = eia.extraer_crudo(RAIZ / "data/eia" / eia.SERIES["diesel"]["archivo"])
    assert tablas["eia_precios"] == ["serie", *crudo_eia.columns, *control]


@pytest.mark.parametrize("tabla", ["precios_oficiales", "precios_diarios", "features_semanales", "referencia_actual"])
def test_plata_y_oro_coinciden_con_el_codigo(tablas, oro, tabla):
    esperadas = list(oro[tabla].columns)
    if tabla == "precios_oficiales":
        esperadas.append("_archivo_origen")
    assert tablas[tabla] == esperadas


def test_precios_internacionales_coincide_con_el_lector(tablas):
    datos = eia.leer(RAIZ / "data/eia" / eia.SERIES["diesel"]["archivo"])
    assert tablas["precios_internacionales"] == [datos.columns[0], "serie", datos.columns[1], "_archivo_origen"]
