"""
core/catalogos.py
──────────────────
Carga los archivos TXT de catálogos (PARTIDOS, CANDIDATOS, DIVIPOL, etc.)
Todos los parsers están aquí — app.py solo llama a las funciones.
"""

from __future__ import annotations

from pathlib import Path
import streamlit as st


@st.cache_data(show_spinner=False)
def cargar_partidos(path: str) -> dict[str, str]:
    """Retorna {codigo: nombre}"""
    result = {}
    try:
        with open(path, encoding="latin-1") as f:
            for linea in f:
                linea = linea.rstrip("\r\n")
                if len(linea) < 6:
                    continue
                codigo = linea[0:5].strip()
                nombre = linea[5:205].strip()
                if codigo:
                    result[codigo] = nombre
    except Exception:
        pass
    return result


@st.cache_data(show_spinner=False)
def cargar_candidatos(path: str) -> dict[str, dict]:
    """
    Retorna {partido_candidato: {nombre_completo, corporacion, ...}}
    SOLO candidatos reales (cod_candidato != "000").
    Las cabeceras de lista se ignoran aquí — sus votos van a resultados_partido.
    """
    result = {}
    try:
        with open(path, encoding="latin-1") as f:
            for linea in f:
                linea = linea.rstrip("\r\n")
                if len(linea) < 20:
                    continue
                corporacion = linea[0:3].strip()
                circunscripcion = linea[3:4].strip()
                cod_depto = linea[4:6].strip()
                cod_muni = linea[6:9].strip()
                cod_comuna = linea[9:11].strip()
                cod_partido = linea[11:16].strip()
                cod_candidato = linea[16:19].strip()
                preferente = linea[19:20].strip()
                nombre = linea[20:70].strip()
                apellido = linea[70:120].strip() if len(linea) >= 120 else ""
                cedula = linea[120:135].strip() if len(linea) >= 135 else ""
                genero = linea[135:136].strip() if len(linea) >= 136 else ""

                # Saltar cabeceras de lista — no son candidatos individuales
                if cod_candidato == "000":
                    continue

                # Saltar filas inválidas (sin nombre real)
                if not nombre or not cod_partido:
                    continue

                key = f"{cod_partido}_{cod_candidato}"
                result[key] = {
                    "nombre": nombre,
                    "apellido": apellido,
                    "nombre_completo": f"{nombre} {apellido}".strip(),
                    "corporacion": corporacion,
                    "circunscripcion": circunscripcion,
                    "cod_depto": cod_depto,
                    "cod_muni": cod_muni,
                    "cod_comuna": cod_comuna,
                    "cod_partido": cod_partido,
                    "cod_candidato": cod_candidato,
                    "es_preferente": preferente == "1",
                    "cedula": cedula,
                    "genero": genero,
                }
    except Exception:
        pass
    return result


@st.cache_data(show_spinner=False)
def cargar_divipol(path: str) -> dict[str, dict]:
    """
    Retorna:
      - por_muni   {depto_muni: {nombre_depto, nombre_municipio, potencial_total, num_mesas}}
      - por_depto  {depto: nombre_depto}
      - por_puesto {depto_muni_zona_puesto: {nombre_puesto, ...}}
    """
    puestos = {}
    por_muni = (
        {}
    )  # {depto_muni: {nombre_depto, nombre_municipio, potencial_total, num_mesas}}
    por_depto = {}  # {depto: nombre_depto}

    try:
        with open(path, encoding="latin-1") as f:
            for linea in f:
                linea = linea.rstrip("\r\n")
                if len(linea) < 114:
                    continue
                cod_depto = linea[0:2].strip()
                cod_muni = linea[2:5].strip()
                cod_zona = linea[5:7].strip()
                cod_puesto = linea[7:9].strip()
                nom_depto = linea[9:21].strip()
                nom_muni = linea[21:51].strip()
                # Campo fijo de 41 chars; el último char suele ser clasificador.
                nom_puesto = linea[51:91].strip()
                pot_h = linea[92:100].strip()
                pot_m = linea[100:108].strip()
                num_mesas = linea[108:114].strip()

                ph = int(pot_h) if pot_h.isdigit() else 0
                pm = int(pot_m) if pot_m.isdigit() else 0
                nm = int(num_mesas) if num_mesas.isdigit() else 0

                muni_key = f"{cod_depto}_{cod_muni}"

                if muni_key not in por_muni:
                    por_muni[muni_key] = {
                        "cod_depto": cod_depto,
                        "cod_municipio": cod_muni,
                        "nombre_depto": nom_depto,
                        "nombre_municipio": nom_muni,
                        "potencial_total": 0,
                        "num_mesas": 0,
                    }
                por_muni[muni_key]["potencial_total"] += ph + pm
                por_muni[muni_key]["num_mesas"] += nm

                if cod_depto not in por_depto:
                    por_depto[cod_depto] = nom_depto

                puesto_key = f"{cod_depto}_{cod_muni}_{cod_zona}_{cod_puesto}"
                if puesto_key not in puestos:
                    puestos[puesto_key] = {
                        "cod_depto": cod_depto,
                        "cod_municipio": cod_muni,
                        "cod_zona": cod_zona,
                        "cod_puesto": cod_puesto,
                        "nombre_depto": nom_depto,
                        "nombre_municipio": nom_muni,
                        "nombre_puesto": nom_puesto,
                    }

    except Exception:
        pass

    return {"por_muni": por_muni, "por_depto": por_depto, "por_puesto": puestos}


@st.cache_data(show_spinner=False)
def cargar_corporaciones(path: str) -> dict[str, str]:
    """Retorna {codigo: nombre}"""
    result = {}
    try:
        with open(path, encoding="latin-1") as f:
            for linea in f:
                linea = linea.rstrip("\r\n")
                if len(linea) < 4:
                    continue
                codigo = linea[0:3].strip()
                nombre = linea[3:203].strip()
                if codigo:
                    result[codigo] = nombre
    except Exception:
        pass
    return result
