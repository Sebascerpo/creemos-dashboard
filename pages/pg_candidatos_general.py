"""
pages/pg_candidatos_general.py
Pagina: Candidatos - explorador general de todos los candidatos.
Filtro por corporación/circunscripción y detalle por candidato.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st
import pandas as pd

from core.parser import (
    cargar_geo_candidato,
    cargar_mesa_candidato,
    cargar_geo_totales_circ,
    cargar_mesa_totales_circ,
)
from pages.shared import (
    fmt,
    pct,
    kpi,
    section,
    plotly_defaults,
    nombre_partido,
    nombre_candidato,
    nombre_depto,
    nombre_municipio_str,
    resolver_mmv_path,
)


def render(datos: dict):
    mmv = datos["mmv"]
    partidos = datos["partidos"]
    candidatos = datos["candidatos"]
    divipol = datos["divipol"]

    if not mmv:
        st.warning("No hay datos MMV cargados.")
        return

    section("ANALISIS POR CANDIDATO", "groups")

    filtro_tipo = st.radio(
        "Corporación",
        ["Senado", "Cámara"],
        horizontal=True,
        key="cand_tipo_radio",
    )

    if filtro_tipo == "Senado":
        corp_obj = "001"
        circ_obj = "0"
        color = "#DC2626"
    else:
        corp_obj = "002"
        circ_obj = "1"
        color = "#2563EB"

    candidatos_filtrados = {
        k: v
        for k, v in mmv["candidatos"].items()
        if (
            candidatos.get(k)
            and candidatos[k].get("corporacion") == corp_obj
            and candidatos[k].get("circunscripcion") == circ_obj
            and v.get("cod_candidato") not in {"000", "996", "997", "998"}
        )
    }

    if not candidatos_filtrados:
        st.info(
            f"No se encontraron candidatos para {filtro_tipo} "
            f"(corporación {corp_obj}, circunscripción {circ_obj})."
        )
        return

    # 1) Elegir departamento — uses por_depto which is in memory
    deptos_disp = sorted(
        {
            dep
            for v in candidatos_filtrados.values()
            for dep, votos_dep in v["por_depto"].items()
            if votos_dep > 0
        }
    )
    if not deptos_disp:
        st.info(f"No hay votos por departamento para {filtro_tipo}.")
        return

    deptos_opc = {f"{nombre_depto(d, divipol)} [{d}]": d for d in deptos_disp}
    sel_dep_label = st.selectbox(
        "Departamento",
        list(deptos_opc.keys()),
        key=f"cand_dep_sel_{corp_obj}_{circ_obj}",
    )
    sel_dep = deptos_opc[sel_dep_label]

    # 2) Candidatos con votos en ese departamento
    candidatos_dep = {
        k: v
        for k, v in candidatos_filtrados.items()
        if v["por_depto"].get(sel_dep, 0) > 0
    }
    if not candidatos_dep:
        st.info(f"No hay candidatos de {filtro_tipo} con votos en {sel_dep_label}.")
        return

    st.caption(
        "Los valores mostrados son votos individuales por candidato "
        "(excluye voto de lista 000, blanco 996, nulo 997 y no marcado 998)."
    )

    # Drill-down por candidato
    section("DETALLE POR CANDIDATO", "person_search")

    opciones = {}
    for k, v in sorted(
        candidatos_dep.items(),
        key=lambda x: x[1]["por_depto"].get(sel_dep, 0),
        reverse=True,
    ):
        votos_dep = v["por_depto"].get(sel_dep, 0)
        label = f"{nombre_candidato(k, candidatos)} - {fmt(votos_dep)} votos"
        opciones[label] = k

    filtro_txt = (
        st.text_input(
            "Escribe para buscar candidato",
            value="",
            key=f"cand_gen_filtro_{corp_obj}_{circ_obj}_{sel_dep}",
            placeholder="Ej: JULIANA / GERMAN / apellido...",
        )
        .strip()
        .casefold()
    )
    if filtro_txt:
        labels_disp = [lbl for lbl in opciones.keys() if filtro_txt in lbl.casefold()]
    else:
        labels_disp = list(opciones.keys())

    if not labels_disp:
        st.info("No hay candidatos que coincidan con la búsqueda.")
        return

    sel_label = st.selectbox(
        f"Buscar candidato ({filtro_tipo} · {sel_dep_label})",
        labels_disp,
        key=f"cand_gen_sel_{corp_obj}_{circ_obj}_{sel_dep}",
    )
    sel_key = opciones[sel_label]
    cd = candidatos_dep[sel_key]
    votos_cand_dep = cd["por_depto"].get(sel_dep, 0)

    # ── LAZY LOAD: geographic data for this candidate ──
    mmv_path_str = str(resolver_mmv_path())
    geo = cargar_geo_candidato(mmv_path_str, sel_key)
    por_muni_dep = {
        k: v for k, v in geo["por_municipio"].items() if k.startswith(sel_dep + "_")
    }
    por_puesto_dep = {
        k: v for k, v in geo["por_puesto"].items() if k.startswith(sel_dep + "_")
    }

    deptos_data = {sel_dep: votos_cand_dep}

    # ── LAZY LOAD: totals for the circunscripcion ──
    totales_circ_geo = cargar_geo_totales_circ(mmv_path_str, circ_obj)
    totales_muni = totales_circ_geo.get("por_municipio", {})
    totales_puesto = totales_circ_geo.get("por_puesto", {})

    total_validos_depto = sum(
        v for k, v in totales_muni.items() if k.startswith(sel_dep + "_")
    )
    if total_validos_depto <= 0:
        total_validos_depto = 1
        label_base_depto = "sin base válida disponible"
    else:
        label_base_depto = f"del total válido de {filtro_tipo.lower()} en el depto ({fmt(total_validos_depto)})"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi(
            "Votos del candidato",
            fmt(votos_cand_dep),
            nombre_partido(cd["cod_partido"], partidos)[:38],
            color,
        )
    with c2:
        kpi(
            "% sobre total",
            pct(votos_cand_dep, total_validos_depto),
            label_base_depto,
            color,
        )
    with c3:
        kpi("Departamento", sel_dep, nombre_depto(sel_dep, divipol), "#2563EB")
    with c4:
        kpi(
            "Municipios",
            str(len(por_muni_dep)),
            "con al menos 1 voto en el depto",
            "#059669",
        )

    col_a, col_b = st.columns(2)

    with col_a:
        section("VOTOS EN DEPARTAMENTO", "location_city")
        df_dep = pd.DataFrame(
            [
                {
                    "Departamento": nombre_depto(d, divipol),
                    "Cod": d,
                    "Votos": v,
                }
                for d, v in sorted(
                    deptos_data.items(), key=lambda x: x[1], reverse=True
                )
            ]
        )
        if not df_dep.empty:
            fig_d = px.bar(
                df_dep,
                x="Departamento",
                y="Votos",
                color="Votos",
                color_continuous_scale=["#F3F4F6", color],
                hover_data=["Cod"],
            )
            fig_d.update_layout(
                coloraxis_showscale=False, height=320, xaxis_tickangle=-35
            )
            st.plotly_chart(plotly_defaults(fig_d), use_container_width=True)

    with col_b:
        section("TOP 20 MUNICIPIOS", "location_on")
        top_m = sorted(por_muni_dep.items(), key=lambda x: x[1], reverse=True)[:20]
        df_m = pd.DataFrame(
            [
                {
                    "Municipio": nombre_municipio_str(k, divipol),
                    "Clave": k,
                    "Votos": v,
                }
                for k, v in top_m
            ]
        )
        if not df_m.empty:
            fig_m = px.bar(
                df_m,
                x="Votos",
                y="Municipio",
                orientation="h",
                color="Votos",
                color_continuous_scale=["#F3F4F6", color],
                hover_data=["Clave"],
            )
            fig_m.update_layout(
                yaxis={"categoryorder": "total ascending"},
                coloraxis_showscale=False,
                height=320,
            )
            st.plotly_chart(plotly_defaults(fig_m), use_container_width=True)

    section("DRILL-DOWN HASTA MESA", "travel_explore")
    st.markdown(
        '<p style="color:#6B7280;font-size:13px;margin-top:-8px;margin-bottom:16px;">'
        "Selecciona para ver el detalle hasta nivel de mesa individual.</p>",
        unsafe_allow_html=True,
    )

    if por_muni_dep:
        dep_nom = nombre_depto(sel_dep, divipol)
        st.markdown(
            f'<p style="color:#D97706;font-size:13px;font-weight:600;">'
            f"Departamento: {dep_nom} [{sel_dep}]</p>",
            unsafe_allow_html=True,
        )

        col_muni, col_puesto, col_mesa = st.columns(3)
        munis_disp = sorted(por_muni_dep.items(), key=lambda x: x[1], reverse=True)
        munis_opc = {
            divipol["por_muni"].get(k, {}).get("nombre_municipio", k): k
            for k, _ in munis_disp
        }

        sel_muni = None
        sel_puesto = None
        sel_mesa = None

        with col_muni:
            if munis_opc:
                sel_muni = munis_opc[
                    st.selectbox(
                        "Municipio",
                        list(munis_opc.keys()),
                        key=f"cand_dd_muni_{sel_key}_{sel_dep}",
                    )
                ]
            else:
                st.info("Sin municipios")

        puestos_opc = {}
        if sel_muni:
            puestos_disp = sorted(
                {
                    k: v
                    for k, v in por_puesto_dep.items()
                    if k.startswith(sel_muni + "_")
                }.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            for k, v in puestos_disp:
                p_info = divipol.get("por_puesto", {}).get(k, {})
                p_name = str(p_info.get("nombre_puesto", "")).strip()
                if p_name:
                    label = f"{p_name} ({fmt(v)} vts)"
                else:
                    label = f"Puesto {k.split('_')[2]}-{k.split('_')[3]} ({fmt(v)} vts)"
                puestos_opc[label] = k

        with col_puesto:
            if puestos_opc:
                sel_puesto = puestos_opc[
                    st.selectbox(
                        "Puesto de votación",
                        list(puestos_opc.keys()),
                        key=f"cand_dd_puesto_{sel_key}_{sel_dep}",
                    )
                ]
            else:
                st.info("Sin puestos")

        # ── LAZY LOAD: mesa data only when puesto selected ──
        por_mesa_dep = {}
        totales_mesa = {}
        mesas_opc = {}
        if sel_puesto:
            por_mesa_full = cargar_mesa_candidato(mmv_path_str, sel_key)
            por_mesa_dep = {
                k: v for k, v in por_mesa_full.items() if k.startswith(sel_dep + "_")
            }
            totales_mesa = cargar_mesa_totales_circ(mmv_path_str, circ_obj)
            mesas_disp = sorted(
                {
                    k: v for k, v in por_mesa_dep.items() if k.startswith(sel_puesto)
                }.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            mesas_opc = {f"Mesa {k.split('_')[4]} ({v} vts)": k for k, v in mesas_disp}

        with col_mesa:
            if mesas_opc:
                sel_mesa = mesas_opc[
                    st.selectbox(
                        "Mesa",
                        list(mesas_opc.keys()),
                        key=f"cand_dd_mesa_{sel_key}_{sel_dep}",
                    )
                ]
            else:
                st.info("Sin mesas")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        r1, r2, r3 = st.columns(3)
        votos_muni = por_muni_dep.get(sel_muni, 0) if sel_muni else 0
        votos_puesto = por_puesto_dep.get(sel_puesto, 0) if sel_puesto else 0
        votos_mesa = por_mesa_dep.get(sel_mesa, 0) if sel_mesa else 0
        total_muni = totales_muni.get(sel_muni, 0) if sel_muni else 0
        total_puesto = totales_puesto.get(sel_puesto, 0) if sel_puesto else 0
        total_mesa = totales_mesa.get(sel_mesa, 0) if sel_mesa else 0

        with r1:
            muni_nom = (
                divipol["por_muni"]
                .get(sel_muni, {})
                .get("nombre_municipio", sel_muni or "")
            )
            kpi(
                "Votos en municipio",
                fmt(votos_muni),
                f"{muni_nom} · {pct(votos_muni, total_muni)} del total del municipio ({fmt(total_muni)} válidos)",
                color,
            )
        with r2:
            kpi(
                "Votos en puesto",
                fmt(votos_puesto),
                f"{pct(votos_puesto, total_puesto)} del total del puesto ({fmt(total_puesto)} válidos)",
                color,
            )
        with r3:
            num_mesa = sel_mesa.split("_")[4] if sel_mesa else ""
            kpi(
                "Votos en mesa",
                fmt(votos_mesa),
                f"Mesa #{num_mesa} · {pct(votos_mesa, total_mesa)} del total de la mesa ({fmt(total_mesa)} válidos)",
                color,
            )
    else:
        st.info(
            "Sin datos de municipios disponibles para este candidato en el departamento."
        )

    section("DETALLE POR MUNICIPIO", "table_chart")
    df_muni_full = pd.DataFrame(
        [
            {
                "Municipio": nombre_municipio_str(k, divipol),
                "Votos": v,
                "% candidato": pct(v, max(votos_cand_dep, 1)),
                "% municipio": pct(v, totales_muni.get(k, 0)),
            }
            for k, v in sorted(por_muni_dep.items(), key=lambda x: x[1], reverse=True)
        ]
    )
    st.dataframe(df_muni_full, use_container_width=True, height=320)
