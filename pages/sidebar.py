"""
pages/sidebar.py
────────────────
Sidebar con navegación y estado del MMV.
"""

from __future__ import annotations

import datetime
import os

import streamlit as st

from pages.shared import DATA_DIR, MMV_CANDIDATE_FILES, resolver_mmv_path

NAV_ITEMS = [
    ("Overview", "bar_chart", "dashboard"),
    ("Curules Senado", "gavel", "curules_senado"),
    ("Curules Camara Antioquia", "gavel", "curules_camara_antioquia"),
    ("Candidatos", "groups", "candidatos"),
    ("German Dario", "person", "german"),
    ("Juliana", "person", "juliana"),
    ("Partidos", "account_balance", "partidos"),
    ("Geografico", "map", "geografico"),
    ("Cruce Votos", "sync_alt", "cruce_votos"),
    ("Mesas Sin Votos", "do_not_disturb_on", "mesas_sin_votos"),
    ("Mesas Diferencia", "warning", "mesas_diferencia"),
    ("Preconteo vs Escrutinio", "compare", "preconteo_escrutinio"),
]


def render_sidebar(datos: dict) -> str:
    with st.sidebar:
        # Logo / título
        st.markdown(
            """
<div style="padding:8px 0 20px 0;">
  <div style="font-family:'Bebas Neue',sans-serif;font-size:26px;
              letter-spacing:0.1em;color:#111827;line-height:1.15;">
    <span style="color:#DC2626;font-size:22px;vertical-align:middle;">📊</span>
    &nbsp;DASHBOARD<br>
    <span style="color:#DC2626;">ELECTORAL</span>
  </div>
  <div style="font-size:10px;color:#6B7280;margin-top:6px;
              font-weight:600;letter-spacing:0.14em;">
    CREEMOS — MONITOREO EN VIVO
  </div>
</div>""",
            unsafe_allow_html=True,
        )

        st.divider()

        labels = [f":material/{icon}: {label}" for label, icon, _ in NAV_ITEMS]
        keys_map = {f":material/{icon}: {label}": key for label, icon, key in NAV_ITEMS}
        sel = st.radio("nav", labels, label_visibility="collapsed")

        st.divider()

        # Estado MMV
        mmv_path = resolver_mmv_path()
        if mmv_path.exists():
            dt = datetime.datetime.fromtimestamp(os.path.getmtime(mmv_path)).strftime(
                "%d/%m %H:%M"
            )
            st.markdown(
                f"""
<div class="alert-ok">
  <span style="font-size:16px;flex-shrink:0">✓</span>
  <div><strong>MMV cargado</strong><br>
  <span style="font-size:11px;opacity:0.75">{mmv_path.name} · Actualizado: {dt}</span></div>
</div>""",
                unsafe_allow_html=True,
            )
        else:
            mmv_names = " / ".join(MMV_CANDIDATE_FILES)
            st.markdown(
                """
<div class="alert-warn">
  <span style="font-size:16px;flex-shrink:0">!</span>
  <div><strong>Archivo no encontrado</strong><br>
  <span style="font-size:11px;">"""
                + mmv_names
                + """ no está en /data</span></div>
</div>""",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button(
            "Recargar datos", use_container_width=True, icon=":material/refresh:"
        ):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

    return keys_map[sel]
