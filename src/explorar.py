"""
Paso 3 — Exploración y validación.

Responde dos cosas antes de construir el tablero:
  1. ¿El universo "TI" está bien delimitado, o se coló gasto que no es de TI?
  2. ¿Cuáles son los hallazgos que van al README?

Uso:
    python src/explorar.py
"""

import sys

import pandas as pd

import config


def cargar() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    hechos = pd.read_csv(config.ARCHIVO_HECHOS, low_memory=False)
    entidades = pd.read_csv(config.ARCHIVO_DIM_ENTIDAD)
    proveedores = pd.read_csv(config.ARCHIVO_DIM_PROVEEDOR)
    return hechos, entidades, proveedores


def cop(valor: float) -> str:
    """Formatea pesos en la escala que se lee de un vistazo."""
    if pd.isna(valor):
        return "n/d"
    for umbral, sufijo in ((1e12, "billones"), (1e9, "mil millones"), (1e6, "millones")):
        if abs(valor) >= umbral:
            return f"${valor / umbral:,.1f} {sufijo}"
    return f"${valor:,.0f}"


def titulo(texto: str) -> None:
    print(f"\n{'=' * 70}\n{texto}\n{'=' * 70}")


def validar_universo(h: pd.DataFrame) -> None:
    """
    Verifica de dónde salió cada contrato del universo TI.

    Importa porque el filtro tiene dos vías (código UNSPSC y palabras clave) y
    cada una falla distinto: el código puede venir mal diligenciado, y el texto
    puede arrastrar contratos que no son de tecnología.
    """
    titulo("1. VALIDACIÓN DEL UNIVERSO")

    codigo = (
        h["categoria"].astype(str).str.upper()
        .str.replace(r"^V\d+\.?", "", regex=True)
        .str.replace(r"\D", "", regex=True)
    )
    h = h.assign(codigo=codigo, familia=codigo.str[:4], segmento=codigo.str[:2])

    por_codigo = h["origen_clasificacion"] == "codigo"
    solo_texto = ~por_codigo
    print(f"Entraron por código UNSPSC : {int(por_codigo.sum()):>8,} "
          f"({por_codigo.mean():5.1%})  {cop(h.loc[por_codigo, 'valor'].sum())}")
    print(f"Entraron solo por texto    : {int(solo_texto.sum()):>8,} "
          f"({solo_texto.mean():5.1%})  {cop(h.loc[solo_texto, 'valor'].sum())}")
    print("\n  Los que entran solo por texto son los de mayor riesgo de falso")
    print("  positivo: no tienen respaldo de la clasificación oficial.")

    print("\nComposición por familia UNSPSC (4 dígitos):")
    resumen = (
        h.loc[por_codigo]
        .groupby("familia")
        .agg(contratos=("valor", "size"), valor=("valor", "sum"))
        .sort_values("valor", ascending=False)
    )
    nombres = {
        "4321": "4321 · Equipos y accesorios de cómputo",
        "4322": "4322 · Equipos y componentes de telecomunicaciones",
        "4323": "4323 · Software",
        "4319": "4319 · Dispositivos de comunicaciones",
        "8111": "8111 · Servicios informáticos",
    }
    total_cod = resumen["valor"].sum()
    for familia, fila in resumen.head(10).iterrows():
        etiqueta = nombres.get(familia, f"{familia} · otra")
        print(f"  {etiqueta:52s} {fila['contratos']:>8,.0f} contratos  "
              f"{cop(fila['valor']):>18s}  ({fila['valor']/total_cod:5.1%})")

    fuera = h.loc[por_codigo & ~h["segmento"].isin(["43", "81"])]
    if len(fuera):
        print(f"\n  [REVISAR] {len(fuera):,} contratos con código fuera de 43 y 81.")

    print("\n  Muestra de los mayores contratos que entraron SOLO por texto:")
    muestra = h.loc[solo_texto].nlargest(8, "valor")[["valor", "descripcion"]]
    for _, fila in muestra.iterrows():
        desc = str(fila["descripcion"])[:92].replace("\n", " ")
        print(f"    {cop(fila['valor']):>16s} · {desc}")
    print("\n  Si entre estos aparece gasto que claramente no es de TI, agrega")
    print("  el término correspondiente a EXCLUSIONES en src/config.py.")


def perfil_general(h: pd.DataFrame) -> None:
    titulo("2. PANORAMA GENERAL")

    total = h["valor"].sum()
    print(f"Contratos analizados      : {len(h):,}")
    print(f"Valor total contratado    : {cop(total)} COP")
    print(f"Valor promedio            : {cop(h['valor'].mean())}")
    print(f"Valor mediano             : {cop(h['valor'].median())}")
    print("\n  La brecha entre promedio y mediana muestra cuánto distorsionan")
    print("  unos pocos megacontratos. Para comunicar, la mediana es más honesta.")

    print("\nDistribución del valor por contrato:")
    for pct in (0.25, 0.50, 0.75, 0.90, 0.99):
        print(f"  Percentil {pct:.0%}: {cop(h['valor'].quantile(pct))}")

    print("\nValor por año de firma:")
    por_anio = h.groupby("anio").agg(contratos=("valor", "size"), valor=("valor", "sum"))
    for anio, fila in por_anio.iterrows():
        print(f"  {int(anio)}: {fila['contratos']:>7,.0f} contratos  {cop(fila['valor']):>18s}")
    print("\n  Nota: el último año está incompleto, no es comparable con los previos.")


def analisis_competencia(h: pd.DataFrame) -> None:
    """
    Desagrega el indicador de baja competencia.

    Es necesario porque agrupar todas las modalidades bajo una sola bandera
    exagera el hallazgo: la mínima cuantía es un mecanismo legítimo y eficiente
    para compras pequeñas, mientras que la contratación directa de alto valor
    es lo que de verdad merece atención.
    """
    titulo("3. COMPETENCIA EN LA ADJUDICACIÓN")

    total = h["valor"].sum()
    por_mod = (
        h.groupby("modalidad")
        .agg(contratos=("valor", "size"), valor=("valor", "sum"), mediana=("valor", "median"))
        .sort_values("valor", ascending=False)
    )

    print(f"{'Modalidad':<45s} {'Contratos':>10s} {'Valor':>18s} {'%':>7s} {'Mediana':>14s}")
    print("-" * 98)
    for modalidad, fila in por_mod.head(12).iterrows():
        nombre = str(modalidad)[:44]
        print(f"{nombre:<45s} {fila['contratos']:>10,.0f} {cop(fila['valor']):>18s} "
              f"{fila['valor']/total:>6.1%} {cop(fila['mediana']):>14s}")

    directa = por_mod[por_mod.index.astype(str).str.contains("irecta", na=False)]
    if len(directa):
        v = directa["valor"].sum()
        print(f"\nSolo contratación directa: {cop(v)} ({v/total:.1%} del valor total)")
        print("Este es el indicador defendible: excluye la mínima cuantía, que por")
        print("diseño aplica a compras pequeñas y no implica falta de competencia.")


def concentracion(h: pd.DataFrame, entidades: pd.DataFrame, proveedores: pd.DataFrame) -> None:
    titulo("4. CONCENTRACIÓN DE ENTIDADES Y PROVEEDORES")

    total = h["valor"].sum()

    ent = (
        h.groupby("id_entidad")
        .agg(contratos=("valor", "size"), valor=("valor", "sum"),
             pct_directa=("baja_competencia", "mean"))
        .merge(entidades[["id_entidad", "entidad_norm"]], on="id_entidad")
        .nlargest(10, "valor")
    )
    print("Top 10 entidades por valor contratado:")
    print(f"{'Entidad':<48s} {'Contratos':>10s} {'Valor':>16s} {'% baja comp.':>13s}")
    print("-" * 90)
    for _, f in ent.iterrows():
        print(f"{str(f['entidad_norm'])[:47]:<48s} {f['contratos']:>10,.0f} "
              f"{cop(f['valor']):>16s} {f['pct_directa']:>12.1%}")

    prov = (
        h.groupby("id_proveedor")
        .agg(contratos=("valor", "size"), valor=("valor", "sum"))
        .merge(proveedores[["id_proveedor", "proveedor_norm"]], on="id_proveedor")
        .sort_values("valor", ascending=False)
    )
    # Los registros sin proveedor identificable no son un contratista: aparecerían
    # en el ranking como si fueran una empresa real.
    sin_id = prov["proveedor_norm"] == "SIN INFORMACION"
    if sin_id.any():
        v = prov.loc[sin_id, "valor"].sum()
        print(f"\n  [calidad] {int(prov.loc[sin_id, 'contratos'].sum()):,} contratos por "
              f"{cop(v)} ({v/total:.1%}) no tienen proveedor identificable.")
        print("  Se excluyen del ranking, pero siguen contando en los totales.")
        prov = prov.loc[~sin_id]
    print("\nTop 10 proveedores por valor adjudicado:")
    print(f"{'Proveedor':<48s} {'Contratos':>10s} {'Valor':>16s} {'% del total':>13s}")
    print("-" * 90)
    for _, f in prov.head(10).iterrows():
        print(f"{str(f['proveedor_norm'])[:47]:<48s} {f['contratos']:>10,.0f} "
              f"{cop(f['valor']):>16s} {f['valor']/total:>12.2%}")

    print("\nConcentración del mercado:")
    for n in (10, 50, 100):
        pct = prov.head(n)["valor"].sum() / total
        print(f"  Los {n:>3d} mayores proveedores capturan {pct:.1%} del valor")
    print(f"  Total de proveedores: {len(prov):,}")


def robustez_del_hallazgo(h: pd.DataFrame) -> None:
    """
    Recalcula el indicador principal sobre el universo restringido.

    Es la prueba de fuego del análisis: si la conclusión cambia según se incluyan
    o no los contratos clasificados solo por texto, el hallazgo es frágil y hay
    que decirlo. Si se sostiene en ambos universos, es sólido y se puede afirmar
    con confianza.
    """
    titulo("5. ROBUSTEZ DEL HALLAZGO PRINCIPAL")

    def indicador(datos: pd.DataFrame) -> tuple[float, float, int]:
        if not len(datos):
            return 0.0, 0.0, 0
        total = datos["valor"].sum()
        es_directa = datos["modalidad"].astype(str).str.contains("irecta", case=False, na=False)
        return datos.loc[es_directa, "valor"].sum() / total, total, len(datos)

    escenarios = {
        "Universo completo": h,
        "Solo respaldados por UNSPSC": h[h["origen_clasificacion"] == "codigo"],
        "Excluyendo valores atípicos": h[~h["valor_atipico"]],
    }

    print(f"{'Escenario':<34s} {'Contratos':>11s} {'Valor total':>16s} {'% directa':>11s}")
    print("-" * 76)
    resultados = {}
    for nombre, datos in escenarios.items():
        pct, total, n = indicador(datos)
        resultados[nombre] = pct
        print(f"{nombre:<34s} {n:>11,} {cop(total):>16s} {pct:>10.1%}")

    brecha = max(resultados.values()) - min(resultados.values())
    print()
    if brecha <= 0.05:
        print(f"  El indicador varía apenas {brecha:.1%} entre escenarios: el hallazgo")
        print("  es robusto y puede afirmarse sin condicionarlo.")
    else:
        print(f"  El indicador varía {brecha:.1%} entre escenarios. Reporta el rango,")
        print("  no un solo número, y explica de qué depende la diferencia.")


def main() -> int:
    if not config.ARCHIVO_HECHOS.exists():
        print(f"[error] Falta {config.ARCHIVO_HECHOS}. Ejecuta antes: python src/transformar.py")
        return 1

    hechos, entidades, proveedores = cargar()
    validar_universo(hechos)
    perfil_general(hechos)
    analisis_competencia(hechos)
    concentracion(hechos, entidades, proveedores)
    robustez_del_hallazgo(hechos)

    titulo("SIGUIENTE PASO")
    print("Revisa la sección 1: si entre los contratos que entraron solo por texto")
    print("aparece gasto que claramente no es de TI, agrega el término a")
    print("EXCLUSIONES en src/config.py y vuelve a correr transformar.py.")
    print("Si el universo ya te parece limpio, la sección 5 te dice qué tan")
    print("firme es tu conclusión y con esos números escribes el README.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
