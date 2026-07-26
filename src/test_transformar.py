"""
Pruebas del pipeline de transformación.

No dependen de la API: generan un CSV sintético con el esquema de SECOP II,
incluyendo los casos sucios que el pipeline debe manejar (duplicados, valores
nulos, fechas invertidas, nombres con y sin tilde, categorías vacías).

Uso:
    python src/test_transformar.py
"""

import sys

import numpy as np
import pandas as pd

import config
from transformar import a_numero, construir, marcar_ti, normalizar_nombre, resolver_columnas


def muestra_sintetica() -> pd.DataFrame:
    """Construye un caso de prueba con problemas de calidad deliberados."""
    filas = [
        # TI por categoría UNSPSC (segmento 43)
        dict(id_contrato="C-001", nombre_entidad="MINISTERIO DE SALUD",
             nit_entidad="899999", departamento="Bogotá", ciudad="Bogotá",
             orden="Nacional", sector="Salud",
             descripcion_del_proceso="Adquisicion de equipos",
             codigo_de_categoria_principal="V1.43.21.15.00",
             tipo_de_contrato="Compraventa", modalidad_de_contratacion="Licitación pública",
             estado_contrato="En ejecución", fecha_de_firma="2024-03-15",
             fecha_de_inicio_del_contrato="2024-04-01", fecha_de_fin_del_contrato="2024-12-31",
             valor_del_contrato="1.500.000.000", valor_pagado="750000000",
             proveedor_adjudicado="TECNOLOGIA S.A.S.", documento_proveedor="900111",
             es_pyme="No"),
        # TI por palabra clave, categoría vacía
        dict(id_contrato="C-002", nombre_entidad="Ministerio de Salud",  # mismo, distinta grafía
             nit_entidad="899999", departamento="Bogotá", ciudad="Bogotá",
             orden="Nacional", sector="Salud",
             descripcion_del_proceso="Servicio de ciberseguridad perimetral",
             codigo_de_categoria_principal="",
             tipo_de_contrato="Prestación de servicios",
             modalidad_de_contratacion="Contratación directa",
             estado_contrato="En ejecución", fecha_de_firma="2024-06-20",
             fecha_de_inicio_del_contrato="2024-07-01", fecha_de_fin_del_contrato="2025-06-30",
             valor_del_contrato="800000000", valor_pagado="0",
             proveedor_adjudicado="TECNOLOGIA SAS", documento_proveedor="900111",
             es_pyme="No"),
        # NO es TI: debe quedar fuera
        dict(id_contrato="C-003", nombre_entidad="ALCALDIA DE CALI",
             nit_entidad="890399", departamento="Valle del Cauca", ciudad="Cali",
             orden="Territorial", sector="Otros",
             descripcion_del_proceso="Suministro de alimentos escolares",
             codigo_de_categoria_principal="V1.50.19.20.00",
             tipo_de_contrato="Suministro", modalidad_de_contratacion="Licitación pública",
             estado_contrato="Terminado", fecha_de_firma="2024-02-10",
             fecha_de_inicio_del_contrato="2024-03-01", fecha_de_fin_del_contrato="2024-11-30",
             valor_del_contrato="2000000000", valor_pagado="2000000000",
             proveedor_adjudicado="ALIMENTOS LTDA", documento_proveedor="800222",
             es_pyme="Sí"),
        # Duplicado exacto de C-001 (debe eliminarse)
        dict(id_contrato="C-001", nombre_entidad="MINISTERIO DE SALUD",
             nit_entidad="899999", departamento="Bogotá", ciudad="Bogotá",
             orden="Nacional", sector="Salud",
             descripcion_del_proceso="Adquisicion de equipos",
             codigo_de_categoria_principal="V1.43.21.15.00",
             tipo_de_contrato="Compraventa", modalidad_de_contratacion="Licitación pública",
             estado_contrato="En ejecución", fecha_de_firma="2024-03-15",
             fecha_de_inicio_del_contrato="2024-04-01", fecha_de_fin_del_contrato="2024-12-31",
             valor_del_contrato="1500000000", valor_pagado="750000000",
             proveedor_adjudicado="TECNOLOGIA S.A.S.", documento_proveedor="900111",
             es_pyme="No"),
        # Valor nulo (debe descartarse)
        dict(id_contrato="C-004", nombre_entidad="SENA",
             nit_entidad="899999", departamento="Bogotá", ciudad="Bogotá",
             orden="Nacional", sector="Educación",
             descripcion_del_proceso="Licenciamiento de software educativo",
             codigo_de_categoria_principal="V1.43.23.30.00",
             tipo_de_contrato="Compraventa", modalidad_de_contratacion="Mínima cuantía",
             estado_contrato="Terminado", fecha_de_firma="2024-05-05",
             fecha_de_inicio_del_contrato="2024-05-10", fecha_de_fin_del_contrato="2024-08-10",
             valor_del_contrato="", valor_pagado="",
             proveedor_adjudicado="SOFT COLOMBIA S.A.", documento_proveedor="901333",
             es_pyme="Sí"),
        # Fechas invertidas (duración debe quedar nula, no negativa)
        dict(id_contrato="C-005", nombre_entidad="DIAN",
             nit_entidad="800197", departamento="Bogotá", ciudad="Bogotá",
             orden="Nacional", sector="Hacienda",
             descripcion_del_proceso="Soporte tecnico de infraestructura tecnologica",
             codigo_de_categoria_principal="V1.81.11.15.00",
             tipo_de_contrato="Prestación de servicios",
             modalidad_de_contratacion="Contratación directa",
             estado_contrato="En ejecución", fecha_de_firma="2024-08-01",
             fecha_de_inicio_del_contrato="2024-12-31", fecha_de_fin_del_contrato="2024-09-01",
             valor_del_contrato="120000000", valor_pagado="60000000",
             proveedor_adjudicado="REDES Y SISTEMAS LTDA", documento_proveedor="830444",
             es_pyme="Sí"),
        # Valor atípicamente bajo (se marca, no se borra)
        dict(id_contrato="C-006", nombre_entidad="DIAN",
             nit_entidad="800197", departamento="Bogotá", ciudad="Bogotá",
             orden="Nacional", sector="Hacienda",
             descripcion_del_proceso="Compra de computadores",
             codigo_de_categoria_principal="V1.43.21.15.00",
             tipo_de_contrato="Compraventa", modalidad_de_contratacion="Mínima cuantía",
             estado_contrato="Terminado", fecha_de_firma="2025-01-15",
             fecha_de_inicio_del_contrato="2025-01-20", fecha_de_fin_del_contrato="2025-03-20",
             valor_del_contrato="50000", valor_pagado="50000",
             proveedor_adjudicado="COMPUTO EXPRESS S.A.S", documento_proveedor="901555",
             es_pyme="Sí"),
    ]
    return pd.DataFrame(filas)


def ok(condicion: bool, descripcion: str, fallos: list[str]) -> None:
    if condicion:
        print(f"  PASA  {descripcion}")
    else:
        print(f"  FALLA {descripcion}")
        fallos.append(descripcion)


def main() -> int:
    fallos: list[str] = []
    print("== Pruebas unitarias de utilidades ==")

    ok(normalizar_nombre("TECNOLOGIA S.A.S.") == normalizar_nombre("Tecnología SAS"),
       "normalizar_nombre unifica variantes societarias y tildes", fallos)
    ok(normalizar_nombre("") == "SIN INFORMACION",
       "normalizar_nombre maneja vacíos", fallos)
    ok(a_numero(pd.Series(["1.500.000.000"]))[0] == 1_500_000_000,
       "a_numero interpreta formato colombiano de miles (1.500.000.000)", fallos)
    ok(a_numero(pd.Series(["1,500,000.50"]))[0] == 1_500_000.50,
       "a_numero interpreta formato anglosajón con decimales", fallos)
    ok(a_numero(pd.Series(["1.500.000,75"]))[0] == 1_500_000.75,
       "a_numero interpreta formato colombiano con decimales", fallos)
    ok(a_numero(pd.Series(["800000000"]))[0] == 800_000_000,
       "a_numero interpreta números sin separadores", fallos)
    ok(a_numero(pd.Series(["$ 120.000.000 COP"]))[0] == 120_000_000,
       "a_numero ignora símbolos de moneda y texto", fallos)
    ok(pd.isna(a_numero(pd.Series([""]))[0]),
       "a_numero deja nulo lo que no es número", fallos)

    print("\n== Prueba de integración del pipeline ==")
    raw = muestra_sintetica()
    cols = resolver_columnas(raw)
    ok(len(cols) >= 15, f"resolver_columnas mapeó {len(cols)} campos lógicos", fallos)

    es_ti = marcar_ti(raw, cols)
    ok(bool(es_ti.sum() == 6),
       f"marcar_ti aisló 6 de 7 registros (excluye alimentos escolares); obtuvo {int(es_ti.sum())}", fallos)
    ok(not bool(es_ti[raw["id_contrato"] == "C-003"].iloc[0]),
       "marcar_ti excluye correctamente el contrato que no es de TI", fallos)

    salida = construir(raw)
    h = salida["hechos"]

    ok(len(h) == 4,
       f"la tabla de hechos deja 4 filas tras quitar duplicado y valor nulo; obtuvo {len(h)}", fallos)
    ok(h["id_contrato"].is_unique, "no quedan id_contrato duplicados", fallos)
    ok(h["valor"].notna().all() and (h["valor"] > 0).all(),
       "todos los valores son numéricos y positivos", fallos)

    dur_c005 = h.loc[h["id_contrato"] == "C-005", "duracion_dias"]
    ok(bool(dur_c005.isna().iloc[0]),
       "las fechas invertidas producen duración nula, no negativa", fallos)

    ok(bool(h.loc[h["id_contrato"] == "C-006", "valor_atipico"].iloc[0]),
       "el contrato de valor irrisorio queda marcado como atípico", fallos)
    ok("C-006" in set(h["id_contrato"]),
       "el atípico se marca pero NO se elimina", fallos)

    ok(bool(h.loc[h["id_contrato"] == "C-002", "baja_competencia"].iloc[0]),
       "contratación directa se marca como baja competencia", fallos)
    ok(not bool(h.loc[h["id_contrato"] == "C-001", "baja_competencia"].iloc[0]),
       "licitación pública NO se marca como baja competencia", fallos)

    prov = salida["dim_proveedor"]
    ok(len(prov) == len(prov["proveedor_norm"].unique()),
       "dim_proveedor no tiene duplicados", fallos)
    ok("TECNOLOGIA" in set(prov["proveedor_norm"]),
       "'TECNOLOGIA S.A.S.' y 'TECNOLOGIA SAS' se consolidan en un proveedor", fallos)

    ent = salida["dim_entidad"]
    ok("MINISTERIO DE SALUD" in set(ent["entidad_norm"]),
       "'MINISTERIO DE SALUD' y 'Ministerio de Salud' se consolidan en una entidad", fallos)

    ok(h["id_entidad"].notna().all() and h["id_proveedor"].notna().all(),
       "todas las filas de hechos tienen llave a sus dimensiones", fallos)

    dimf = salida["dim_fecha"]
    ok(len(dimf) > 0 and dimf["fecha"].is_unique,
       "dim_fecha es continua y sin fechas repetidas", fallos)

    print("\n" + "=" * 60)
    if fallos:
        print(f"RESULTADO: {len(fallos)} prueba(s) fallaron")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("RESULTADO: todas las pruebas pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
