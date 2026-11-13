"""Compara los archivos de datos del pull request contra los de `main`.

El workflow `tests.yml` copia la carpeta `data/` de `main` en la ruta de la variable DATOS_BASE.
Si un archivo todavía no existe en `main`, su comparación se salta.

Para correrlo en local, desde la raíz del repo:

    mkdir -p base/data/mem base/data/eia
    git show origin/main:data/mem/precios_promedio_nacionales_diarios.xlsx > base/data/mem/precios_promedio_nacionales_diarios.xlsx
    DATOS_BASE=base pytest tests/test_no_empeorar.py
"""

import os
from pathlib import Path

import pytest

from gas_price import eia, mem

RAIZ = Path(__file__).parents[1]
BASE = os.environ.get("DATOS_BASE")
EXCEL_MEM = Path("data") / "mem" / "precios_promedio_nacionales_diarios.xlsx"


def ruta_base(relativa: Path) -> Path:
    if not BASE:
        pytest.skip("Sin DATOS_BASE no hay versión de main contra la cual comparar")
    ruta = Path(BASE) / relativa
    if not ruta.exists():
        pytest.skip(f"{relativa} todavía no existe en main")
    return ruta


def test_el_excel_del_mem_no_empeora():
    base = mem.limpiar(mem.extraer_crudo(mem.leer_hoja(ruta_base(EXCEL_MEM))))
    nuevo = mem.limpiar(mem.extraer_crudo(mem.leer_hoja(RAIZ / EXCEL_MEM)))
    problemas = mem.comparar_versiones(base, nuevo)
    assert not problemas, "\n".join(problemas)


@pytest.mark.parametrize("serie", list(eia.SERIES))
def test_las_series_de_la_eia_no_empeoran(serie):
    relativa = Path("data") / "eia" / eia.SERIES[serie]["archivo"]
    base = eia.leer(ruta_base(relativa))
    nuevo = eia.leer(RAIZ / relativa)
    problemas = eia.comparar_versiones(base, nuevo)
    assert not problemas, "\n".join(problemas)
