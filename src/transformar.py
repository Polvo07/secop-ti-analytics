"""
Paso 2 — Transformación.

Toma el CSV crudo, aísla el universo de contratos de TI, limpia y construye un
modelo estrella (1 tabla de hechos + 3 dimensiones) listo para Power BI.

Uso:
    python src/transformar.py
"""

import re
import sys
import unicodedata

import numpy as np
import pandas as pd

import config

# --- Mapeo flexible de columnas ---------------------------------------------
# Cada campo lógico se resuelve contra varios nombres posibles, porque SECOP II
# ha cambiado nomenclatura entre versiones del dataset.
MAPA_COLUMNAS: dict[str, tuple[str, ...]] = {
    "id_contrato": ("id_contrato", "referencia_del_contrato", "id_del_portafolio"),
    "entidad": ("nombre_entidad", "nombre_de_la_entidad", "entidad"),
    "nit_entidad": ("nit_entidad", "nit_de_la_entidad"),
    "departamento": ("departamento", "departamento_entidad"),
    "ciudad": ("ciudad", "ciudad_entidad", "municipio"),
    "orden": ("orden", "orden_entidad"),
    "sector": ("sector", "sector_entidad"),
    "descripcion": ("descripcion_del_proceso", "objeto_del_contrato", "detalle_del_objeto"),
    "categoria": ("codigo_de_categoria_principal", "categoria_principal"),
    "tipo_contrato": ("tipo_de_contrato", "tipo_contrato"),
    "modalidad": ("modalidad_de_contratacion", "modalidad_de_contrataci_n"),
    "estado": ("estado_contrato", "estado_del_contrato", "estado"),
    "fecha_firma": ("fecha_de_firma", "fecha_de_firma_del_contrato"),
    "fecha_inicio": ("fecha_de_inicio_del_contrato", "fecha_de_inicio"),
    "fecha_fin": ("fecha_de_fin_del_contrato", "fecha_de_fin"),
    "valor": ("valor_del_contrato", "valor_contrato", "valor_total_adjudicacion"),
    "valor_pagado": ("valor_pagado", "valor_facturado"),
    "proveedor": ("proveedor_adjudicado", "nombre_del_proveedor", "proveedor"),
    "doc_proveedor": ("documento_proveedor", "nit_del_proveedor", "identificacion_del_proveedor"),
    "es_pyme": ("es_pyme", "espyme"),
}


def resolver_columnas(df: pd.DataFrame) -> dict[str, str]:
    """Devuelve {campo_logico: columna_real} para las que existan en el archivo."""
    encontrado: dict[str, str] = {}
    for logico, candidatos in MAPA_COLUMNAS.items():
        for c in candidatos:
            if c in df.columns:
                encontrado[logico] = c
                break
    faltantes = set(MAPA_COLUMNAS) - set(encontrado)
    if faltantes:
        print(f"[aviso] campos no encontrados en el origen: {sorted(faltantes)}")
    return encontrado


# --- Utilidades de normalización --------------------------------------------
def sin_tildes(texto: str) -> str:
    """Quita tildes y pasa a minúsculas, para comparar texto de forma estable."""
    if not isinstance(texto, str):
        return ""
    normal = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normal if not unicodedata.combining(c)).lower()


def normalizar_nombre(nombre: str) -> str:
    """
    Estandariza razones sociales: mayúsculas, sin puntuación redundante ni
    sufijos societarios, para que 'ABC S.A.S.' y 'ABC SAS' cuenten como uno solo.

    Los textos de relleno ('VALOR PROVEEDOR', 'NO DEFINIDO') se colapsan en una
    sola categoría, porque de lo contrario aparecen como si fueran empresas
    reales en los rankings por valor adjudicado.
    """
    if not isinstance(nombre, str) or not nombre.strip():
        return "SIN INFORMACION"
    limpio = sin_tildes(nombre).upper()
    limpio = re.sub(r"[^\w\s]", " ", limpio)
    limpio = re.sub(r"\b(S\s*A\s*S|SAS|S\s*A|LTDA|E\s*S\s*P|SUCURSAL|COLOMBIA)\b", " ", limpio)
    limpio = re.sub(r"\s+", " ", limpio).strip()
    if not limpio or limpio in config.PROVEEDORES_INVALIDOS:
        return "SIN INFORMACION"
    return limpio


def _texto_a_numero(valor: str) -> float:
    """
    Interpreta un importe que puede venir en formato colombiano ('1.500.000,50')
    o anglosajón ('1,500,000.50'), o sin separadores ('1500000').

    Regla: si aparecen los dos separadores, el que esté más a la derecha es el
    decimal. Si solo aparece uno y se repite, es separador de miles. Si aparece
    una sola vez seguido de exactamente 3 dígitos, se asume separador de miles,
    porque los valores de contrato en COP se registran sin centavos.
    """
    limpio = re.sub(r"[^\d,.\-]", "", str(valor))
    if not limpio or limpio in {"-", ".", ","}:
        return float("nan")

    tiene_punto, tiene_coma = "." in limpio, "," in limpio

    if tiene_punto and tiene_coma:
        decimal = "." if limpio.rfind(".") > limpio.rfind(",") else ","
        miles = "," if decimal == "." else "."
        limpio = limpio.replace(miles, "").replace(decimal, ".")
    elif tiene_punto or tiene_coma:
        sep = "." if tiene_punto else ","
        if limpio.count(sep) > 1:
            limpio = limpio.replace(sep, "")
        else:
            entero, _, resto = limpio.partition(sep)
            limpio = entero + resto if len(resto) == 3 else f"{entero}.{resto}"

    try:
        return float(limpio)
    except ValueError:
        return float("nan")


def a_numero(serie: pd.Series) -> pd.Series:
    """Convierte una columna de importes a numérico, tolerando ambos formatos."""
    if serie.dtype.kind in "if":
        return serie.astype("float64")
    return serie.map(_texto_a_numero).astype("float64")


# --- Filtro del universo TI --------------------------------------------------
def _codigo_unspsc(serie: pd.Series) -> pd.Series:
    """
    Reduce el código de categoría a sus dígitos, en orden.

    SECOP II lo publica como 'V1.43.23.15.00' (segmento.familia.clase.producto).
    Al quitar el prefijo de versión y los puntos queda '43231500', que permite
    filtrar por prefijo a la profundidad que se necesite: '43' toma el segmento
    completo, '8111' toma solo una familia dentro del segmento 81.
    """
    texto = serie.astype(str).str.upper()
    sin_version = texto.str.replace(r"^V\d+\.?", "", regex=True)
    return sin_version.str.replace(r"\D", "", regex=True)


def clasificar_ti(df: pd.DataFrame, cols: dict[str, str]) -> pd.Series:
    """
    Clasifica cada contrato y registra POR QUÉ vía entró al universo de TI.

    Devuelve 'codigo' si lo respalda la clasificación oficial UNSPSC, 'texto' si
    solo coincidió por palabras en el objeto contractual, y '' si no es de TI.

    La distinción importa: los que entran solo por texto son mucho más frágiles,
    porque dependen de cómo redactó el objeto un funcionario. Guardar el origen
    permite reportar los hallazgos con y sin ellos, en vez de esconder el
    supuesto detrás de un único número.
    """
    por_codigo = pd.Series(False, index=df.index)
    if "categoria" in cols:
        codigo = _codigo_unspsc(df[cols["categoria"]])
        for prefijo in config.PREFIJOS_UNSPSC_TI:
            por_codigo |= codigo.str.startswith(prefijo, na=False)

    por_texto = pd.Series(False, index=df.index)
    excluido = pd.Series(False, index=df.index)
    if "descripcion" in cols:
        desc = df[cols["descripcion"]].map(sin_tildes)
        patron = "|".join(re.escape(p) for p in config.PALABRAS_CLAVE_TI)
        por_texto = desc.str.contains(patron, regex=True, na=False)

        patron_excl = "|".join(re.escape(p) for p in config.EXCLUSIONES)
        excluido = desc.str.contains(patron_excl, regex=True, na=False)

    origen = pd.Series("", index=df.index, dtype="object")
    origen[por_texto & ~excluido] = "texto"
    origen[por_codigo & ~excluido] = "codigo"  # el respaldo oficial prevalece
    return origen


def marcar_ti(df: pd.DataFrame, cols: dict[str, str]) -> pd.Series:
    """Máscara booleana del universo de TI."""
    return clasificar_ti(df, cols) != ""


# --- Construcción del modelo -------------------------------------------------
def cargar_ti_por_lotes(ruta, tam_lote: int = 250_000) -> tuple[pd.DataFrame, int]:
    """
    Lee el CSV crudo por lotes y conserva únicamente los contratos de TI.

    El archivo completo tiene millones de filas y 85 columnas; cargarlo entero
    en memoria consume varios GB y hace fallar el proceso en un equipo normal.
    La estrategia es filtrar temprano: se leen solo las columnas necesarias, se
    procesa por lotes y se descarta la gran mayoría de filas antes de acumular.
    El resultado final es una fracción del original y ya cabe cómodamente.

    Devuelve (contratos_ti, total_leido).
    """
    encabezado = pd.read_csv(ruta, nrows=0)
    cols = resolver_columnas(encabezado)
    columnas_usadas = list(dict.fromkeys(cols.values()))
    print(f"[carga] leyendo {len(columnas_usadas)} de {len(encabezado.columns)} columnas")

    lotes: list[pd.DataFrame] = []
    total = 0
    for i, lote in enumerate(
        pd.read_csv(ruta, usecols=columnas_usadas, chunksize=tam_lote, low_memory=False),
        start=1,
    ):
        total += len(lote)
        ti = lote.loc[marcar_ti(lote, cols)]
        if len(ti):
            lotes.append(ti)
        acumulado = sum(len(x) for x in lotes)
        print(f"[carga] lote {i}: {total:,} leídos · {acumulado:,} de TI")

    if not lotes:
        raise RuntimeError("Ningún registro quedó clasificado como TI. Revisa los filtros.")

    return pd.concat(lotes, ignore_index=True), total


def construir(df_raw: pd.DataFrame, n_total: int | None = None) -> dict[str, pd.DataFrame]:
    cols = resolver_columnas(df_raw)
    reporte: list[str] = []

    n0 = n_total if n_total is not None else len(df_raw)
    reporte.append(f"- Registros descargados: **{n0:,}**")

    # 1) Aislar TI y registrar por qué vía entró cada contrato. Si los datos ya
    #    vienen filtrados por lotes, este paso no descarta nada adicional.
    origen = clasificar_ti(df_raw, cols)
    df = df_raw.loc[origen != ""].copy()
    df["origen_clasificacion"] = origen.loc[df.index]
    reporte.append(f"- Contratos clasificados como TI: **{len(df):,}** ({len(df)/n0:.1%} del total)")
    if len(df):
        respaldo = (df["origen_clasificacion"] == "codigo").mean()
        reporte.append(f"- Respaldados por código UNSPSC oficial: **{respaldo:.1%}** "
                       f"(el resto entró por coincidencia de texto)")

    # 2) Renombrar a nombres lógicos, conservando las columnas derivadas que ya
    #    se calcularon y que no forman parte del mapa del origen.
    df = df.rename(columns={real: logico for logico, real in cols.items()})
    conservar = [c for c in MAPA_COLUMNAS if c in df.columns] + ["origen_clasificacion"]
    df = df[conservar].copy()

    # 3) Tipos
    for campo in ("valor", "valor_pagado"):
        if campo in df.columns:
            df[campo] = a_numero(df[campo])
    for campo in ("fecha_firma", "fecha_inicio", "fecha_fin"):
        if campo in df.columns:
            df[campo] = pd.to_datetime(df[campo], errors="coerce", format="mixed")

    # 4) Duplicados
    if "id_contrato" in df.columns:
        antes = len(df)
        df = df.drop_duplicates(subset=["id_contrato"], keep="last")
        reporte.append(f"- Duplicados por id_contrato eliminados: **{antes - len(df):,}**")

    # 5) Registros sin valor utilizable
    antes = len(df)
    df = df[df["valor"].notna() & (df["valor"] > 0)]
    reporte.append(f"- Registros sin valor válido descartados: **{antes - len(df):,}**")

    # 6) Normalización de nombres
    if "entidad" in df.columns:
        df["entidad_norm"] = df["entidad"].map(normalizar_nombre)
    if "proveedor" in df.columns:
        df["proveedor_norm"] = df["proveedor"].map(normalizar_nombre)

    # 7) Columnas derivadas de negocio
    df["anio"] = df["fecha_firma"].dt.year
    df["mes"] = df["fecha_firma"].dt.month
    df["anio_mes"] = df["fecha_firma"].dt.to_period("M").astype(str)

    if {"fecha_inicio", "fecha_fin"}.issubset(df.columns):
        dur = (df["fecha_fin"] - df["fecha_inicio"]).dt.days
        # Duraciones negativas o absurdas se anulan en vez de propagarse
        df["duracion_dias"] = dur.where((dur >= 0) & (dur <= 365 * 10))

    if "modalidad" in df.columns:
        mod = df["modalidad"].map(sin_tildes)
        patron_baja = "|".join(re.escape(m) for m in config.MODALIDADES_BAJA_COMPETENCIA)
        df["baja_competencia"] = mod.str.contains(patron_baja, regex=True, na=False)
    else:
        df["baja_competencia"] = False

    df["valor_atipico"] = df["valor"] < config.VALOR_MINIMO_RAZONABLE
    reporte.append(
        f"- Contratos marcados como valor atípico (< {config.VALOR_MINIMO_RAZONABLE:,} COP): "
        f"**{int(df['valor_atipico'].sum()):,}**"
    )

    df["rango_valor"] = pd.cut(
        df["valor"],
        bins=[0, 10e6, 50e6, 200e6, 1e9, np.inf],
        labels=["< 10M", "10M – 50M", "50M – 200M", "200M – 1.000M", "> 1.000M"],
    )

    if "valor_pagado" in df.columns:
        df["pct_ejecutado"] = (df["valor_pagado"] / df["valor"]).clip(upper=2)

    # 8) Dimensiones
    dim_entidad = pd.DataFrame()
    if "entidad_norm" in df.columns:
        campos = [c for c in ("entidad_norm", "nit_entidad", "departamento", "ciudad", "orden", "sector") if c in df.columns]
        dim_entidad = (
            df[campos].drop_duplicates(subset=["entidad_norm"]).reset_index(drop=True)
        )
        dim_entidad.insert(0, "id_entidad", range(1, len(dim_entidad) + 1))
        df = df.merge(dim_entidad[["id_entidad", "entidad_norm"]], on="entidad_norm", how="left")

    dim_proveedor = pd.DataFrame()
    if "proveedor_norm" in df.columns:
        campos = [c for c in ("proveedor_norm", "doc_proveedor", "es_pyme") if c in df.columns]
        dim_proveedor = (
            df[campos].drop_duplicates(subset=["proveedor_norm"]).reset_index(drop=True)
        )
        dim_proveedor.insert(0, "id_proveedor", range(1, len(dim_proveedor) + 1))
        df = df.merge(dim_proveedor[["id_proveedor", "proveedor_norm"]], on="proveedor_norm", how="left")

    # 9) Dimensión fecha continua (necesaria para inteligencia de tiempo en DAX)
    dim_fecha = pd.DataFrame()
    if df["fecha_firma"].notna().any():
        rango = pd.date_range(
            df["fecha_firma"].min().normalize(),
            df["fecha_firma"].max().normalize(),
            freq="D",
        )
        meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        dim_fecha = pd.DataFrame({"fecha": rango})
        dim_fecha["anio"] = dim_fecha["fecha"].dt.year
        dim_fecha["trimestre"] = "T" + dim_fecha["fecha"].dt.quarter.astype(str)
        dim_fecha["mes"] = dim_fecha["fecha"].dt.month
        dim_fecha["nombre_mes"] = dim_fecha["mes"].map(lambda m: meses[m - 1])
        dim_fecha["anio_mes"] = dim_fecha["fecha"].dt.to_period("M").astype(str)

    # 10) Tabla de hechos
    cols_hechos = [c for c in (
        "id_contrato", "id_entidad", "id_proveedor", "fecha_firma", "fecha_inicio",
        "fecha_fin", "anio", "mes", "anio_mes", "valor", "valor_pagado",
        "pct_ejecutado", "duracion_dias", "modalidad", "tipo_contrato", "estado",
        "categoria", "descripcion", "baja_competencia", "valor_atipico", "rango_valor",
        "origen_clasificacion",
    ) if c in df.columns]
    hechos = df[cols_hechos].copy()

    reporte.append(f"- Filas en la tabla de hechos: **{len(hechos):,}**")
    reporte.append(f"- Entidades únicas: **{len(dim_entidad):,}**")
    reporte.append(f"- Proveedores únicos: **{len(dim_proveedor):,}**")
    if len(hechos):
        reporte.append(f"- Valor total contratado: **${hechos['valor'].sum():,.0f} COP**")
        reporte.append(f"- Adjudicado por baja competencia: **{hechos.loc[hechos['baja_competencia'], 'valor'].sum() / hechos['valor'].sum():.1%}** del valor")

    return {
        "hechos": hechos,
        "dim_entidad": dim_entidad,
        "dim_proveedor": dim_proveedor,
        "dim_fecha": dim_fecha,
        "_reporte": reporte,
    }


def main() -> int:
    if not config.ARCHIVO_RAW.exists():
        print(f"[error] No existe {config.ARCHIVO_RAW}. Ejecuta primero: python src/extraer.py")
        return 1

    df_ti, n_total = cargar_ti_por_lotes(config.ARCHIVO_RAW)
    salida = construir(df_ti, n_total=n_total)

    salida["hechos"].to_csv(config.ARCHIVO_HECHOS, index=False, encoding="utf-8")
    salida["dim_entidad"].to_csv(config.ARCHIVO_DIM_ENTIDAD, index=False, encoding="utf-8")
    salida["dim_proveedor"].to_csv(config.ARCHIVO_DIM_PROVEEDOR, index=False, encoding="utf-8")
    salida["dim_fecha"].to_csv(config.ARCHIVO_DIM_FECHA, index=False, encoding="utf-8")

    lineas = ["# Reporte de calidad de datos", "",
              "Generado automáticamente por `src/transformar.py`.", ""]
    lineas += salida["_reporte"]
    config.ARCHIVO_CALIDAD.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    print("\n".join(salida["_reporte"]))
    print(f"\n[guardado] modelo en {config.DIR_PROCESSED}")
    print(f"[guardado] reporte de calidad en {config.ARCHIVO_CALIDAD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
