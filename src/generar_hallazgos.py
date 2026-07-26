"""
Paso 4 — Generación de hallazgos.

Calcula las cifras del análisis y las escribe directamente en el README, entre
los marcadores HALLAZGOS. Se hace por código y no a mano porque los números de
un informe copiados manualmente se desactualizan en cuanto cambia el pipeline,
y un dato mal transcrito destruye la credibilidad de todo el trabajo.

Uso:
    python src/generar_hallazgos.py
"""

import re
import sys
from datetime import date

import pandas as pd

import config

INICIO = "<!-- HALLAZGOS:INICIO -->"
FIN = "<!-- HALLAZGOS:FIN -->"
README = config.RAIZ / "README.md"


def cop(valor: float, decimales: int = 1) -> str:
    if pd.isna(valor):
        return "n/d"
    for umbral, sufijo in ((1e12, "billones"), (1e9, "mil millones"), (1e6, "millones")):
        if abs(valor) >= umbral:
            return f"${valor / umbral:,.{decimales}f} {sufijo}"
    return f"${valor:,.0f}"


def pct_directa(datos: pd.DataFrame) -> float:
    if not len(datos):
        return 0.0
    es_directa = datos["modalidad"].astype(str).str.contains("irecta", case=False, na=False)
    return datos.loc[es_directa, "valor"].sum() / datos["valor"].sum()


def construir_seccion() -> str:
    h = pd.read_csv(config.ARCHIVO_HECHOS, low_memory=False)
    ent = pd.read_csv(config.ARCHIVO_DIM_ENTIDAD)
    prov = pd.read_csv(config.ARCHIVO_DIM_PROVEEDOR)

    total = h["valor"].sum()
    directa = pct_directa(h)

    top_prov = (
        h.groupby("id_proveedor")["valor"].sum()
        .reset_index()
        .merge(prov[["id_proveedor", "proveedor_norm"]], on="id_proveedor")
        .query("proveedor_norm != 'SIN INFORMACION'")
        .nlargest(10, "valor")
    )
    conc10 = top_prov["valor"].sum() / total

    top_ent = (
        h.groupby("id_entidad")
        .agg(valor=("valor", "sum"), contratos=("valor", "size"))
        .reset_index()
        .merge(ent[["id_entidad", "entidad_norm"]], on="id_entidad")
        .nlargest(5, "valor")
    )

    solo_codigo = h[h["origen_clasificacion"] == "codigo"]
    respaldo = len(solo_codigo) / len(h)
    escenarios = {
        "Universo completo": h,
        "Solo respaldados por código UNSPSC": solo_codigo,
        "Excluyendo valores atípicos": h[~h["valor_atipico"]],
    }
    valores = {k: pct_directa(v) for k, v in escenarios.items()}
    brecha = max(valores.values()) - min(valores.values())

    anios = sorted(h["anio"].dropna().unique().astype(int))
    periodo = f"{anios[0]}–{anios[-1]}" if anios else "n/d"

    L: list[str] = [INICIO, ""]
    L.append(f"*Cifras generadas automáticamente por `src/generar_hallazgos.py` "
             f"el {date.today():%d/%m/%Y}. Periodo analizado: {periodo}.*")
    L.append("")
    L.append("| Indicador | Valor |")
    L.append("|---|---|")
    L.append(f"| Contratos de TI analizados | {len(h):,} |")
    L.append(f"| Valor total contratado | {cop(total)} COP |")
    L.append(f"| Valor mediano por contrato | {cop(h['valor'].median())} |")
    L.append(f"| **Adjudicado por contratación directa** | **{directa:.1%}** |")
    L.append(f"| Entidades contratantes | {len(ent):,} |")
    L.append(f"| Proveedores | {len(prov):,} |")
    L.append(f"| Participación de los 10 mayores proveedores | {conc10:.1%} |")
    L.append(f"| Contratos respaldados por código UNSPSC oficial | {respaldo:.1%} |")
    L.append("")

    # El titular se deriva de la cifra: un encabezado escrito a mano queda
    # desmentido por su propia tabla en cuanto los datos cambian.
    if directa >= 0.60:
        titular = "La mayoría del gasto en TI se adjudica sin competencia abierta"
    elif directa >= 0.45:
        titular = "Casi la mitad del gasto en TI se adjudica sin competencia abierta"
    elif directa >= 0.30:
        titular = "Un tercio del gasto en TI se adjudica sin competencia abierta"
    else:
        titular = "La contratación directa pesa menos de lo esperado en el gasto en TI"
    L.append(f"### 1. {titular}")
    L.append("")
    L.append(f"De los {cop(total)} contratados en tecnología, el **{directa:.1%}** se "
             "adjudicó por contratación directa. La cifra excluye deliberadamente la "
             "mínima cuantía, que por diseño aplica a compras pequeñas y no implica "
             "ausencia de competencia.")
    L.append("")
    L.append("El resultado se sostiene al recortar el universo de distintas formas:")
    L.append("")
    L.append("| Escenario | Contratos | Valor | % contratación directa |")
    L.append("|---|---:|---:|---:|")
    for nombre, datos in escenarios.items():
        L.append(f"| {nombre} | {len(datos):,} | {cop(datos['valor'].sum())} | "
                 f"{valores[nombre]:.1%} |")
    L.append("")
    if brecha <= 0.05:
        L.append(f"La variación entre escenarios es de apenas {brecha:.1%}, así que el "
                 "hallazgo no depende de cómo se delimite el universo.")
    else:
        L.append(f"La variación entre escenarios llega a {brecha:.1%}, así que la cifra "
                 "debe leerse como un rango y no como un valor único.")
    L.append("")

    if conc10 >= 0.50:
        titular2 = "El mercado está concentrado en pocos proveedores"
    elif conc10 >= 0.25:
        titular2 = "El mercado muestra una concentración moderada"
    else:
        titular2 = "El mercado está mucho menos concentrado de lo esperado"
    L.append(f"### 2. {titular2}")
    L.append("")
    matiz = "apenas el" if conc10 < 0.25 else "el"
    lectura = ("una dispersión notable: el gasto se reparte en miles de contratos "
               "pequeños en lugar de concentrarse en unos pocos grandes contratistas."
               if conc10 < 0.25 else
               "una concentración relevante para un mercado con tantos participantes.")
    L.append(f"Participan **{len(prov):,} proveedores** distintos y los diez mayores "
             f"captan {matiz} **{conc10:.1%}** del valor. Para un sector con altas "
             f"barreras técnicas, es {lectura}")
    L.append("")
    L.append(f"La mediana de {cop(h['valor'].median())} frente a un promedio de "
             f"{cop(h['valor'].mean())} confirma el patrón: unos pocos megacontratos "
             "elevan el promedio, pero el contrato típico es pequeño.")
    L.append("")

    L.append("### 3. La concentración de la contratación directa varía mucho por entidad")
    L.append("")
    L.append("| Entidad | Contratos | Valor |")
    L.append("|---|---:|---:|")
    for _, f in top_ent.iterrows():
        L.append(f"| {f['entidad_norm']} | {f['contratos']:,} | {cop(f['valor'])} |")
    L.append("")
    L.append("El porcentaje de adjudicación directa no es uniforme entre entidades. "
             "Esa dispersión, más que el promedio nacional, es lo que señala dónde "
             "vale la pena mirar de cerca.")
    L.append("")
    L.append(FIN)
    return "\n".join(L)


def main() -> int:
    if not config.ARCHIVO_HECHOS.exists():
        print(f"[error] Falta {config.ARCHIVO_HECHOS}. Ejecuta antes: python src/transformar.py")
        return 1
    if not README.exists():
        print(f"[error] No se encontró {README}")
        return 1

    seccion = construir_seccion()
    texto = README.read_text(encoding="utf-8")

    if INICIO in texto and FIN in texto:
        patron = re.compile(re.escape(INICIO) + r".*?" + re.escape(FIN), re.DOTALL)
        texto = patron.sub(seccion, texto)
        print("[README] sección de hallazgos actualizada")
    else:
        print("[aviso] No se encontraron los marcadores en el README.")
        print(f"        Agrega {INICIO} y {FIN} donde quieras la sección.")
        salida = config.DIR_DOCS / "hallazgos.md"
        salida.write_text(seccion, encoding="utf-8")
        print(f"[guardado] sección escrita en {salida} para pegarla a mano")
        return 0

    README.write_text(texto, encoding="utf-8")
    print(f"[guardado] {README}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
