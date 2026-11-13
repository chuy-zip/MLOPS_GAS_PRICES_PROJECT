import datetime as dt

import numpy as np
import pandas as pd
import pytest

from gas_price import features, modelo


def oficiales(precios_por_dia: dict) -> pd.DataFrame:
    """Plata del MEM con el mismo precio para los tres combustibles."""
    filas = [
        {"fecha": dt.date.fromisoformat(dia), "combustible": c, "precio_q_galon": precio, "tipo_cambio": 7.7, "regimen_fiscal": "normal"}
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
    assert list(etiquetas) == ["sube", "baja", "se_mantiene", "se_mantiene", None]


def test_precios_diarios_rellena_huecos_y_los_marca():
    diarios = features.precios_diarios(oficiales({"2026-01-05": 30.0, "2026-01-08": 31.0}))
    superior = diarios[diarios["combustible"] == "super"]
    assert len(superior) == 4
    assert list(superior["precio_oficial"]) == [30.0, 30.0, 30.0, 31.0]
    assert list(superior["es_imputado"]) == [False, True, True, False]


def test_features_etiqueta_es_el_cambio_de_la_semana_siguiente():
    precios = [30.0] * 9 + [31.0, 31.0, 30.0]
    diarios = features.precios_diarios(oficiales(lunes_con_precios(precios)))
    semanales = features.features_modelo(diarios, internacionales("2025-12-01", 120))
    superior = semanales[semanales["combustible"] == "super"].set_index("semana")

    # Cada semana se identifica por su martes de inicio. La del martes 24 de febrero cierra el lunes 2 de marzo.
    assert superior.loc[dt.date(2026, 2, 24), "etiqueta"] == "sube"  # lunes 2 a lunes 9: 30 a 31
    assert superior.loc[dt.date(2026, 3, 3), "etiqueta"] == "se_mantiene"  # lunes 9 a lunes 16: 31 a 31
    assert superior.loc[dt.date(2026, 3, 10), "etiqueta"] == "baja"  # lunes 16 a lunes 23: 31 a 30
    assert superior["etiqueta"].iloc[-1] is None, "La última semana todavía no tiene etiqueta"


def test_semana_incompleta_no_inventa_etiqueta():
    # Los datos terminan un martes con un cambio de precio. La semana del lunes 16 todavía no llega.
    precios = lunes_con_precios([30.0] * 10)
    precios["2026-03-10"] = 35.0
    diarios = features.precios_diarios(oficiales(precios))
    semanales = features.features_modelo(diarios, internacionales("2025-12-01", 120))
    superior = semanales[semanales["combustible"] == "super"].set_index("semana")

    # La semana del martes 10 todavía no termina. La más reciente completa es la del martes 3, que cierra el lunes 9.
    assert superior.index.max() == dt.date(2026, 3, 3), "No debe existir la semana que todavía no termina"
    assert superior.loc[dt.date(2026, 3, 3), "etiqueta"] is None, "La semana más reciente es la que se va a predecir"


def test_features_no_usa_el_precio_internacional_del_mismo_lunes():
    precios = lunes_con_precios([30.0] * 12)
    diarios = features.precios_diarios(oficiales(precios))
    lunes = dt.date(2026, 3, 9)
    inicio = dt.date(2025, 12, 1)

    normal = internacionales("2025-12-01", 120)
    alterado = internacionales(
        "2025-12-01", 120, precio=lambda i: 9.0 if inicio + dt.timedelta(days=i) >= lunes else 2.0
    )
    semana = lunes - dt.timedelta(days=6)  # la semana que cierra ese lunes empieza el martes anterior
    fila = lambda intl: features.features_modelo(diarios, intl).set_index(["semana", "combustible"]).loc[(semana, "super")]

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
            fila["etiqueta"] = ["sube", "baja", "se_mantiene"][(i + len(c)) % 3]
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
    assert set(predicciones) <= {"sube", "baja", "se_mantiene"}
    assert 0 <= resultado["modelo_balanced_accuracy"] <= 1


def test_predecir_la_semana_actual():
    datos = semanales_sinteticas()
    ultima = datos["semana"].max()
    datos.loc[datos["semana"] == ultima, "etiqueta"] = None
    entrenado = modelo.construir_modelo().fit(*[
        modelo.con_etiqueta(datos)[features.VARIABLES], modelo.con_etiqueta(datos)["etiqueta"]
    ])

    filas = modelo.semana_a_predecir(datos)
    resultado = modelo.predecir(entrenado, filas, version_modelo="3")

    assert list(resultado["combustible"]) == ["diesel", "regular", "super"]
    assert (resultado["semana"] == ultima).all()
    assert (resultado["semana_objetivo"] == ultima + dt.timedelta(days=7)).all()
    sumas = resultado[["prob_sube", "prob_baja", "prob_se_mantiene"]].sum(axis=1)
    assert sumas.to_numpy() == pytest.approx([1.0, 1.0, 1.0])
    assert (resultado["probabilidad"] == resultado[["prob_sube", "prob_baja", "prob_se_mantiene"]].max(axis=1)).all()
    assert set(resultado["version_modelo"]) == {"3"}



def test_inicio_de_semana_es_el_martes():
    fechas = ["2026-11-10", "2026-11-12", "2026-11-16", "2026-11-17"]  # martes, jueves, lunes, martes
    assert list(features.inicio_de_semana(fechas)) == [
        dt.date(2026, 11, 10), dt.date(2026, 11, 10), dt.date(2026, 11, 10), dt.date(2026, 11, 17),
    ]


def test_precio_semanal_combina_mem_y_fotos():
    diarios = features.precios_diarios(oficiales({"2026-11-10": 30.0, "2026-11-13": 32.0, "2026-11-16": 32.0}))
    fotos = pd.DataFrame({
        "fecha": [dt.date(2026, 11, 11), dt.date(2026, 11, 12)],
        "combustible": ["super", "super"],
        "precio_q_galon": [31.0, 33.0],
    })
    semanal = features.precio_semanal(diarios, fotos).set_index(["semana", "combustible", "fuente"])

    mem_super = semanal.loc[(dt.date(2026, 11, 10), "super", "mem")]
    assert mem_super["n_observaciones"] == 7  # martes 10 a lunes 16, con los días faltantes rellenados
    assert mem_super["precio_minimo"] == 30.0
    assert mem_super["precio_maximo"] == 32.0

    fotos_super = semanal.loc[(dt.date(2026, 11, 10), "super", "fotos")]
    assert fotos_super["precio_promedio"] == pytest.approx(32.0)
    assert fotos_super["n_observaciones"] == 2


def test_variacion_semanal_solo_compara_semanas_consecutivas():
    semanal = pd.DataFrame({
        "semana": [dt.date(2026, 10, 27), dt.date(2026, 11, 3), dt.date(2026, 11, 17)],
        "combustible": ["super"] * 3,
        "fuente": ["fotos"] * 3,
        "precio_promedio": [30.0, 31.0, 30.5],
    })
    variacion = features.variacion_semanal(semanal).set_index("semana")

    assert variacion.loc[dt.date(2026, 11, 3), "variacion_q"] == pytest.approx(1.0)
    assert variacion.loc[dt.date(2026, 11, 3), "direccion"] == "sube"
    assert pd.isna(variacion.loc[dt.date(2026, 11, 17), "variacion_q"]), "Falta la semana del 10, no hay con qué comparar"
    assert variacion.loc[dt.date(2026, 11, 17), "direccion"] is None
