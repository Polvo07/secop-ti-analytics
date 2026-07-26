"""
Configuración central del proyecto.

Fuente: SECOP II - Contratos Electrónicos (Colombia Compra Eficiente)
Portal:  https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II-Contratos-Electr-nicos/jbjy-vk9h
API:     https://dev.socrata.com/foundry/www.datos.gov.co/jbjy-vk9h
"""

from pathlib import Path

# --- Fuente de datos ---------------------------------------------------------
DOMINIO = "www.datos.gov.co"
DATASET_ID = "jbjy-vk9h"
API_URL = f"https://{DOMINIO}/resource/{DATASET_ID}.json"

# Token opcional de Socrata. Sin token la API funciona, pero con límite de tasa
# más estricto. Se registra gratis en https://evergreen.data.socrata.com/signup
# Si lo tienes, expórtalo así:  export SOCRATA_APP_TOKEN="tu_token"
APP_TOKEN_ENV = "SOCRATA_APP_TOKEN"

# --- Ventana de análisis -----------------------------------------------------
# Se analizan contratos firmados desde esta fecha. Ajusta si quieres más historia.
FECHA_INICIO = "2023-01-01"

# --- Definición del universo "TI" -------------------------------------------
# SECOP II clasifica con UNSPSC en `codigo_de_categoria_principal`,
# con formato tipo "V1.43.23.15.00". El segmento (2 dígitos tras "V1.") define
# la familia de bienes/servicios.
#   43 = Difusión de tecnologías de información y telecomunicaciones
#   81 = Servicios basados en ingeniería, investigación y tecnología
SEGMENTOS_UNSPSC_TI = ["43", "81"]

# Respaldo por palabra clave sobre la descripción del proceso. Se usa porque la
# categoría UNSPSC llega vacía o mal diligenciada en una fracción de registros.
PALABRAS_CLAVE_TI = [
    "software", "hardware", "licenciamiento", "licencias",
    "ciberseguridad", "seguridad informatica", "seguridad de la informacion",
    "infraestructura tecnologica", "servidores", "datacenter", "data center",
    "nube", "cloud", "hosting", "computadores", "equipos de computo",
    "desarrollo de software", "aplicativo", "sistema de informacion",
    "mesa de ayuda", "soporte tecnico", "conectividad", "redes",
    "telecomunicaciones", "internet", "fibra optica", "base de datos",
]

# --- Umbrales de negocio -----------------------------------------------------
# Contratos por debajo de este valor se marcan como atípicos (suelen ser errores
# de digitación o registros de prueba), no se eliminan: se marcan para revisión.
VALOR_MINIMO_RAZONABLE = 1_000_000  # 1 millón COP

# Modalidades consideradas de menor competencia (insumo del indicador de riesgo)
MODALIDADES_BAJA_COMPETENCIA = [
    "contratacion directa",
    "contratacion regimen especial",
    "minima cuantia",
]

# --- Rutas -------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"
DIR_DOCS = RAIZ / "docs"

ARCHIVO_RAW = DIR_RAW / "secop_ti_raw.csv"
ARCHIVO_HECHOS = DIR_PROCESSED / "hechos_contratos.csv"
ARCHIVO_DIM_ENTIDAD = DIR_PROCESSED / "dim_entidad.csv"
ARCHIVO_DIM_PROVEEDOR = DIR_PROCESSED / "dim_proveedor.csv"
ARCHIVO_DIM_FECHA = DIR_PROCESSED / "dim_fecha.csv"
ARCHIVO_CALIDAD = DIR_DOCS / "reporte_calidad.md"

for _d in (DIR_RAW, DIR_PROCESSED, DIR_DOCS):
    _d.mkdir(parents=True, exist_ok=True)
