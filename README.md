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

> Esta sección se completa al ejecutar el pipeline. Los números salen de
> `docs/reporte_calidad.md`, que se genera automáticamente.

| Indicador | Valor |
|---|---|
| Contratos de TI analizados | _pendiente_ |
| Valor total contratado | _pendiente_ |
| % adjudicado por baja competencia | _pendiente_ |
| Entidades contratantes | _pendiente_ |
| Proveedores | _pendiente_ |
| Participación de los 10 mayores proveedores | _pendiente_ |

**Conclusiones:**

1. _pendiente_
2. _pendiente_
3. _pendiente_

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
