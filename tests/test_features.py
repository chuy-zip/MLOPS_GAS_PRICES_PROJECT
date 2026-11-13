import datetime as dt

import numpy as np
import pandas as pd
import pytest

from gas_price import features, modelo


def oficiales(precios_por_dia: dict) -> pd.DataFrame:
    """Plata del MEM con el mismo precio para los tres combustibles."""
    filas = [
        {"fecha": dt.date.fromisoformat(dia), "combustible": c, "precio_gtq_galon": precio, "tipo_cambio": 7.7, "regimen_fiscal": "normal"}
        for dia, precio in precios_por_dia.items()
        for c in ["super", "regular", "diesel"]
    ]
    return pd.DataFrame(filas)


def internacionales(inicio: str, dias: int, precio=2.0) -> pd.DataFrame:
    fechas = pd.date_range(inicio, periods=dias, freq="D").date
    precios = precio if callable(precio) else (lambda i: precio)
    return pd.DataFrame(
        [{"fecha": f, "serie": s, "precio_usd_galon": precios(i)} for i, f in enumerate(fechas) for s in ["gasolina", "diesel"]]
    )


def lunes_con_precios(precios: list[float], inicio="2026-01-05") -> dict:
    lunes = pd.date_range(inicio, periods=len(precios), freq="7D")
    return {d.date().isoformat(): p for d, p in zip(lunes, precios)}


def test_etiquetar_usa_el_umbral():
    etiquetas = features.etiquetar(pd.Series([0.5, -0.5, 0.05, -0.05, np.nan]))
    assert list(etiquetas) == ["sube", "baja", "igual", "igual", None]


def test_precios_diarios_rellena_huecos_y_los_marca():
    diarios = features.precios_diarios(oficiales({"2026-01-05": 30.0, "2026-01-08": 31.0}))
    superior = diarios[diarios["combustible"] == "super"]
    assert len(superior) == 4
    assert list(superior["precio_oficial"]) == [30.0, 30.0, 30.0, 31.0]
    assert list(superior["es_imputado"]) == [False, True, True, False]


def test_features_etiqueta_es_el_cambio_de_la_semana_siguiente():
    precios = [30.0] * 9 + [31.0, 31.0, 30.0]
    diarios = features.precios_diarios(oficiales(lunes_con_precios(precios)))
    semanales = features.features_semanales(diarios, internacionales("2025-12-01", 120))
    superior = semanales[semanales["combustible"] == "super"].set_index("semana")

    assert superior.loc[dt.date(2026, 3, 2), "etiqueta"] == "sube"  # 30 a 31
    assert superior.loc[dt.date(2026, 3, 9), "etiqueta"] == "igual"  # 31 a 31
    assert superior.loc[dt.date(2026, 3, 16), "etiqueta"] == "baja"  # 31 a 30
    assert superior["etiqueta"].iloc[-1] is None, "La última semana todavía no tiene etiqueta"


def test_features_no_usa_el_precio_internacional_del_mismo_lunes():
    precios = lunes_con_precios([30.0] * 12)
    diarios = features.precios_diarios(oficiales(precios))
    lunes = dt.date(2026, 3, 9)
    inicio = dt.date(2025, 12, 1)

    normal = internacionales("2025-12-01", 120)
    alterado = internacionales(
        "2025-12-01", 120, precio=lambda i: 9.0 if inicio + dt.timedelta(days=i) >= lunes else 2.0
    )
    fila = lambda intl: features.features_semanales(diarios, intl).set_index(["semana", "combustible"]).loc[(lunes, "super")]

    assert fila(normal)["intl_cambio_1"] == pytest.approx(fila(alterado)["intl_cambio_1"])


def test_referencia_actual_toma_el_ultimo_precio_y_el_proximo_lunes():
    diarios = features.precios_diarios(oficiales({"2026-11-09": 32.49, "2026-11-11": 32.0}))
    referencia = features.referencia_actual(diarios).set_index("combustible")
    assert referencia.loc["super", "precio_referencia"] == 32.0
    assert referencia.loc["super", "limite_normal"] == pytest.approx(33.0)
    assert referencia.loc["super", "proximo_cambio"] == dt.date(2026, 11, 16)


def semanales_sinteticas(semanas=60) -> pd.DataFrame:
    generador = np.random.default_rng(0)
    filas = []
    for i in range(semanas):
        for c in ["super", "regular", "diesel"]:
            fila = {"semana": dt.date(2025, 1, 6) + dt.timedelta(weeks=i), "combustible": c}
            fila.update({v: generador.normal() for v in features.VARIABLES_NUMERICAS})
            fila["etiqueta"] = ["sube", "baja", "igual"][(i + len(c)) % 3]
            filas.append(fila)
    return pd.DataFrame(filas)


def test_particion_temporal_no_mezcla_fechas():
    entrenamiento, prueba = modelo.particion_temporal(semanales_sinteticas(), semanas_de_prueba=10)
    assert entrenamiento["semana"].max() < prueba["semana"].min()
    assert prueba["semana"].nunique() == 10


def test_modelo_entrena_y_predice_las_tres_clases():
    datos = semanales_sinteticas()
    entrenado, resultado = modelo.evaluar(datos, semanas_de_prueba=10)
    predicciones = entrenado.predict(datos[features.VARIABLES])
    assert set(predicciones) <= {"sube", "baja", "igual"}
    assert 0 <= resultado["modelo_balanced_accuracy"] <= 1
