"""Descarga los precios internacionales de la EIA y actualiza los archivos de data/eia.

Uso, desde la raíz del repo y con el paquete instalado (pip install -e .):

    python scripts/actualizar_eia.py

Antes de reemplazar cada archivo, lo valida con las mismas reglas de "no empeorar" que el CI.
Si algo falla, no toca el archivo del repo. Después de correrlo, revisar el resumen,
hacer commit en una rama y abrir un pull request.
"""

import sys
import tempfile
import urllib.request
from pathlib import Path

from gas_price import eia

URL = "https://www.eia.gov/dnav/pet/hist_xls/{serie}d.xls"
CARPETA = Path(__file__).resolve().parents[1] / "data" / "eia"


def descargar(serie: str, destino: Path) -> None:
    pedido = urllib.request.Request(URL.format(serie=serie), headers={"User-Agent": "gas-price-pipeline"})
    with urllib.request.urlopen(pedido, timeout=60) as respuesta:
        destino.write_bytes(respuesta.read())


def actualizar(nombre: str, config: dict, temporal: Path) -> bool:
    """Devuelve True si la serie quedó actualizada o sin cambios, False si hubo un problema."""
    actual = CARPETA / config["archivo"]
    nuevo = temporal / config["archivo"]

    descargar(config["serie_eia"], nuevo)
    datos_nuevos = eia.leer(nuevo)

    if actual.exists():
        datos_actuales = eia.leer(actual)
        problemas = eia.comparar_versiones(datos_actuales, datos_nuevos)
        if problemas:
            print(f"{nombre}: NO se actualizó. Problemas:")
            for problema in problemas:
                print(f"  {problema}")
            return False
        dias_nuevos = len(datos_nuevos) - len(datos_actuales)
    else:
        dias_nuevos = len(datos_nuevos)

    if dias_nuevos == 0:
        print(f"{nombre}: sin datos nuevos. Último día {datos_nuevos['fecha'].iloc[-1]}")
        return True

    actual.write_bytes(nuevo.read_bytes())
    print(f"{nombre}: {dias_nuevos} días nuevos. Último día {datos_nuevos['fecha'].iloc[-1]}")
    return True


def main() -> int:
    CARPETA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporal:
        resultados = [actualizar(nombre, config, Path(temporal)) for nombre, config in eia.SERIES.items()]
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
