# Medidas DAX para el tablero

Se pegan en Power BI con **Modelado → Nueva medida** (una por una).
Antes de crearlas: marcar `dim_fecha` como tabla de fechas
(*Modelado → Marcar como tabla de fechas → campo `fecha`*), o la inteligencia de
tiempo no funciona.

## Relaciones del modelo

| Desde | Hacia | Cardinalidad |
|---|---|---|
| `hechos_contratos[id_entidad]` | `dim_entidad[id_entidad]` | muchos a uno |
| `hechos_contratos[id_proveedor]` | `dim_proveedor[id_proveedor]` | muchos a uno |
| `hechos_contratos[fecha_firma]` | `dim_fecha[fecha]` | muchos a uno |

---

## Medidas base

```dax
Valor Contratado =
SUM ( hechos_contratos[valor] )
```

```dax
Total Contratos =
COUNTROWS ( hechos_contratos )
```

```dax
Valor Promedio =
DIVIDE ( [Valor Contratado], [Total Contratos] )
```

La mediana comunica mejor que el promedio cuando unos pocos megacontratos
distorsionan la distribución. Conviene mostrar las dos juntas:

```dax
Valor Mediano =
MEDIAN ( hechos_contratos[valor] )
```

```dax
Entidades Contratantes =
DISTINCTCOUNT ( hechos_contratos[id_entidad] )
```

```dax
Proveedores =
DISTINCTCOUNT ( hechos_contratos[id_proveedor] )
```

---

## Indicador de competencia

El indicador central del análisis: qué proporción del dinero se adjudica por
modalidades con menor competencia.

```dax
Valor Baja Competencia =
CALCULATE (
    [Valor Contratado],
    hechos_contratos[baja_competencia] = TRUE ()
)
```

```dax
% Baja Competencia =
DIVIDE ( [Valor Baja Competencia], [Valor Contratado] )
```

Formato: porcentaje, 1 decimal.

---

## Concentración de proveedores

Cuánto del mercado capturan los 10 proveedores más grandes. Por encima de ~60% el
mercado está concentrado.

```dax
Valor Top 10 Proveedores =
VAR TopProv =
    TOPN ( 10, ALLSELECTED ( dim_proveedor[proveedor_norm] ), [Valor Contratado], DESC )
RETURN
    CALCULATE ( [Valor Contratado], KEEPFILTERS ( TopProv ) )
```

```dax
% Concentración Top 10 =
DIVIDE ( [Valor Top 10 Proveedores], CALCULATE ( [Valor Contratado], ALLSELECTED ( dim_proveedor ) ) )
```

---

## Ejecución presupuestal

```dax
Valor Pagado =
SUM ( hechos_contratos[valor_pagado] )
```

```dax
% Ejecución =
DIVIDE ( [Valor Pagado], [Valor Contratado] )
```

---

## Inteligencia de tiempo

```dax
Valor Año Anterior =
CALCULATE ( [Valor Contratado], SAMEPERIODLASTYEAR ( dim_fecha[fecha] ) )
```

```dax
Variación Anual % =
VAR Anterior = [Valor Año Anterior]
RETURN
    IF ( NOT ISBLANK ( Anterior ), DIVIDE ( [Valor Contratado] - Anterior, Anterior ) )
```

El `IF` evita mostrar un crecimiento infinito en el primer año del análisis, donde
no hay periodo de comparación.

```dax
Valor Acumulado Año =
TOTALYTD ( [Valor Contratado], dim_fecha[fecha] )
```

---

## Medida de contexto para títulos dinámicos

Sirve para que el título de la página refleje el filtro activo:

```dax
Título Dinámico =
VAR Entidades = SELECTEDVALUE ( dim_entidad[entidad_norm], "todas las entidades" )
VAR Anios =
    IF (
        HASONEVALUE ( dim_fecha[anio] ),
        FORMAT ( SELECTEDVALUE ( dim_fecha[anio] ), "0" ),
        "el periodo completo"
    )
RETURN
    "Contratación de TI — " & Entidades & " — " & Anios
```

---

## Estructura sugerida del tablero

**Página 1 — Panorama**
Tarjetas con Valor Contratado, Total Contratos, Valor Mediano, % Baja Competencia ·
línea de evolución mensual · barras de top 10 entidades · mapa por departamento.

**Página 2 — Proveedores**
Top 20 proveedores por valor · % Concentración Top 10 · distribución pyme vs. no
pyme · dispersión valor contra número de contratos por proveedor.

**Página 3 — Modalidades y riesgo**
% Baja Competencia por entidad (ordenado descendente) · matriz modalidad contra
rango de valor · evolución del % de contratación directa en el tiempo.

Un detalle que suma: en cada página, un cuadro de texto con la conclusión en una
frase. Un tablero que dice qué significa lo que muestra vale mucho más que uno que
solo muestra.
