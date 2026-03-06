"""
pages/pg_geografico.py
───────────────────────
Página: Geográfico
Filtros: Corporación / Ámbito / Candidato
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st
import pandas as pd

from core.parser import COD_ANTIOQUIA
from pages.shared import (
    CANDIDATOS_PRINCIPALES,
    pct, section, plotly_defaults, nombre_depto,
)


def _pref_filter(src: dict, dep: str) -> dict:
    pref = dep + "_"
    return {k: v for k, v in src.items() if k.startswith(pref)}


def _aggregate_partido(
    mmv: dict,
    party_code: str,
    circ: str,
) -> dict:
    """
    Agrega votos válidos de un partido en una corporación/circunscripción:
    lista (000) + candidatos, desde agregados MMV por circ+partido.
    """
    pd = mmv.get("partidos_por_circ", {}).get(circ, {}).get(party_code, {})
    return {
        "por_depto": dict(pd.get("por_depto_validos_total", {})),
        "por_municipio": dict(pd.get("por_municipio_validos_total", {})),
    }


def render(datos: dict):
    mmv = datos["mmv"]
    divipol = datos["divipol"]
    candidatos = datos["candidatos"]

    if not mmv:
        st.warning("No hay datos MMV cargados.")
        return

    section("ANÁLISIS GEOGRÁFICO", "public")

    # ── Filtros ──
    f1, f2, f3 = st.columns(3)
    with f1:
        filtro_corp = st.radio(
            "Corporación", ["Senado", "Cámara"],
            horizontal=True, key="geo_corp",
        )
    with f2:
        filtro_scope = st.radio(
            "Ámbito", ["Nacional", "Solo Antioquia"],
            horizontal=True, key="geo_scope",
        )
    # CREEMOS por corporación desde configuración principal
    cand_sen = next(
        (k for k, m in CANDIDATOS_PRINCIPALES.items() if m.get("cargo", "").lower() == "senado"),
        "01070_001",
    )
    cand_cam = next(
        (k for k, m in CANDIDATOS_PRINCIPALES.items() if "camara" in m.get("cargo", "").lower()),
        "01067_117",
    )

    with f3:
        # Candidato opcional; si no se selecciona, usar partido CREEMOS de la corporación.
        cands_opc = {"Sin candidato (Partido CREEMOS)": None}
        if filtro_corp == "Senado":
            cands_opc[CANDIDATOS_PRINCIPALES.get(cand_sen, {}).get("nombre", "Juliana")] = cand_sen
        else:
            cands_opc[CANDIDATOS_PRINCIPALES.get(cand_cam, {}).get("nombre", "German")] = cand_cam
        filtro_cand_label = st.selectbox(
            "Candidato", list(cands_opc.keys()), key="geo_cand")
        filtro_cand_key = cands_opc[filtro_cand_label]

    if filtro_corp == "Senado":
        corp_obj = "001"
        circ_obj = "0"
        party_creemos = cand_sen.split("_")[0]
    else:
        corp_obj = "002"
        circ_obj = "1"
        party_creemos = cand_cam.split("_")[0]

    # Objetivo del panel:
    # - candidato si se selecciona
    # - partido CREEMOS de la corporación si no se selecciona candidato
    objetivo_label = ""
    if filtro_cand_key:
        cand_meta = candidatos.get(filtro_cand_key)
        cand_data = mmv["candidatos"].get(filtro_cand_key)
        if not cand_meta:
            st.warning("El candidato seleccionado no existe en CANDIDATOS.")
            return
        if (
            cand_meta.get("corporacion") != corp_obj
            or cand_meta.get("circunscripcion") != circ_obj
        ):
            st.warning(
                "El candidato no coincide con la corporación/circunscripción seleccionada."
            )
            return
        if not cand_data:
            st.info("El candidato no tiene registros en MMV para este corte.")
            return
        if cand_data.get("circunscripcion") != circ_obj:
            st.warning("El candidato no coincide con la circunscripción activa en MMV.")
            return

        objetivo = {
            "por_depto": dict(cand_data["por_depto"]),
            "por_municipio": dict(cand_data["por_municipio"]),
        }
        objetivo_label = cand_meta.get("nombre_completo", filtro_cand_key)
    else:
        objetivo = _aggregate_partido(mmv, party_creemos, circ_obj)
        objetivo_label = f"Partido CREEMOS [{party_creemos}]"

    if filtro_scope == "Solo Antioquia":
        objetivo = {
            "por_depto": {k: v for k, v in objetivo["por_depto"].items() if k == COD_ANTIOQUIA},
            "por_municipio": _pref_filter(objetivo["por_municipio"], COD_ANTIOQUIA),
        }

    total_obj = sum(objetivo["por_depto"].values())
    scope_label = "nacional" if filtro_scope == "Nacional" else "Antioquia"

    if total_obj <= 0:
        if filtro_cand_key:
            st.info(
                f"No hay votos para el candidato seleccionado en {filtro_corp} ({scope_label}) "
                f"con corporación/circunscripción {corp_obj}/{circ_obj}."
            )
        else:
            st.info(
                f"No hay votos para el Partido CREEMOS en {filtro_corp} ({scope_label}) "
                f"con corporación/circunscripción {corp_obj}/{circ_obj}."
            )
        return

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    st.caption(
        f"Corporación/circunscripción activa: {corp_obj}/{circ_obj}. "
        f"Objetivo: {objetivo_label}."
    )
    st.caption(
        "Votos objetivo = candidato seleccionado o Partido CREEMOS "
        "(lista + candidatos válidos según corresponda)."
    )

    # ── Construir tabla departamentos ──
    # Mostrar solo departamentos donde el objetivo sí tiene votos.
    dept_codes = sorted(
        [d for d, v in objetivo["por_depto"].items() if v > 0],
        key=lambda d: objetivo["por_depto"].get(d, 0),
        reverse=True,
    )

    rows = []
    for cod in dept_codes:
        data_dep_global = mmv["deptos"].get(cod, {})

        total_mesas_div = sum(
            v["num_mesas"] for k, v in divipol["por_muni"].items()
            if k.startswith(cod + "_")
        )
        pot = sum(
            v["potencial_total"] for k, v in divipol["por_muni"].items()
            if k.startswith(cod + "_")
        )
        votos_obj = objetivo["por_depto"].get(cod, 0)

        row = {
            "Cód":                cod,
            "Departamento":       nombre_depto(cod, divipol),
            "Mesas reportadas":   len(data_dep_global.get("mesas", [])),
            "Total mesas":        total_mesas_div,
            "% mesas":            pct(len(data_dep_global.get("mesas", [])), total_mesas_div),
            "Potencial":          pot,
            "Votos objetivo (candidato/partido)":    votos_obj,
            "% participación objetivo": pct(votos_obj, pot),
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    if filtro_corp == "Senado":
        section("RESUMEN POR DEPARTAMENTO", "map")
        st.dataframe(df, use_container_width=True, height=400)

        # ── Gráfico departamento ──
        if not df.empty:
            fig2 = px.bar(
                df.head(20), x="Departamento", y="Votos objetivo (candidato/partido)",
                color="Votos objetivo (candidato/partido)", color_continuous_scale=["#1C2537", "#2196F3"],
                hover_data=["Cód", "% participación objetivo"],
                title=f"Votos objetivo por departamento ({objetivo_label})",
            )
            fig2.update_layout(coloraxis_showscale=False, height=350, xaxis_tickangle=-35)
            st.plotly_chart(plotly_defaults(fig2), use_container_width=True)

    # ── Drill-down municipios ──
    section("DRILL-DOWN POR MUNICIPIO", "travel_explore")

    deptos_disp = {f"{nombre_depto(cod, divipol)} [{cod}]": cod for cod in dept_codes}
    if not deptos_disp:
        return

    sel_dep_label = st.selectbox(
        "Seleccionar departamento", list(deptos_disp.keys()), key="geo_dep")
    sel_dep = deptos_disp[sel_dep_label]

    obj_muni_sel_dep = _pref_filter(objetivo["por_municipio"], sel_dep)
    # Mostrar solo municipios donde el objetivo sí tiene votos.
    muni_keys = sorted(
        [k for k, v in obj_muni_sel_dep.items() if v > 0],
        key=lambda k: obj_muni_sel_dep.get(k, 0),
        reverse=True,
    )

    munis_del_depto = {
        k: v for k, v in mmv["municipios"].items()
        if v["cod_depto"] == sel_dep and k in set(muni_keys)
    }

    rows_m = []
    for muni_key in muni_keys:
        data = munis_del_depto.get(muni_key, {})
        div_info = divipol["por_muni"].get(muni_key, {})
        pot = div_info.get("potencial_total", 0)
        votos_obj = obj_muni_sel_dep.get(muni_key, 0)

        row = {
            "Municipio":         div_info.get("nombre_municipio", muni_key),
            "Clave":             muni_key,
            "Mesas":             len(data.get("mesas", [])),
            "Potencial":         pot,
            "Votos objetivo (candidato/partido)":   votos_obj,
            "% participación objetivo": pct(votos_obj, pot),
        }
        rows_m.append(row)

    st.dataframe(pd.DataFrame(rows_m), use_container_width=True, height=380)
