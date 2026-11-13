import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from gas_price import eia

DATOS = Path(__file__).parents[1] / "data" / "eia"


@pytest.mark.parametrize("serie", list(eia.SERIES))
def test_archivo_del_repo_se_lee_sin_errores(serie):
    datos = eia.leer(DATOS / eia.SERIES[serie]["archivo"])
    assert datos["fecha"].is_unique
    assert datos["fecha"].is_monotonic_increasing
    assert datos["fecha"].min() <= dt.date(2013, 1, 1), "Debe cubrir todo el rango del Excel del MEM"
    assert len(eia.precios_fuera_de_rango(datos)) == 0


def serie(*filas):
    return pd.DataFrame(filas, columns=["fecha", "precio_usd_galon"]).assign(
        fecha=lambda d: pd.to_datetime(d["fecha"]).dt.date
    )


def test_comparar_detecta_perdidas_cambios_y_nulos():
    base = serie(("2026-01-05", 2.0), ("2026-01-06", 2.1), ("2026-01-07", 2.2))
    nuevo = serie(("2026-01-05", 2.5), ("2026-01-06", None))
    problemas = " | ".join(eia.comparar_versiones(base, nuevo))
    assert "Se perdieron 1 fechas" in problemas
    assert "Cambió el precio de 1 fechas" in problemas
    assert "1 fechas quedaron sin dato" in problemas


def test_comparar_acepta_fechas_nuevas():
    base = serie(("2026-01-05", 2.0))
    nuevo = serie(("2026-01-05", 2.0), ("2026-01-06", 2.1))
    assert eia.comparar_versiones(base, nuevo) == []
