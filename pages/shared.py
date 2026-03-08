"""
pages/shared.py
───────────────
Constantes, estilos, helpers y carga de datos.
Importado por todas las páginas.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.catalogos import (
    cargar_candidatos,
    cargar_corporaciones,
    cargar_divipol,
    cargar_partidos,
)
from core.parser import procesar_mmv, COD_ANTIOQUIA

# ──────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
MMV_CANDIDATE_FILES = [
    "PPP_MMV_DD_9999_test.txt",
    "PPP_MMV_DD_9999.txt",
]


def resolver_mmv_path() -> Path:
    for fname in MMV_CANDIDATE_FILES:
        p = DATA_DIR / fname
        if p.exists():
            return p
    return DATA_DIR / MMV_CANDIDATE_FILES[0]


CANDIDATOS_PRINCIPALES = {
    "01070_001": {
        "nombre": "JULIANA GUTIERREZ ZULUAGA",
        "cargo": "Senado",
        "circ": "1",
        "color": "#E63946",
    },
    "01067_117": {
        "nombre": "GERMAN DARIO HOYOS GIRALDO",
        "cargo": "Cámara",
        "circ": "2",
        "color": "#2196F3",
    },
}

COLORES = {
    "red": "#DC2626",
    "blue": "#2563EB",
    "green": "#059669",
    "yellow": "#D97706",
    "muted": "#6B7280",
    "bg": "#FFFFFF",
    "surface": "#F9FAFB",
    "surface2": "#F3F4F6",
    "border": "#E5E7EB",
    "text": "#111827",
}

# ──────────────────────────────────────────────
# ESTILOS — llamar inject_styles() una vez en app.py
# ──────────────────────────────────────────────


def inject_styles():
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    --bg:       #FFFFFF;
    --surface:  #F9FAFB;
    --surface2: #F3F4F6;
    --border:   #E5E7EB;
    --text:     #111827;
    --muted:    #6B7280;
    --red:      #DC2626;
    --blue:     #2563EB;
    --green:    #059669;
    --yellow:   #D97706;
}

html, body, .stApp {
    background-color: #FFFFFF !important;
    color: #111827 !important;
}
.stApp *:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded):not([class*="material"]) {
    font-family: 'Inter', sans-serif;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #F9FAFB !important;
    border-right: 1px solid #E5E7EB !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] strong,
[data-testid="stSidebar"] a { color: #111827 !important; }

/* Main content */
[data-testid="stMainBlockContainer"] {
    background-color: #FFFFFF !important;
}

/* Radio buttons in sidebar */
[data-testid="stSidebar"] .stRadio label {
    color: #374151 !important;
    font-size: 14px;
    font-weight: 500;
    padding: 4px 0;
}
[data-testid="stSidebar"] .stRadio label:hover {
    color: #DC2626 !important;
}

/* KPI Cards */
.kpi-card {
    background: #F9FAFB;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 20px 24px;
    position: relative;
    overflow: hidden;
    margin-bottom: 8px;
    height: 100%;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--accent, #DC2626);
}
.kpi-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #6B7280;
    margin-bottom: 8px;
}
.kpi-value {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 40px;
    line-height: 1;
    color: #111827;
    letter-spacing: 0.02em;
}
.kpi-sub {
    font-size: 12px;
    color: #6B7280;
    margin-top: 6px;
}

/* Section titles */
.section-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 20px;
    letter-spacing: 0.08em;
    color: #111827;
    border-bottom: 2px solid #E5E7EB;
    padding-bottom: 8px;
    margin: 24px 0 16px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-title .material-icons-round {
    color: #DC2626;
    font-size: 22px;
}

/* Badges */
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    vertical-align: middle;
    margin-left: 6px;
}
.badge-senado { background: #FEE2E2; color: #DC2626; border: 1px solid #FECACA; }
.badge-camara { background: #DBEAFE; color: #2563EB; border: 1px solid #BFDBFE; }
.badge-nac    { background: #D1FAE5; color: #059669; border: 1px solid #A7F3D0; }
.badge-ant    { background: #FEF3C7; color: #D97706; border: 1px solid #FDE68A; }

/* Alerts */
.alert-warn {
    background: #FEF3C7;
    border: 1px solid #FDE68A;
    border-radius: 8px;
    padding: 12px 16px;
    color: #92400E;
    font-size: 13px;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 12px;
}
.alert-ok {
    background: #D1FAE5;
    border: 1px solid #A7F3D0;
    border-radius: 8px;
    padding: 12px 16px;
    color: #065F46;
    font-size: 13px;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 12px;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #E5E7EB;
}
.stTabs [data-baseweb="tab"] {
    color: #6B7280 !important;
    background: transparent !important;
}
.stTabs [aria-selected="true"] {
    color: #111827 !important;
    border-bottom: 2px solid #DC2626 !important;
}

/* Dataframes */
.stDataFrame { border: 1px solid #E5E7EB !important; border-radius: 8px; }

/* Expanders */
.stExpander {
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
    background: #F9FAFB !important;
}

/* Buttons */
.stButton button {
    background: #FFFFFF !important;
    border: 1px solid #D1D5DB !important;
    color: #111827 !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
}
.stButton button:hover {
    border-color: #DC2626 !important;
    color: #DC2626 !important;
    background: #FEF2F2 !important;
}

/* Selectbox / inputs */
.stSelectbox > div > div,
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background: #FFFFFF !important;
    border-color: #D1D5DB !important;
    color: #111827 !important;
}

/* Plotly transparent bg */
.js-plotly-plot .plotly { background: transparent !important; }

/* Streamlit alerts/messages text */
.stAlert p, .stAlert span { color: inherit !important; }

/* Download button */
.stDownloadButton button {
    background: #FFFFFF !important;
    border: 1px solid #D1D5DB !important;
    color: #111827 !important;
}
.stDownloadButton button:hover {
    border-color: #DC2626 !important;
    color: #DC2626 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────
# CARGA DE DATOS
# ──────────────────────────────────────────────


@st.cache_resource(show_spinner=False)
def cargar_todo(cache_key: str = "") -> dict:
    mmv_path = resolver_mmv_path()
    cand_path = DATA_DIR / "CANDIDATOS.txt"
    part_path = DATA_DIR / "PARTIDOS.txt"
    div_path = DATA_DIR / "DIVIPOL.txt"
    corp_path = DATA_DIR / "CORPORACION.txt"

    datos = {}
    datos["mmv"] = (
        procesar_mmv(str(mmv_path), cache_key=cache_key) if mmv_path.exists() else None
    )
    datos["partidos"] = cargar_partidos(str(part_path)) if part_path.exists() else {}
    datos["candidatos"] = (
        cargar_candidatos(str(cand_path)) if cand_path.exists() else {}
    )
    datos["divipol"] = (
        cargar_divipol(str(div_path))
        if div_path.exists()
        else {"por_muni": {}, "por_depto": {}, "por_puesto": {}}
    )
    datos["corporaciones"] = (
        cargar_corporaciones(str(corp_path)) if corp_path.exists() else {}
    )
    return datos


# ──────────────────────────────────────────────
# HELPERS GENERALES
# ──────────────────────────────────────────────


def ms(icon: str, extra_cls: str = "") -> str:
    return f'<span class="material-icons-round {extra_cls}">{icon}</span>'


def fmt(n: int | float) -> str:
    return f"{int(n):,}".replace(",", ".")


def pct(num: int | float, den: int | float, decimals: int = 1) -> str:
    if den == 0:
        return "—"
    return f"{num / den * 100:.{decimals}f}%"


def kpi(label: str, value: str, sub: str = "", accent: str = "#DC2626"):
    st.markdown(
        f"""
<div class="kpi-card" style="--accent:{accent}">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
  <div class="kpi-sub">{sub}</div>
</div>""",
        unsafe_allow_html=True,
    )


def section(title: str, icon: str):
    st.markdown(f"#### :material/{icon}: {title}")


def badge(tipo: str) -> str:
    MAP = {
        "senado": '<span class="badge badge-senado">Senado</span>',
        "camara": '<span class="badge badge-camara">Cámara</span>',
        "nacional": '<span class="badge badge-nac">Nacional</span>',
        "antioquia": '<span class="badge badge-ant">Antioquia</span>',
    }
    return MAP.get(tipo, "")


def plotly_defaults(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#374151", family="Inter"),
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#374151")),
    )
    fig.update_xaxes(
        gridcolor="#E5E7EB", linecolor="#D1D5DB", tickfont=dict(color="#6B7280")
    )
    fig.update_yaxes(
        gridcolor="#E5E7EB", linecolor="#D1D5DB", tickfont=dict(color="#6B7280")
    )
    return fig


def nombre_partido(cod: str, partidos: dict) -> str:
    return partidos.get(cod, f"[{cod}]")


def nombre_candidato(cand_key: str, candidatos: dict) -> str:
    info = candidatos.get(cand_key)
    if info:
        return info["nombre_completo"]
    parts = cand_key.split("_")
    return f"Candidato {parts[1] if len(parts) > 1 else cand_key}"


def nombre_depto(cod: str, divipol: dict) -> str:
    return divipol.get("por_depto", {}).get(cod, cod)


def nombre_municipio_str(muni_key: str, divipol: dict) -> str:
    info = divipol.get("por_muni", {}).get(muni_key, {})
    if info:
        return (
            f"{info.get('nombre_municipio', muni_key)} ({info.get('nombre_depto', '')})"
        )
    return muni_key


def es_senado(circ: str) -> bool:
    return circ == "1"
