"""
core/parser_testigos.py
────────────────────────
Parsea el archivo RESULTADOS_MMV.txt (reportes de testigos) con el
mismo formato de 38 chars del MMV oficial.

Retorna un dict con estructura:
{
    "por_mesa_candidato": {mesa_key: {cand_key: votos, ...}},
    "por_mesa_total": {mesa_key: votos_total},
    "mesas": set de mesa_keys,
    "lineas": int total de líneas,
}
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import streamlit as st

from core.parser import _parsear_linea, COD_BLANCO, COD_NULO, COD_NO_MARC, COD_LISTA

TESTIGOS_FILE = "RESULTADOS_MMV.txt"


@st.cache_data(show_spinner=False, ttl=3600)
def parsear_testigos(data_dir_str: str) -> dict | None:
    """
    Parsea RESULTADOS_MMV.txt y retorna datos por mesa.
    Retorna None si el archivo no existe.
    """
    path = Path(data_dir_str) / TESTIGOS_FILE
    if not path.exists():
        return None

    por_mesa_candidato: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    por_mesa_total: dict[str, int] = defaultdict(int)
    mesas: set[str] = set()
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
            mesa_key = f"{depto}_{muni}_{zona}_{puesto}_{r['num_mesa']}"

            mesas.add(mesa_key)

            # Excluir blanco, nulo, no marcado del cruce
            if candidato in {COD_BLANCO, COD_NULO, COD_NO_MARC}:
                continue

            cand_key = f"{partido}_{candidato}"
            por_mesa_candidato[mesa_key][cand_key] += votos
            por_mesa_total[mesa_key] += votos

    return {
        "por_mesa_candidato": dict(por_mesa_candidato),
        "por_mesa_total": dict(por_mesa_total),
        "mesas": mesas,
        "lineas": total_lineas,
    }
