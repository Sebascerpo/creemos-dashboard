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
    "01070_001": {"nombre": "JULIANA GUTIERREZ ZULUAGA",  "cargo": "Senado", "circ": "1", "color": "#E63946"},
    "01067_117": {"nombre": "GERMAN DARIO HOYOS GIRALDO", "cargo": "Cámara", "circ": "2", "color": "#2196F3"},
}

COLORES = {
    "red":    "#E63946",
    "blue":   "#2196F3",
    "green":  "#10B981",
    "yellow": "#F59E0B",
    "muted":  "#94A3B8",
    "bg":     "#0A0E1A",
    "surface":"#111827",
    "surface2":"#1C2537",
    "border": "#2D3748",
    "text":   "#F1F5F9",
}

# ──────────────────────────────────────────────
# ESTILOS — llamar inject_styles() una vez en app.py
# ──────────────────────────────────────────────

def inject_styles():
    st.html("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;500;600&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,300,0,0&display=swap" rel="stylesheet">
    """)
    st.markdown("""
<style>
.ms {
    font-family: 'Material Symbols Rounded';
    font-weight: normal;
    font-style: normal;
    font-size: 18px;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    display: inline-block;
    white-space: nowrap;
    vertical-align: middle;
    font-variation-settings: 'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 24;
}
.ms-fill { font-variation-settings: 'FILL' 1, 'wght' 300, 'GRAD' 0, 'opsz' 24; }
.ms-lg   { font-size: 20px; }

:root {
    --bg:       #0A0E1A;
    --surface:  #111827;
    --surface2: #1C2537;
    --border:   #2D3748;
    --text:     #F1F5F9;
    --muted:    #94A3B8;
    --red:      #E63946;
    --blue:     #2196F3;
    --green:    #10B981;
    --yellow:   #F59E0B;
}

html, body, .stApp {
    background-color: #0A0E1A !important;
    color: #F1F5F9 !important;
}
.stApp * { font-family: 'Inter', sans-serif; }

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #111827 !important;
    border-right: 1px solid #2D3748 !important;
}
[data-testid="stSidebar"] * { color: #F1F5F9 !important; }

/* Main content area */
[data-testid="stMainBlockContainer"] {
    background-color: #0A0E1A !important;
}

/* Radio buttons in sidebar */
[data-testid="stSidebar"] .stRadio label {
    color: #94A3B8 !important;
    font-size: 14px;
    padding: 4px 0;
}
[data-testid="stSidebar"] .stRadio label:hover {
    color: #F1F5F9 !important;
}

/* KPI Cards */
.kpi-card {
    background: #1C2537;
    border: 1px solid #2D3748;
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
    background: var(--accent, #E63946);
}
.kpi-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #94A3B8;
    margin-bottom: 8px;
}
.kpi-value {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 40px;
    line-height: 1;
    color: #F1F5F9;
    letter-spacing: 0.02em;
}
.kpi-sub {
    font-size: 12px;
    color: #94A3B8;
    margin-top: 6px;
}

/* Section titles */
.section-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 20px;
    letter-spacing: 0.08em;
    color: #F1F5F9;
    border-bottom: 1px solid #2D3748;
    padding-bottom: 8px;
    margin: 24px 0 16px 0;
    display: flex;
    align-items: center;
    gap: 8px;
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
.badge-senado { background: rgba(230,57,70,0.2);  color: #E63946; border: 1px solid rgba(230,57,70,0.4); }
.badge-camara { background: rgba(33,150,243,0.2); color: #2196F3; border: 1px solid rgba(33,150,243,0.4); }
.badge-nac    { background: rgba(16,185,129,0.2); color: #10B981; border: 1px solid rgba(16,185,129,0.4); }
.badge-ant    { background: rgba(245,158,11,0.2); color: #F59E0B; border: 1px solid rgba(245,158,11,0.4); }

/* Alerts */
.alert-warn {
    background: rgba(245,158,11,0.08);
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: 8px;
    padding: 12px 16px;
    color: #F59E0B;
    font-size: 13px;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 12px;
}
.alert-ok {
    background: rgba(16,185,129,0.08);
    border: 1px solid rgba(16,185,129,0.3);
    border-radius: 8px;
    padding: 12px 16px;
    color: #10B981;
    font-size: 13px;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 12px;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #2D3748;
}
.stTabs [data-baseweb="tab"] {
    color: #94A3B8 !important;
    background: transparent !important;
}
.stTabs [aria-selected="true"] {
    color: #F1F5F9 !important;
    border-bottom: 2px solid #E63946 !important;
}

/* Dataframes */
.stDataFrame { border: 1px solid #2D3748 !important; border-radius: 8px; }

/* Expanders */
.stExpander {
    border: 1px solid #2D3748 !important;
    border-radius: 8px !important;
    background: #111827 !important;
}

/* Buttons */
.stButton button {
    background: #1C2537 !important;
    border: 1px solid #2D3748 !important;
    color: #F1F5F9 !important;
    border-radius: 6px !important;
}
.stButton button:hover {
    border-color: #E63946 !important;
    color: #E63946 !important;
}

/* Selectbox / inputs */
.stSelectbox > div > div,
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background: #1C2537 !important;
    border-color: #2D3748 !important;
    color: #F1F5F9 !important;
}

/* Plotly transparent bg */
.js-plotly-plot .plotly { background: transparent !important; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# CARGA DE DATOS
# ──────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def cargar_todo(cache_key: str = "") -> dict:
    mmv_path  = resolver_mmv_path()
    cand_path = DATA_DIR / "CANDIDATOS.txt"
    part_path = DATA_DIR / "PARTIDOS.txt"
    div_path  = DATA_DIR / "DIVIPOL.txt"
    corp_path = DATA_DIR / "CORPORACION.txt"

    datos = {}
    datos["mmv"]           = procesar_mmv(str(mmv_path), cache_key=cache_key) if mmv_path.exists() else None
    datos["partidos"]      = cargar_partidos(str(part_path))      if part_path.exists() else {}
    datos["candidatos"]    = cargar_candidatos(str(cand_path))    if cand_path.exists() else {}
    datos["divipol"]       = cargar_divipol(str(div_path))        if div_path.exists()  else {"por_muni": {}, "por_depto": {}, "por_puesto": {}}
    datos["corporaciones"] = cargar_corporaciones(str(corp_path)) if corp_path.exists() else {}
    return datos


# ──────────────────────────────────────────────
# HELPERS GENERALES
# ──────────────────────────────────────────────

def ms(icon: str, extra_cls: str = "") -> str:
    return f'<span class="ms {extra_cls}">{icon}</span>'

def fmt(n: int | float) -> str:
    return f"{int(n):,}".replace(",", ".")

def pct(num: int | float, den: int | float, decimals: int = 1) -> str:
    if den == 0:
        return "—"
    return f"{num / den * 100:.{decimals}f}%"

def kpi(label: str, value: str, sub: str = "", accent: str = "#E63946"):
    st.markdown(f"""
<div class="kpi-card" style="--accent:{accent}">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
  <div class="kpi-sub">{sub}</div>
</div>""", unsafe_allow_html=True)

def section(title: str, icon: str):
    st.markdown(
        f'<div class="section-title"><span>{title}</span></div>',
        unsafe_allow_html=True,
    )

def badge(tipo: str) -> str:
    MAP = {
        "senado":    '<span class="badge badge-senado">Senado</span>',
        "camara":    '<span class="badge badge-camara">Cámara</span>',
        "nacional":  '<span class="badge badge-nac">Nacional</span>',
        "antioquia": '<span class="badge badge-ant">Antioquia</span>',
    }
    return MAP.get(tipo, "")

def plotly_defaults(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter"),
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94A3B8")),
    )
    fig.update_xaxes(gridcolor="#2D3748", linecolor="#2D3748", tickfont=dict(color="#94A3B8"))
    fig.update_yaxes(gridcolor="#2D3748", linecolor="#2D3748", tickfont=dict(color="#94A3B8"))
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
        return f"{info.get('nombre_municipio', muni_key)} ({info.get('nombre_depto', '')})"
    return muni_key

def es_senado(circ: str) -> bool:
    return circ == "1"
