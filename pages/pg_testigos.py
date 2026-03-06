"""
pages/pg_testigos.py
─────────────────────
Página: Testigos electorales
Formulario de reporte + cruce con MMV + semáforo.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from core.parser import cargar_geo_candidato
from pages.shared import section, resolver_mmv_path


def render(datos: dict):
    mmv = datos["mmv"]

    section("REPORTE DE TESTIGOS", "visibility")
    st.markdown(
        '<p style="color:#94A3B8;font-size:13px;margin-top:-8px;margin-bottom:16px;">'
        "Ingresa los votos reportados por testigos en campo. "
        "El sistema cruza automáticamente con los datos oficiales del MMV.</p>",
        unsafe_allow_html=True,
    )

    if "testigos" not in st.session_state:
        st.session_state.testigos = []

    # ── Formulario ──
    with st.expander("Agregar reporte de testigo", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            t_depto = st.text_input(
                "Código Depto (2 dígitos)", max_chars=2, key="t_depto"
            )
            t_muni = st.text_input(
                "Código Municipio (3 dígitos)", max_chars=3, key="t_muni"
            )
        with col2:
            t_zona = st.text_input("Zona (2 dígitos)", max_chars=2, key="t_zona")
            t_puesto = st.text_input("Puesto (2 dígitos)", max_chars=2, key="t_puesto")
            t_mesa = st.text_input("Mesa (6 dígitos)", max_chars=6, key="t_mesa")
        with col3:
            t_votos_juliana = st.number_input(
                "Votos JULIANA (Senado)", min_value=0, key="t_vj"
            )
            t_votos_german = st.number_input(
                "Votos GERMAN DARIO (Cámara)", min_value=0, key="t_vg"
            )
            t_testigo = st.text_input("Nombre testigo", key="t_nombre")
            t_obs = st.text_area("Observaciones", key="t_obs", height=68)

        if st.button(
            "Registrar reporte",
            use_container_width=True,
            icon=":material/check_circle:",
        ):
            if t_depto and t_muni and t_mesa:
                muni_key = f"{t_depto}_{t_muni}"
                mesa_key = f"{t_depto}_{t_muni}_{t_zona}_{t_puesto}_{t_mesa.zfill(6)}"
                votos_oficial_j, votos_oficial_g = None, None
                if mmv:
                    mmv_path_str = str(resolver_mmv_path())
                    cj = mmv["candidatos"].get("01070_001")
                    cg = mmv["candidatos"].get("01067_117")
                    if cj:
                        geo_j = cargar_geo_candidato(mmv_path_str, "01070_001")
                        votos_oficial_j = geo_j["por_municipio"].get(muni_key)
                    if cg:
                        geo_g = cargar_geo_candidato(mmv_path_str, "01067_117")
                        votos_oficial_g = geo_g["por_municipio"].get(muni_key)

                st.session_state.testigos.append(
                    {
                        "mesa_key": mesa_key,
                        "testigo": t_testigo,
                        "votos_juliana": t_votos_juliana,
                        "votos_german": t_votos_german,
                        "oficial_juliana": votos_oficial_j,
                        "oficial_german": votos_oficial_g,
                        "observaciones": t_obs,
                    }
                )
                st.success(f"Reporte registrado para mesa {mesa_key}")
            else:
                st.error("Completa al menos Depto, Municipio y Mesa.")

    # ── Tabla reportes ──
    if st.session_state.testigos:
        section("REPORTES REGISTRADOS", "fact_check")

        def semaforo(rep, ofi) -> str:
            if ofi is None:
                return "Sin dato oficial"
            diff = rep - ofi
            if diff == 0:
                return "Coincide"
            return f"Diferencia: {diff:+,}"

        rows = [
            {
                "Mesa": t["mesa_key"],
                "Testigo": t["testigo"],
                "Juliana (testigo)": t["votos_juliana"],
                "Juliana (oficial)": (
                    t["oficial_juliana"] if t["oficial_juliana"] is not None else "—"
                ),
                "Estado Juliana": semaforo(t["votos_juliana"], t["oficial_juliana"]),
                "German (testigo)": t["votos_german"],
                "German (oficial)": (
                    t["oficial_german"] if t["oficial_german"] is not None else "—"
                ),
                "Estado German": semaforo(t["votos_german"], t["oficial_german"]),
                "Observaciones": t["observaciones"],
            }
            for t in st.session_state.testigos
        ]

        df_t = pd.DataFrame(rows)
        st.dataframe(df_t, use_container_width=True, height=350)

        ca, cb = st.columns(2)
        with ca:
            st.download_button(
                "Exportar CSV",
                df_t.to_csv(index=False).encode("utf-8"),
                "testigos.csv",
                "text/csv",
                use_container_width=True,
                icon=":material/download:",
            )
        with cb:
            if st.button(
                "Limpiar reportes", use_container_width=True, icon=":material/delete:"
            ):
                st.session_state.testigos = []
                st.rerun()
    else:
        st.info("Aún no hay reportes. Usa el formulario arriba para agregar uno.")
