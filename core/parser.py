"""
core/parser.py
──────────────
Parsea y agrega el archivo MMV en memoria.

Estructura del archivo (38 chars ancho fijo):
  cod_depto(2) cod_muni(3) zona(2) puesto(2) num_mesa(6)
  cod_jal(2) num_comunicado(4) circunscripcion(1)
  cod_partido(5) cod_candidato(3) votos(8)

circunscripcion:
  1 = Senado (nacional)
  2 = Cámara (departamental)
  (otros valores posibles según el archivo real)

Antioquia = cod_depto "01"
"""

from __future__ import annotations

from collections import defaultdict
import streamlit as st

COD_LISTA = "000"
COD_BLANCO = "996"
COD_NULO = "997"
COD_NO_MARC = "998"

COD_ANTIOQUIA = "01"


def _parsear_linea(linea: str) -> dict | None:
    linea = linea.rstrip("\r\n")
    if len(linea) < 38:
        return None
    try:
        return {
            "cod_depto": linea[0:2],
            "cod_muni": linea[2:5],
            "zona": linea[5:7],
            "puesto": linea[7:9],
            "num_mesa": linea[9:15],
            "cod_jal": linea[15:17],
            "circunscripcion": linea[21:22],
            "cod_partido": linea[22:27],
            "cod_candidato": linea[27:30],
            "votos": int(linea[30:38]) if linea[30:38].strip().isdigit() else 0,
        }
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def procesar_mmv(path: str) -> dict:
    """
    Lee el MMV y retorna agregados en memoria.

    Retorna:
      candidatos   {cand_key: {votos_total, por_depto, por_municipio,
                               por_puesto, por_mesa, cod_partido,
                               cod_candidato, circunscripcion}}
      partidos     {cod_partido: {votos_total, por_depto, por_municipio,
                                  circunscripcion}}
      municipios   {depto_muni: {mesas, votos_validos, ...}}
      deptos       {cod_depto: {municipios, mesas, votos_validos, ...}}
      mesas_count  int
      total_lineas int
    """
    candidatos = defaultdict(
        lambda: {
            "votos_total": 0,
            "por_depto": defaultdict(int),
            "por_municipio": defaultdict(int),
            # {depto_muni_zona_puesto: votos}  — para drill-down a puesto
            "por_puesto": defaultdict(int),
            # {mesa_key: votos}  — para drill-down a mesa individual
            "por_mesa": defaultdict(int),
            "cod_partido": "",
            "cod_candidato": "",
            "circunscripcion": "",
        }
    )
    partidos = defaultdict(
        lambda: {
            "votos_total": 0,
            "por_depto": defaultdict(int),
            "por_municipio": defaultdict(int),
            "por_puesto": defaultdict(int),
            "por_mesa": defaultdict(int),
            "circunscripcion": "",
        }
    )
    municipios = defaultdict(
        lambda: {
            "mesas": set(),
            "votos_validos": 0,
            "votos_blanco": 0,
            "votos_nulo": 0,
            "votos_no_marcado": 0,
            "cod_depto": "",
            "cod_muni": "",
        }
    )
    deptos = defaultdict(
        lambda: {
            "municipios": set(),
            "mesas": set(),
            "votos_validos": 0,
            "votos_blanco": 0,
            "votos_nulo": 0,
            "votos_no_marcado": 0,
        }
    )
    stats_por_circ = defaultdict(
        lambda: {
            "votos_total": 0,
            "votos_validos_candidatos": 0,
            "votos_lista": 0,
            "votos_validos_total": 0,  # candidatos + lista
            "votos_blanco": 0,
            "votos_nulo": 0,
            "votos_no_marcado": 0,
        }
    )
    totales_validos_por_circ = defaultdict(
        lambda: {
            "por_municipio": defaultdict(int),
            "por_puesto": defaultdict(int),
            "por_mesa": defaultdict(int),
        }
    )
    partidos_por_circ = defaultdict(
        lambda: defaultdict(
            lambda: {
                "votos_lista": 0,
                "votos_candidatos": 0,
                "votos_validos_total": 0,  # lista + candidatos
                "por_depto_validos_total": defaultdict(int),
                "por_municipio_validos_total": defaultdict(int),
                "por_puesto_validos_total": defaultdict(int),
                "por_mesa_validos_total": defaultdict(int),
            }
        )
    )

    mesas_set = set()
    total_lineas = 0

    with open(path, encoding="latin-1") as f:
        for linea in f:
            if not linea.strip():
                continue
            total_lineas += 1
            r = _parsear_linea(linea)
            if not r:
                continue

            partido = r["cod_partido"]
            candidato = r["cod_candidato"]
            votos = r["votos"]
            depto = r["cod_depto"]
            muni = r["cod_muni"]
            zona = r["zona"]
            puesto = r["puesto"]
            circ = r["circunscripcion"]
            mesa_key = f"{depto}_{muni}_{zona}_{puesto}_{r['num_mesa']}"
            puesto_key = f"{depto}_{muni}_{zona}_{puesto}"
            muni_key = f"{depto}_{muni}"
            cand_key = f"{partido}_{candidato}"
            stats_por_circ[circ]["votos_total"] += votos

            mesas_set.add(mesa_key)
            municipios[muni_key]["cod_depto"] = depto
            municipios[muni_key]["cod_muni"] = muni
            municipios[muni_key]["mesas"].add(mesa_key)
            deptos[depto]["municipios"].add(muni_key)
            deptos[depto]["mesas"].add(mesa_key)

            # Votos especiales
            if candidato == COD_BLANCO:
                municipios[muni_key]["votos_blanco"] += votos
                deptos[depto]["votos_blanco"] += votos
                stats_por_circ[circ]["votos_blanco"] += votos
                continue
            if candidato == COD_NULO:
                municipios[muni_key]["votos_nulo"] += votos
                deptos[depto]["votos_nulo"] += votos
                stats_por_circ[circ]["votos_nulo"] += votos
                continue
            if candidato == COD_NO_MARC:
                municipios[muni_key]["votos_no_marcado"] += votos
                deptos[depto]["votos_no_marcado"] += votos
                stats_por_circ[circ]["votos_no_marcado"] += votos
                continue

            # Votos válidos — no duplicar lista + preferente
            if candidato != COD_LISTA:
                municipios[muni_key]["votos_validos"] += votos
                deptos[depto]["votos_validos"] += votos
                stats_por_circ[circ]["votos_validos_candidatos"] += votos
                stats_por_circ[circ]["votos_validos_total"] += votos
                totales_validos_por_circ[circ]["por_municipio"][muni_key] += votos
                totales_validos_por_circ[circ]["por_puesto"][puesto_key] += votos
                totales_validos_por_circ[circ]["por_mesa"][mesa_key] += votos
                partidos_por_circ[circ][partido]["votos_candidatos"] += votos
                partidos_por_circ[circ][partido]["votos_validos_total"] += votos
                partidos_por_circ[circ][partido]["por_depto_validos_total"][depto] += votos
                partidos_por_circ[circ][partido]["por_municipio_validos_total"][muni_key] += votos
                partidos_por_circ[circ][partido]["por_puesto_validos_total"][puesto_key] += votos
                partidos_por_circ[circ][partido]["por_mesa_validos_total"][mesa_key] += votos
            else:
                stats_por_circ[circ]["votos_lista"] += votos
                stats_por_circ[circ]["votos_validos_total"] += votos
                totales_validos_por_circ[circ]["por_municipio"][muni_key] += votos
                totales_validos_por_circ[circ]["por_puesto"][puesto_key] += votos
                totales_validos_por_circ[circ]["por_mesa"][mesa_key] += votos
                partidos_por_circ[circ][partido]["votos_lista"] += votos
                partidos_por_circ[circ][partido]["votos_validos_total"] += votos
                partidos_por_circ[circ][partido]["por_depto_validos_total"][depto] += votos
                partidos_por_circ[circ][partido]["por_municipio_validos_total"][muni_key] += votos
                partidos_por_circ[circ][partido]["por_puesto_validos_total"][puesto_key] += votos
                partidos_por_circ[circ][partido]["por_mesa_validos_total"][mesa_key] += votos

            # Candidatos (solo preferentes, no cabeceras)
            if candidato != COD_LISTA:
                candidatos[cand_key]["votos_total"] += votos
                candidatos[cand_key]["por_depto"][depto] += votos
                candidatos[cand_key]["por_municipio"][muni_key] += votos
                candidatos[cand_key]["por_puesto"][puesto_key] += votos
                candidatos[cand_key]["por_mesa"][mesa_key] += votos
                candidatos[cand_key]["cod_partido"] = partido
                candidatos[cand_key]["cod_candidato"] = candidato
                candidatos[cand_key]["circunscripcion"] = circ

            # Partidos (solo votos de lista 000)
            if candidato == COD_LISTA:
                partidos[partido]["votos_total"] += votos
                partidos[partido]["por_depto"][depto] += votos
                partidos[partido]["por_municipio"][muni_key] += votos
                partidos[partido]["por_puesto"][puesto_key] += votos
                partidos[partido]["por_mesa"][mesa_key] += votos
                partidos[partido]["circunscripcion"] = circ

    partidos_por_circ_out = {}
    for circ, partidos_circ in partidos_por_circ.items():
        partidos_por_circ_out[circ] = {}
        for cod_partido, d in partidos_circ.items():
            partidos_por_circ_out[circ][cod_partido] = {
                "votos_lista": d["votos_lista"],
                "votos_candidatos": d["votos_candidatos"],
                "votos_validos_total": d["votos_validos_total"],
                "por_depto_validos_total": dict(d["por_depto_validos_total"]),
                "por_municipio_validos_total": dict(d["por_municipio_validos_total"]),
                "por_puesto_validos_total": dict(d["por_puesto_validos_total"]),
                "por_mesa_validos_total": dict(d["por_mesa_validos_total"]),
            }
    totales_validos_por_circ_out = {}
    for circ, d in totales_validos_por_circ.items():
        totales_validos_por_circ_out[circ] = {
            "por_municipio": dict(d["por_municipio"]),
            "por_puesto": dict(d["por_puesto"]),
            "por_mesa": dict(d["por_mesa"]),
        }

    return {
        "candidatos": dict(candidatos),
        "partidos": dict(partidos),
        "municipios": dict(municipios),
        "deptos": dict(deptos),
        "stats_por_circ": dict(stats_por_circ),
        "partidos_por_circ": partidos_por_circ_out,
        "totales_validos_por_circ": totales_validos_por_circ_out,
        "mesas_count": len(mesas_set),
        "total_lineas": total_lineas,
    }
