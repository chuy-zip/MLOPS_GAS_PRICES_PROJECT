"""Descarga de Databricks lo que necesita la API: el modelo `champion` y una copia de oro.

Uso, desde la raíz del repo, con el paquete instalado con sus extras de exportación:

    pip install -e ".[exportar]"
    databricks auth login --host <url_del_workspace>      # una sola vez, con la CLI de Databricks
    python scripts/exportar_para_api.py

Deja en `api/artefactos/`:

    modelo/                  el modelo de MLflow, con su requirements.txt
    datos/*.parquet          referencia_actual, precio_semanal, metricas_modelo, predicciones
                             y la semana más reciente de features_modelo
    manifiesto.json          versión del modelo, fecha de exportación y filas de cada tabla

Al final verifica que el modelo descargado prediga lo mismo que `gold.predicciones`.
La carpeta no se sube al repo: la imagen de Docker de la API la copia al construirse.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import time
from pathlib import Path

import mlflow
import mlflow.artifacts
import mlflow.sklearn
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, Format, StatementState
from mlflow.tracking import MlflowClient

from gas_price import exportar

RAIZ = Path(__file__).resolve().parents[1]


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalogo", default="equipo_01")
    parser.add_argument("--esquema-gold", default="gold")
    parser.add_argument("--destino", default=str(RAIZ / "api" / "artefactos"))
    parser.add_argument("--perfil", default=None, help="Perfil de ~/.databrickscfg. Por defecto, el de la CLI o las variables de entorno")
    parser.add_argument("--warehouse-id", default=None, help="SQL warehouse. Por defecto, el primero del workspace")
    return parser.parse_args()


def elegir_warehouse(cliente: WorkspaceClient, warehouse_id: str | None) -> str:
    if warehouse_id:
        return warehouse_id
    warehouses = list(cliente.warehouses.list())
    if not warehouses:
        sys.exit("No hay ningún SQL warehouse en el workspace")
    print(f"SQL warehouse: {warehouses[0].name}")
    return warehouses[0].id


def consultar(cliente: WorkspaceClient, warehouse_id: str, sentencia: str):
    respuesta = cliente.statement_execution.execute_statement(
        statement=sentencia,
        warehouse_id=warehouse_id,
        wait_timeout="50s",
        disposition=Disposition.INLINE,
        format=Format.JSON_ARRAY,
    )
    # Si el warehouse estaba apagado, la consulta puede tardar más que la espera inicial.
    while respuesta.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(5)
        respuesta = cliente.statement_execution.get_statement(respuesta.statement_id)
    if respuesta.status.state != StatementState.SUCCEEDED:
        sys.exit(f"Falló la consulta: {respuesta.status.error}\n{sentencia}")

    columnas = [(c.name, getattr(c.type_name, "value", c.type_name)) for c in respuesta.manifest.schema.columns]
    filas = list(respuesta.result.data_array or []) if respuesta.result else []
    siguiente = respuesta.result.next_chunk_index if respuesta.result else None
    while siguiente is not None:
        parte = cliente.statement_execution.get_statement_result_chunk_n(respuesta.statement_id, siguiente)
        filas.extend(parte.data_array or [])
        siguiente = parte.next_chunk_index
    return exportar.a_dataframe(columnas, filas)


def main() -> int:
    args = argumentos()
    oro = f"{args.catalogo}.{args.esquema_gold}"
    destino = Path(args.destino)
    carpeta_datos = destino / "datos"
    carpeta_modelo = destino / "modelo"

    try:
        cliente = WorkspaceClient(profile=args.perfil) if args.perfil else WorkspaceClient()
    except ValueError as error:
        sys.exit(
            "No hay credenciales de Databricks en esta computadora.\n"
            "Inicia sesión una vez con la CLI de Databricks:\n"
            "    databricks auth login --host <url_del_workspace> --profile DEFAULT\n"
            f"Detalle: {error}"
        )
    print(f"Workspace: {cliente.config.host}")

    # Tablas de oro
    warehouse_id = elegir_warehouse(cliente, args.warehouse_id)
    carpeta_datos.mkdir(parents=True, exist_ok=True)
    tablas = {}
    for nombre, plantilla in exportar.TABLAS.items():
        datos = consultar(cliente, warehouse_id, plantilla.format(oro=oro))
        datos.to_parquet(carpeta_datos / f"{nombre}.parquet", index=False)
        tablas[nombre] = datos
        print(f"{nombre}: {len(datos)} filas")

    # Modelo champion
    destino_mlflow = f"databricks://{args.perfil}" if args.perfil else "databricks"
    mlflow.set_tracking_uri(destino_mlflow)
    mlflow.set_registry_uri(destino_mlflow.replace("databricks", "databricks-uc", 1))
    nombre_modelo = exportar.NOMBRE_MODELO.format(oro=oro)
    version = MlflowClient().get_model_version_by_alias(nombre_modelo, exportar.ALIAS)
    if carpeta_modelo.exists():
        shutil.rmtree(carpeta_modelo)
    descargado = mlflow.artifacts.download_artifacts(
        artifact_uri=f"models:/{nombre_modelo}@{exportar.ALIAS}", dst_path=str(carpeta_modelo)
    )
    print(f"Modelo {nombre_modelo} versión {version.version} en {descargado}")

    manifiesto = {
        "exportado_en": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "workspace": cliente.config.host,
        "modelo": nombre_modelo,
        "version_modelo": version.version,
        "run_id": version.run_id,
        "filas": {nombre: len(datos) for nombre, datos in tablas.items()},
        "semana_mas_reciente": str(tablas["features_modelo"]["semana"].max()) if len(tablas["features_modelo"]) else None,
    }
    (destino / "manifiesto.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")

    # Verificación: el modelo descargado debe predecir lo mismo que Databricks.
    requisitos = Path(descargado) / "requirements.txt"
    if requisitos.exists():
        sklearn_requerido = [l for l in requisitos.read_text().splitlines() if l.startswith("scikit-learn")]
        print(f"Versión con que se entrenó: {sklearn_requerido}. La imagen de la API debe usar la misma")
    try:
        campeon = mlflow.sklearn.load_model(descargado)
    except Exception as error:  # noqa: BLE001
        print(f"No se pudo cargar el modelo en esta computadora: {error}")
        print("Lo más probable es que la versión local de scikit-learn sea distinta. Revisa requirements.txt")
        return 1

    diferencias = exportar.comparar_con_predicciones(campeon, tablas["features_modelo"], tablas["predicciones"])
    if diferencias:
        print("El modelo descargado NO coincide con gold.predicciones:")
        for diferencia in diferencias:
            print(f"  {diferencia}")
        return 1
    print("Verificado: el modelo descargado predice lo mismo que gold.predicciones")
    print(f"Listo. Artefactos en {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
