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
# SECOP II clasifica con UNSPSC en `codigo_de_categoria_principal`, con formato
# tipo "V1.43.23.15.00", donde los dígitos son: segmento.familia.clase.producto.
#
# Se filtra por prefijo, a la profundidad que cada caso requiere:
#   43   = segmento completo: equipos de cómputo, telecomunicaciones y software.
#          Todo el segmento es tecnología, así que se toma entero.
#   8111 = SOLO la familia de servicios informáticos dentro del segmento 81
#          (desarrollo de software, centros de datos, administración de sistemas).
#
# El segmento 81 completo NO sirve: incluye ingeniería civil y ambiental. Al
# usarlo entero se colaban obras como la construcción del Aeropuerto del Café
# por $634 mil millones, que inflaban el universo con gasto que no es de TI.
PREFIJOS_UNSPSC_TI = ["43", "8111"]

# Respaldo por palabra clave sobre la descripción del proceso. Se usa porque la
# categoría UNSPSC llega vacía o mal diligenciada en una fracción de registros.
# Los términos son específicos a propósito: "redes" a secas capturaba contratos
# de manejo de "redes sociales", que no son de TI.
PALABRAS_CLAVE_TI = [
    "software", "hardware", "licenciamiento de software", "licencias de software",
    "ciberseguridad", "seguridad informatica", "seguridad de la informacion",
    "infraestructura tecnologica", "servidores", "datacenter", "data center",
    "centro de datos", "computacion en la nube", "servicios en la nube",
    "hosting", "computadores", "equipos de computo", "equipos de computacion",
    "desarrollo de software", "aplicativo", "aplicaciones moviles",
    "sistema de informacion", "sistemas de informacion",
    "mesa de ayuda", "soporte tecnico",
    "servicio de conectividad", "servicios de conectividad", "conectividad a internet",
    "redes de datos", "red de datos", "cableado estructurado",
    "telecomunicaciones", "fibra optica", "base de datos", "bases de datos",
    "canal de internet", "servicio de internet",
]

# Términos que descalifican un contrato aunque haya coincidido por palabra clave.
# Evitan los falsos positivos más frecuentes: obra civil que menciona "redes"
# (de acueducto), y comunicaciones que menciona "redes sociales".
EXCLUSIONES = [
    "redes sociales", "community manager", "publicidad", "pauta digital",
    "obra civil", "obras civiles", "construccion de", "pavimento", "pavimentacion",
    "acueducto", "alcantarillado", "interventoria a la obra", "interventoria de obra",
    "lado aire", "malla vial", "puente vehicular", "mantenimiento de vias",
    # Convenios interadministrativos: su objeto es tan amplio ("aunar esfuerzos
    # técnicos, económicos, humanos y logísticos para...") que mencionan
    # tecnología de pasada. Contarlos como gasto en TI no es defendible.
    "aunar esfuerzos",
    # Detectados al revisar los mayores contratos clasificados solo por texto
    "restauracion ecologica", "conectividad ecologica", "dispositivos medicos",
    "mandato sin representacion",
]

# Textos de relleno que aparecen en el campo de proveedor cuando el registro
# quedó incompleto. Sin depurarlos, "VALOR PROVEEDOR" figura entre los diez
# mayores contratistas del país con casi medio billón de pesos.
PROVEEDORES_INVALIDOS = [
    "VALOR PROVEEDOR", "NO DEFINIDO", "NO APLICA", "POR DEFINIR",
    "SIN INFORMACION", "NA", "N A", "PENDIENTE", "NO REGISTRA",
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
