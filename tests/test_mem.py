import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gas_price import mem

EXCEL = Path(__file__).parents[1] / "data" / "mem" / "precios_promedio_nacionales_diarios.xlsx"


def hoja_de_prueba(filas):
    """Arma una hoja con la misma forma que el Excel del MEM: títulos, encabezado, unidades y notas."""
    encabezado = ["FECHA", "Tipo de Cambio", "Gasolina Superior", "Gasolina Regular", "Aceite Combustible Diésel"]
    unidades = ["Unidades:", "GTQ/USD", "GTQ/GALON", "GTQ/GALON", "GTQ/GALON"]
    vacia = [None] * 5
    titulo = ["DIRECCIÓN GENERAL DE HIDROCARBUROS", None, None, None, None]
    nota = ["Fuente: MEM", None, None, None, None]
    return pd.DataFrame([titulo, vacia, encabezado, unidades, *filas, nota], dtype=object)


def fila(fecha, tc=7.7, superior=30.0, regular=29.0, diesel=28.0):
    return [dt.datetime.fromisoformat(fecha), tc, superior, regular, diesel]


@pytest.fixture(scope="module")
def crudo_real():
    return mem.extraer_crudo(mem.leer_hoja(EXCEL))


def test_crudo_descarta_titulos_unidades_y_notas():
    crudo = mem.extraer_crudo(hoja_de_prueba([fila("2026-01-05"), fila("2026-01-06")]))
    assert list(crudo["fecha_texto"]) == ["2026-01-05", "2026-01-06"]
    assert list(crudo["fila_excel"]) == [5, 6]


def test_falta_columna_obligatoria():
    hoja = hoja_de_prueba([fila("2026-01-05")])
    hoja.iloc[2, 3] = "Otra cosa"
    with pytest.raises(ValueError, match="gasolina regular"):
        mem.extraer_crudo(hoja)


def test_precio_cero_es_nulo_y_texto_con_espacios_se_lee():
    hoja = hoja_de_prueba([fila("2026-01-05", tc="\xa07.70907\xa0", superior=0, regular=0, diesel=0)])
    limpio = mem.limpiar(mem.extraer_crudo(hoja))
    assert limpio.loc[0, "tipo_cambio"] == pytest.approx(7.70907)
    assert limpio[mem.COMBUSTIBLES].isna().all(axis=None)


def test_duplicados_identicos_quedan_una_vez():
    hoja = hoja_de_prueba([fila("2026-01-05"), fila("2026-01-05"), fila("2026-01-06")])
    limpio = mem.limpiar(mem.extraer_crudo(hoja))
    assert len(limpio) == 2


def test_duplicados_con_valores_distintos_fallan():
    hoja = hoja_de_prueba([fila("2026-01-05"), fila("2026-01-05", superior=31.0)])
    with pytest.raises(ValueError, match="2026-01-05"):
        mem.limpiar(mem.extraer_crudo(hoja))


def test_formato_largo_omite_dias_sin_precio_y_marca_regimen():
    hoja = hoja_de_prueba([fila("2026-05-01"), fila("2026-05-02", superior=0, regular=0, diesel=0), fila("2026-10-05")])
    largo = mem.a_formato_largo(mem.limpiar(mem.extraer_crudo(hoja)))
    assert len(largo) == 6
    assert set(largo.loc[largo["fecha"] == dt.date(2026, 5, 1), "regimen_fiscal"]) == {"subsidio"}
    assert set(largo.loc[largo["fecha"] == dt.date(2026, 10, 5), "regimen_fiscal"]) == {"exento"}


def test_comparar_detecta_perdidas_cambios_y_nulos():
    base = mem.limpiar(mem.extraer_crudo(hoja_de_prueba([fila("2026-01-05"), fila("2026-01-06"), fila("2026-01-07")])))
    nuevo = mem.limpiar(
        mem.extraer_crudo(hoja_de_prueba([fila("2026-01-05", superior=35.0), fila("2026-01-06", regular=0)]))
    )
    problemas = " | ".join(mem.comparar_versiones(base, nuevo))
    assert "Se perdieron 1 fechas" in problemas
    assert "super: cambió el valor" in problemas
    assert "regular: 1 fechas quedaron sin dato" in problemas


def test_comparar_acepta_fechas_nuevas():
    base = mem.limpiar(mem.extraer_crudo(hoja_de_prueba([fila("2026-01-05")])))
    nuevo = mem.limpiar(mem.extraer_crudo(hoja_de_prueba([fila("2026-01-05"), fila("2026-01-06")])))
    assert mem.comparar_versiones(base, nuevo) == []


def test_excel_del_repo_se_limpia_sin_errores(crudo_real):
    limpio = mem.limpiar(crudo_real)
    assert limpio["fecha"].is_unique
    assert limpio["fecha"].is_monotonic_increasing
    assert limpio["tipo_cambio"].notna().all()
    assert len(mem.precios_fuera_de_rango(limpio)) == 0
    assert not np.isnan(limpio[mem.COMBUSTIBLES].iloc[-1]).any(), "El último día debe tener precio"
