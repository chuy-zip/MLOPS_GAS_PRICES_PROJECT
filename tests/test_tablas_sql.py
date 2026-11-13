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
    semanal = features.precio_semanal(diarios)
    return {
        "precios_oficiales": oficiales,
        "precios_diarios": diarios,
        "features_modelo": features.features_modelo(diarios, internacionales),
        "referencia_actual": features.referencia_actual(diarios),
        "precio_semanal": semanal,
        "variacion_semanal": features.variacion_semanal(semanal),
    }


def test_cada_sentencia_crea_una_tabla_sin_reemplazar_nada():
    for sentencia in sentencias():
        assert sentencia.startswith("CREATE TABLE IF NOT EXISTS"), sentencia[:60]


def test_estan_todas_las_tablas(tablas):
    assert set(tablas) == {
        "fotos_precios", "mem_precios", "eia_precios",
        "precios", "precios_rejected", "precios_oficiales", "precios_internacionales",
        "precios_diarios", "precio_semanal", "variacion_semanal", "features_modelo",
        "referencia_actual", "predicciones", "metricas_modelo",
    }


def test_tablas_de_fotos_tienen_las_columnas_del_enunciado(tablas):
    auditoria = ["_ingestion_timestamp", "_source_file"]
    assert tablas["fotos_precios"] == ["path", "modificationTime", "length", "content", *auditoria]
    minimas = ["fecha", "combustible", "precio_q_galon", "modalidad", "ubicacion", "foto_origen"]
    assert tablas["precios"] == minimas
    assert tablas["precios_rejected"] == [*minimas, "motivo"]


def test_bronce_usa_las_columnas_de_auditoria_del_enunciado(tablas):
    for tabla in ["fotos_precios", "mem_precios", "eia_precios"]:
        assert {"_ingestion_timestamp", "_source_file"} <= set(tablas[tabla]), tabla


def test_cada_columna_de_oro_tiene_comentario():
    for sentencia in sentencias():
        if "${esquema_gold}" not in sentencia:
            continue
        cuerpo = sentencia.split("(", 1)[1].rsplit(")", 1)[0]
        for linea in cuerpo.splitlines():
            if linea.strip():
                assert "COMMENT" in linea, f"Columna de oro sin comentario: {linea.strip()}"
        assert sentencia.rsplit(")", 1)[1].strip().startswith("COMMENT"), "Tabla de oro sin comentario"


def test_predicciones_coincide_con_el_codigo(tablas, oro):
    from gas_price import modelo
    semanales = oro["features_modelo"]
    entrenado = modelo.construir_modelo().fit(
        modelo.con_etiqueta(semanales)[features.VARIABLES], modelo.con_etiqueta(semanales)["etiqueta"]
    )
    resultado = modelo.predecir(entrenado, modelo.semana_a_predecir(semanales), version_modelo="1")
    assert tablas["predicciones"] == [*resultado.columns, "predicho_en", "direccion_real", "acierto"]


def test_metricas_modelo_coincide_con_el_codigo(tablas):
    from gas_price import modelo
    resultado = {k: 0.5 for k in [
        "modelo_balanced_accuracy", "modelo_f1_macro", "modelo_direccion_con_movimiento",
        "regla_balanced_accuracy", "regla_f1_macro", "regla_direccion_con_movimiento",
    ]}
    resultado.update(filas_entrenamiento=10, filas_prueba=5, inicio_prueba="2024-11-11")
    fila = modelo.fila_de_metricas(resultado, version_modelo="1")
    esperadas = list(fila.columns)
    esperadas.insert(1, "entrenado_en")
    assert tablas["metricas_modelo"] == esperadas


def test_bronce_coincide_con_los_lectores(tablas):
    control = ["_source_file", "_source_url", "_file_hash", "_ingestion_timestamp"]
    crudo_mem = mem.extraer_crudo(mem.leer_hoja(RAIZ / "data/mem/precios_promedio_nacionales_diarios.xlsx"))
    assert tablas["mem_precios"] == [*crudo_mem.columns, *control]
    crudo_eia = eia.extraer_crudo(RAIZ / "data/eia" / eia.SERIES["diesel"]["archivo"])
    assert tablas["eia_precios"] == ["serie", *crudo_eia.columns, *control]


@pytest.mark.parametrize("tabla", [
    "precios_oficiales", "precios_diarios", "features_modelo", "referencia_actual", "precio_semanal", "variacion_semanal",
])
def test_plata_y_oro_coinciden_con_el_codigo(tablas, oro, tabla):
    esperadas = list(oro[tabla].columns)
    if tabla == "precios_oficiales":
        esperadas.append("_source_file")
    assert tablas[tabla] == esperadas


def test_precios_internacionales_coincide_con_el_lector(tablas):
    datos = eia.leer(RAIZ / "data/eia" / eia.SERIES["diesel"]["archivo"])
    assert tablas["precios_internacionales"] == [datos.columns[0], "serie", datos.columns[1], "_source_file"]
