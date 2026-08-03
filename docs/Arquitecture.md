# Arquitectura — secop-ti-analytics

Documento para desarrolladores externos que quieran entender, reproducir o extender
el pipeline. Repositorio: https://github.com/Polvo07/secop-ti-analytics

## 1. Contexto y objetivo

El proyecto convierte los datos abiertos de contratación pública de TI en Colombia
(SECOP II, vía API Socrata) en un modelo analítico consultable desde Power BI.

Preguntas de negocio que el sistema responde:

1. ¿Cuánto gasta el Estado en tecnología y cómo evoluciona en el tiempo?
2. ¿Qué entidades concentran ese gasto?
3. ¿Qué proveedores lo capturan y qué tan concentrado está el mercado?
4. ¿Qué proporción se adjudica sin competencia abierta (contratación directa)?

No es un servicio en vivo: es un pipeline batch que un desarrollador ejecuta
localmente para regenerar el modelo y el tablero.

## 2. Diseño de alto nivel

```
API Socrata ──► extraer.py ──► data/raw/        CSV crudo, nunca se modifica
                                    │
                                    ▼
                          transformar.py ──► data/processed/   modelo estrella
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              explorar.py    generar_hallazgos.py   Power BI
              validación         README          dashboard.pbix
```

Cada script en `src/` hace una sola cosa y escribe su salida a disco antes de que
el siguiente empiece. Eso permite reejecutar una etapa (por ejemplo, ajustar el
filtro de clasificación en `transformar.py`) sin volver a descargar los 3.5
millones de registros crudos desde la API.

| Etapa | Script | Entrada | Salida |
|---|---|---|---|
| Extracción | `src/extraer.py` | API Socrata (SoQL) | `data/raw/*.csv` |
| Transformación | `src/transformar.py` | `data/raw/` | `data/processed/` (modelo estrella) |
| Validación | `src/explorar.py` | `data/processed/` | reporte en consola |
| Reporte | `src/generar_hallazgos.py` | `data/processed/` | cifras insertadas en `README.md` |
| Visualización | `dashboard.pbix` | `data/processed/` | tablero Power BI |
| Pruebas | `src/test_transformar.py` | fixtures sintéticos | resultado pass/fail |

## 3. Modelo de datos

Esquema estrella, elegido para que Power BI filtre rápido y las medidas DAX no
dependan de relaciones ambiguas:

```
              dim_fecha
                  │
dim_entidad ──► hechos_contratos ◄── dim_proveedor
```

| Tabla | Grano | Contenido |
|---|---|---|
| `hechos_contratos` | 1 fila = 1 contrato | Valor, fechas, modalidad, banderas de negocio |
| `dim_entidad` | 1 fila = 1 entidad | Nombre normalizado, NIT, departamento, orden, sector |
| `dim_proveedor` | 1 fila = 1 proveedor | Razón social normalizada, documento, si es pyme |
| `dim_fecha` | 1 fila = 1 día | Calendario continuo para inteligencia de tiempo |

La tabla de hechos no se versiona en Git (pesa ~53 MB); en su lugar se incluye
`data/muestra_hechos.csv`, una muestra aleatoria de 5,000 contratos con semilla
fija, suficiente para inspeccionar el modelo sin correr el pipeline completo.

## 4. Punto de integración externo

El único punto de integración con el exterior es la API Socrata / SoQL que expone
el dataset SECOP II — Contratos Electrónicos. `extraer.py` la consume con un
token opcional (`SOCRATA_APP_TOKEN`) para un límite de velocidad más alto. No hay
API propia que el proyecto exponga: el consumo es de afuera hacia adentro.

## 5. Decisiones clave y trade-offs

**Definición de "TI" — código UNSPSC + texto, con exclusiones.**
Filtro primario: segmento `43` completo (tecnologías de información y
telecomunicaciones) y solo la familia `8111` del segmento 81 (servicios
informáticos). Tomar el segmento 81 entero fue el primer intento y estaba mal:
ese segmento incluye ingeniería civil, e infló el universo a $57.5 billones con
contratos como la construcción de un aeropuerto. Restringir a 8111 más una lista
de exclusiones lo dejó en $25.8 billones. Cada contrato guarda en
`origen_clasificacion` si entró por código oficial o por coincidencia de texto,
para poder recalcular cualquier hallazgo con y sin los registros más frágiles.

**Esquema inferido sobre una muestra, no una fila.** La API omite campos vacíos
por registro, así que una sola fila subreporta columnas (81 de 85 detectadas al
probar con una). Se corrigió uniendo las llaves de 200 filas antes de construir
el filtro de fecha — si esa etapa falla silenciosamente, el pipeline descarga
todo el histórico del dataset sin aviso.

**Indicador reportado conservador por diseño.** El pipeline puede marcar tres
modalidades como de baja competencia (66.2%), pero el README solo reporta
contratación directa (49.3%): la mínima cuantía es un mecanismo legítimo para
compras pequeñas y contarla exageraría el hallazgo.

**Atípicos marcados, no eliminados.** Un contrato de TI por 50,000 COP es casi
seguro un error de digitación, pero borrarlo silenciosamente distorsiona los
conteos. Se marca con `valor_atipico`, dejando la decisión visible y su impacto
medible.

**Procesamiento por lotes.** 3.5 millones de filas × 85 columnas no caben
cómodamente en memoria (8–12 GB). `transformar.py` lee en bloques de 250,000
filas, conserva solo 20 de las 85 columnas y descarta lo que no es de TI antes de
acumular. Resultado: 119,113 filas finales.

**Cifras del README generadas, no escritas a mano.** `generar_hallazgos.py`
calcula los números desde `data/processed/` y los inserta entre marcadores
(`<!-- HALLAZGOS:INICIO -->` / `:FIN`), para que el texto no pueda contradecir a
su propia tabla cuando los datos cambien.

## 6. Validación

Tres verificaciones independientes protegen los hallazgos:

- **Pruebas automatizadas** (`python src/test_transformar.py`): 35 pruebas sin
  conexión sobre fixtures sintéticos que reproducen problemas reales del origen
  (duplicados, nulos, fechas invertidas, formatos numéricos mixtos).
- **Prueba de robustez**: el hallazgo principal se recalcula sobre universos
  alternativos (todo el dataset, solo respaldados por UNSPSC, sin atípicos). La
  variación es de ~2 puntos porcentuales, así que la conclusión no depende de
  cómo se recorte el universo.
- **Cruce entre herramientas**: el total en Power BI coincide con el calculado en
  Python por un camino distinto, validando relaciones y tipos del modelo.

## 7. Cómo levantarlo localmente

Requisitos: Python 3.10+, Power BI Desktop.

```bash
git clone https://github.com/Polvo07/secop-ti-analytics.git
cd secop-ti-analytics
pip install -r requirements.txt   # pandas, requests, numpy

export SOCRATA_APP_TOKEN="tu_token"   # opcional, mejora el límite de velocidad

python src/test_transformar.py        # verifica el entorno antes de descargar
python src/extraer.py --limite 5000   # prueba rápida
python src/extraer.py                 # descarga completa (~40 min)
python src/transformar.py             # genera el modelo en data/processed/
python src/explorar.py                # valida el universo y muestra hallazgos
python src/generar_hallazgos.py       # actualiza las cifras del README
```

Luego se abre `dashboard.pbix` en Power BI Desktop y se actualizan las fuentes
apuntando a `data/processed/`.

## 8. Limitaciones conocidas

- Los valores son montos **contratados**, no ejecutados.
- El último año del periodo analizado está incompleto y no es comparable con
  años anteriores.
- Solo el 36.7% de los contratos tiene respaldo de código UNSPSC oficial; el
  resto entra por coincidencia de texto sobre el objeto del contrato.
- Un contrato de TI que ningún funcionario describió con los términos esperados
  queda fuera del universo — no hay forma de detectarlo desde los datos.

## 9. Stack

Python (pandas, requests, numpy) · API Socrata / SoQL · Power BI · DAX · Git
