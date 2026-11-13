"""Evalúa el modelo de tendencia en local, con los archivos de data/ y el mismo código que usa Databricks.

Uso, desde la raíz del repo y con el paquete instalado (pip install -e .):

    python scripts/evaluar_modelo.py

Sirve para probar cambios en las variables o en el modelo antes de llevarlos al pipeline.
"""

from pathlib import Path

import pandas as pd

from gas_price import eia, features, mem, modelo

DATOS = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    crudo = mem.extraer_crudo(mem.leer_hoja(DATOS / "mem" / "precios_promedio_nacionales_diarios.xlsx"))
    precios_oficiales = mem.a_formato_largo(mem.limpiar(crudo))

    partes = []
    for serie, config in eia.SERIES.items():
        datos = eia.leer(DATOS / "eia" / config["archivo"])
        datos.insert(1, "serie", serie)
        partes.append(datos)
    precios_internacionales = pd.concat(partes, ignore_index=True)

    diarios = features.precios_diarios(precios_oficiales)
    semanales = features.features_modelo(diarios, precios_internacionales)
    _, resultado = modelo.evaluar(semanales)

    print(f"Semanas con variables: {semanales['semana'].nunique()}, desde {semanales['semana'].min()}")
    print(f"Entrenamiento: {resultado['filas_entrenamiento']} filas. Prueba: {resultado['filas_prueba']} filas desde {resultado['inicio_prueba']}")
    print()
    print(f"{'Métrica':28s} {'Modelo':>8s} {'Repetir semana pasada':>22s}")
    for nombre in ["balanced_accuracy", "f1_macro", "direccion_con_movimiento"]:
        print(f"{nombre:28s} {resultado['modelo_' + nombre]:8.2f} {resultado['regla_' + nombre]:22.2f}")


if __name__ == "__main__":
    main()
