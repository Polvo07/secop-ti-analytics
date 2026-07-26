# Radiografía del gasto público en TI en Colombia

Análisis end-to-end de la contratación pública de tecnología en Colombia a partir
de datos abiertos oficiales: extracción vía API, limpieza reproducible en Python,
modelo dimensional y tablero en Power BI.

**Fuente:** [SECOP II – Contratos Electrónicos](https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II-Contratos-Electr-nicos/jbjy-vk9h),
Colombia Compra Eficiente · Portal Nacional de Datos Abiertos.

---

## El problema

El Estado colombiano publica cada contrato que firma, pero los datos crudos son
prácticamente inutilizables para responder preguntas de negocio: más de 100
columnas, nombres de entidades y proveedores escritos de formas distintas para el
mismo actor, categorías sin diligenciar y valores en formatos inconsistentes.

Este proyecto convierte ese ruido en respuestas concretas:

1. ¿Cuánto gasta el Estado en tecnología y cómo evoluciona en el tiempo?
2. ¿Qué entidades concentran ese gasto?
3. ¿Qué proveedores lo capturan y qué tan concentrado está el mercado?
4. ¿Qué proporción se adjudica por modalidades de baja competencia?
5. ¿Cómo se distribuye geográficamente y por tamaño de contrato?

La pregunta 4 es la más relevante: la contratación directa es legal y muchas veces
justificada, pero una concentración alta en una entidad específica es una señal que
vale la pena mirar de cerca.

---

## Hallazgos

<!-- HALLAZGOS:INICIO -->

*Cifras generadas automáticamente por `src/generar_hallazgos.py` el 26/07/2026. Periodo analizado: 2023–2026.*

| Indicador | Valor |
|---|---|
| Contratos de TI analizados | 119,113 |
| Valor total contratado | $25.8 billones COP |
| Valor mediano por contrato | $29.6 millones |
| **Adjudicado por contratación directa** | **49.3%** |
| Entidades contratantes | 2,912 |
| Proveedores | 44,287 |
| Participación de los 10 mayores proveedores | 21.7% |
| Contratos respaldados por código UNSPSC oficial | 36.7% |

### 1. Casi la mitad del gasto en TI se adjudica sin competencia abierta

De los $25.8 billones contratados en tecnología, el **49.3%** se adjudicó por contratación directa. La cifra excluye deliberadamente la mínima cuantía, que por diseño aplica a compras pequeñas y no implica ausencia de competencia.

El resultado se sostiene al recortar el universo de distintas formas:

| Escenario | Contratos | Valor | % contratación directa |
|---|---:|---:|---:|
| Universo completo | 119,113 | $25.8 billones | 49.3% |
| Solo respaldados por código UNSPSC | 43,697 | $19.3 billones | 47.4% |
| Excluyendo valores atípicos | 118,694 | $25.8 billones | 49.3% |

La variación entre escenarios es de apenas 1.9%, así que el hallazgo no depende de cómo se delimite el universo.

### 2. El mercado está mucho menos concentrado de lo esperado

Participan **44,287 proveedores** distintos y los diez mayores captan apenas el **21.7%** del valor. Para un sector con altas barreras técnicas, es una dispersión notable: el gasto se reparte en miles de contratos pequeños en lugar de concentrarse en unos pocos grandes contratistas.

La mediana de $29.6 millones frente a un promedio de $217.0 millones confirma el patrón: unos pocos megacontratos elevan el promedio, pero el contrato típico es pequeño.

### 3. La concentración de la contratación directa varía mucho por entidad

| Entidad | Contratos | Valor |
|---|---:|---:|
| RNEC | 143 | $2.0 billones |
| RAMA JUDICIAL DIRECCION EJECUTIVA DE ADMINISTRACION JUDICIAL | 181 | $873.7 mil millones |
| SENA DIRECCION GENERAL | 70 | $790.1 mil millones |
| FONDO NACIONAL DEL AHORRO | 113 | $731.6 mil millones |
| MINISTERIO DEL INTERIOR | 300 | $620.2 mil millones |

El porcentaje de adjudicación directa no es uniforme entre entidades. Esa dispersión, más que el promedio nacional, es lo que señala dónde vale la pena mirar de cerca.

<!-- HALLAZGOS:FIN -->

---

## Arquitectura

```
API Socrata  ──►  extraer.py  ──►  data/raw/       (CSV crudo, sin tocar)
                                        │
                                        ▼
                              transformar.py  ──►  data/processed/  (modelo estrella)
                                        │
                                        ▼
                                  Power BI  ──►  dashboard.pbix
```

**Modelo dimensional** (esquema estrella, para que Power BI filtre rápido y las
medidas DAX no dependan de relaciones ambiguas):

```
              dim_fecha
                  │
dim_entidad ──► hechos_contratos ◄── dim_proveedor
```

| Tabla | Grano | Descripción |
|---|---|---|
| `hechos_contratos` | 1 fila = 1 contrato | Valor, fechas, modalidad, banderas de negocio |
| `dim_entidad` | 1 fila = 1 entidad | Nombre normalizado, NIT, departamento, orden, sector |
| `dim_proveedor` | 1 fila = 1 proveedor | Razón social normalizada, documento, si es pyme |
| `dim_fecha` | 1 fila = 1 día | Calendario continuo para inteligencia de tiempo |

---

## Decisiones de diseño

Las decisiones no obvias, que es donde está el criterio real del proyecto:

**El esquema no se asume, se consulta.** SECOP II ha cambiado nombres de columnas
entre versiones. `extraer.py` pide una fila primero para leer el esquema real, y
`transformar.py` resuelve cada campo lógico contra varios nombres candidatos. Si
mañana cambian `fecha_de_firma` por `fecha_firma_contrato`, el pipeline sigue
corriendo.

**"TI" se define por dos vías, no una.** El filtro primario es el segmento UNSPSC
(43 = tecnologías de información y telecomunicaciones, 81 = servicios de
ingeniería y tecnología). Pero esa categoría llega vacía o mal diligenciada en una
fracción de los registros, así que se complementa con búsqueda de términos en la
descripción del objeto contractual. El reporte de calidad cuantifica cuánto aporta
cada vía.

**Los atípicos se marcan, no se borran.** Un contrato de TI por 50.000 COP es casi
seguro un error de digitación, pero borrarlo silenciosamente distorsiona los
conteos. Se marca con `valor_atipico` y el tablero permite excluirlos con un filtro,
de modo que la decisión sea visible y reversible.

**Los nombres se normalizan antes de agrupar.** "TECNOLOGÍA S.A.S.", "Tecnologia
SAS" y "TECNOLOGIA S A S" son el mismo proveedor. Sin normalizar (tildes,
puntuación, sufijos societarios), cualquier ranking de proveedores es falso.

**Las fechas invertidas anulan la duración, no la vuelven negativa.** Hay contratos
con fecha de fin anterior a la de inicio. Propagar un número negativo contamina
cualquier promedio; dejarlo nulo lo excluye correctamente del cálculo.

**Se usa CSV y no Parquet.** Parquet sería más eficiente, pero CSV es legible desde
cualquier herramienta sin dependencias extra y Power BI lo consume nativamente. A
este volumen la diferencia de rendimiento no justifica la fricción.

---

## Cómo reproducirlo

Requisitos: Python 3.10+ y Power BI Desktop.

```bash
git clone https://github.com/Polvo07/secop-ti-analytics.git
cd secop-ti-analytics
pip install -r requirements.txt

# (opcional pero recomendado) token gratuito de Socrata para mejor límite de tasa
export SOCRATA_APP_TOKEN="tu_token"

python src/extraer.py --limite 5000   # prueba rápida
python src/extraer.py                 # descarga completa
python src/transformar.py             # genera el modelo en data/processed/
python src/test_transformar.py        # pruebas del pipeline
```

Luego se abre `dashboard.pbix` y se actualizan las fuentes apuntando a
`data/processed/`.

---

## Calidad de datos

El pipeline incluye 21 pruebas automatizadas que corren sin conexión (usan un
conjunto sintético con los problemas reales del origen: duplicados, valores nulos,
fechas invertidas, nombres con y sin tilde, categorías vacías, importes en formato
colombiano y anglosajón).

```bash
python src/test_transformar.py
```

Cada ejecución de `transformar.py` genera además `docs/reporte_calidad.md` con
cuántos registros se descartaron y por qué motivo.

---

## Stack

Python (pandas, requests) · API Socrata · Power BI · DAX · Git

---

## Autor

**Andrés Felipe Domínguez Pallares** — Estudiante de Ingeniería Multimedia,
Universidad Simón Bolívar.
[LinkedIn](https://www.linkedin.com/in/andres-dominguez-4877a51b8/) ·
[GitHub](https://github.com/Polvo07)
