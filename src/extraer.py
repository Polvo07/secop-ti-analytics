"""
Paso 1 — Extracción.

Descarga contratos de SECOP II desde la API de Socrata, filtrando en el servidor
por fecha para no traer millones de filas innecesarias.

Uso:
    python src/extraer.py                 # usa la ventana definida en config.py
    python src/extraer.py --limite 5000   # prueba rápida
"""

import argparse
import os
import sys
import time

import pandas as pd
import requests

import config


def _cabeceras() -> dict:
    """Incluye el app token si está disponible como variable de entorno."""
    token = os.environ.get(config.APP_TOKEN_ENV)
    return {"X-App-Token": token} if token else {}


def inspeccionar_esquema() -> list[str]:
    """
    Trae una fila para conocer las columnas reales del dataset.

    SECOP II ha cambiado nombres de columnas entre versiones, así que el pipeline
    no asume el esquema: lo consulta y se adapta.
    """
    resp = requests.get(
        config.API_URL, params={"$limit": 1}, headers=_cabeceras(), timeout=60
    )
    resp.raise_for_status()
    filas = resp.json()
    if not filas:
        raise RuntimeError("La API respondió sin registros. Revisa el DATASET_ID.")
    columnas = sorted(filas[0].keys())
    print(f"[esquema] {len(columnas)} columnas detectadas")
    return columnas


def _resolver(columnas: list[str], *candidatos: str) -> str | None:
    """Devuelve el primer nombre de columna que exista en el dataset."""
    for c in candidatos:
        if c in columnas:
            return c
    return None


def construir_where(columnas: list[str]) -> str:
    """Arma la cláusula $where de SoQL para filtrar por fecha en el servidor."""
    col_fecha = _resolver(columnas, "fecha_de_firma", "fecha_de_firma_del_contrato")
    if not col_fecha:
        print("[aviso] No se encontró columna de fecha de firma; se descarga sin filtro de fecha.")
        return ""
    return f"{col_fecha} >= '{config.FECHA_INICIO}T00:00:00.000'"


def descargar(limite_total: int | None = None, tam_pagina: int = 50_000) -> pd.DataFrame:
    """
    Descarga paginada. Socrata permite $limit alto, pero paginar evita timeouts
    y permite mostrar progreso en descargas largas.
    """
    columnas = inspeccionar_esquema()
    where = construir_where(columnas)

    paginas: list[pd.DataFrame] = []
    offset = 0
    total = 0

    while True:
        if limite_total is not None:
            tam_pagina = min(tam_pagina, limite_total - total)
            if tam_pagina <= 0:
                break

        params = {"$limit": tam_pagina, "$offset": offset, "$order": ":id"}
        if where:
            params["$where"] = where

        for intento in range(1, 4):
            try:
                resp = requests.get(
                    config.API_URL, params=params, headers=_cabeceras(), timeout=180
                )
                resp.raise_for_status()
                break
            except requests.RequestException as exc:
                if intento == 3:
                    raise
                espera = 5 * intento
                print(f"[reintento {intento}] {exc} — esperando {espera}s")
                time.sleep(espera)

        filas = resp.json()
        if not filas:
            break

        paginas.append(pd.DataFrame(filas))
        total += len(filas)
        offset += len(filas)
        print(f"[descarga] {total:,} registros acumulados")

        if len(filas) < tam_pagina:
            break

    if not paginas:
        raise RuntimeError("No se descargó ningún registro. Revisa el filtro de fecha.")

    df = pd.concat(paginas, ignore_index=True)
    print(f"[descarga] finalizada: {len(df):,} filas x {len(df.columns)} columnas")
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrae contratos de SECOP II.")
    parser.add_argument(
        "--limite", type=int, default=None,
        help="Máximo de registros a descargar (para pruebas rápidas).",
    )
    args = parser.parse_args()

    df = descargar(limite_total=args.limite)
    df.to_csv(config.ARCHIVO_RAW, index=False, encoding="utf-8")
    print(f"[guardado] {config.ARCHIVO_RAW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
