"""
pages/pg_exportar.py
─────────────────────
Página: Exportar datos como CSV.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from pages.shared import section, nombre_partido, nombre_candidato, es_senado


def render(datos: dict):
    mmv        = datos["mmv"]
    partidos   = datos["partidos"]
    candidatos = datos["candidatos"]

    if not mmv:
        st.warning("No hay datos MMV cargados.")
        return

    section("EXPORTAR DATOS", "download")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Candidatos")
        df_cands = pd.DataFrame([{
            "Clave":      k,
            "Partido":    nombre_partido(v["cod_partido"], partidos),
            "Candidato":  nombre_candidato(k, candidatos),
            "Tipo":       "Senado" if es_senado(v["circunscripcion"]) else "Cámara",
            "Votos":      v["votos_total"],
            "Deptos":     len(v["por_depto"]),
            "Municipios": len(v["por_municipio"]),
        } for k, v in sorted(mmv["candidatos"].items(),
                              key=lambda x: x[1]["votos_total"], reverse=True)])
        st.download_button(
            "Descargar candidatos CSV",
            df_cands.to_csv(index=False).encode("utf-8"),
            "candidatos.csv", "text/csv",
            use_container_width=True, icon=":material/download:",
        )

    with col2:
        st.subheader("Partidos")
        df_part = pd.DataFrame([{
            "Código":     cod,
            "Partido":    nombre_partido(cod, partidos),
            "Tipo":       "Senado" if d["circunscripcion"] == "1" else "Cámara",
            "Votos":      d["votos_total"],
            "Deptos":     len(d["por_depto"]),
            "Municipios": len(d["por_municipio"]),
        } for cod, d in sorted(mmv["partidos"].items(),
                                key=lambda x: x[1]["votos_total"], reverse=True)])
        st.download_button(
            "Descargar partidos CSV",
            df_part.to_csv(index=False).encode("utf-8"),
            "partidos.csv", "text/csv",
            use_container_width=True, icon=":material/download:",
        )

    st.subheader("Municipios")
    df_munis = pd.DataFrame([{
        "Clave":         k,
        "Depto":         v["cod_depto"],
        "Municipio":     v["cod_muni"],
        "Mesas":         len(v["mesas"]),
        "Votos válidos": v["votos_validos"],
        "Blancos":       v["votos_blanco"],
        "Nulos":         v["votos_nulo"],
    } for k, v in sorted(mmv["municipios"].items(),
                          key=lambda x: x[1]["votos_validos"], reverse=True)])
    st.download_button(
        "Descargar municipios CSV",
        df_munis.to_csv(index=False).encode("utf-8"),
        "municipios.csv", "text/csv",
        use_container_width=True, icon=":material/download:",
    )

    st.subheader("Departamentos")
    df_deptos = pd.DataFrame([{
        "Depto":         cod,
        "Municipios":    len(d["municipios"]),
        "Mesas":         len(d["mesas"]),
        "Votos válidos": d["votos_validos"],
        "Blancos":       d["votos_blanco"],
        "Nulos":         d["votos_nulo"],
    } for cod, d in sorted(mmv["deptos"].items(),
                            key=lambda x: x[1]["votos_validos"], reverse=True)])
    st.download_button(
        "Descargar departamentos CSV",
        df_deptos.to_csv(index=False).encode("utf-8"),
        "departamentos.csv", "text/csv",
        use_container_width=True, icon=":material/download:",
    )
