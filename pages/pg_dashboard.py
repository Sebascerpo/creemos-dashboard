"""
pages/pg_dashboard.py
──────────────────────
Página: Overview — resumen general, candidatos CREEMOS
y distribución por partido (dos tortas).
"""

from __future__ import annotations

import math
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from core.parser import COD_ANTIOQUIA
from pages.shared import (
    CANDIDATOS_PRINCIPALES,
    fmt,
    pct,
    kpi,
    section,
    plotly_defaults,
    nombre_partido,
    nombre_candidato,
    resolver_mmv_path,
)


def render(datos: dict):
    mmv = datos["mmv"]
    partidos = datos["partidos"]
    candidatos = datos["candidatos"]
    divipol = datos["divipol"]

    if not mmv:
        st.warning(
            f"No se encontró el archivo MMV activo. "
            f"Verifica `{resolver_mmv_path().name}` en la carpeta `/data`."
        )
        return

    total_validos = sum(d["votos_validos"] for d in mmv["municipios"].values())
    total_lista = sum(d["votos_total"] for d in mmv["partidos"].values())
    total_blancos = sum(d["votos_blanco"] for d in mmv["municipios"].values())
    total_nulos = sum(d["votos_nulo"] for d in mmv["municipios"].values())
    total_no_marcados = sum(d["votos_no_marcado"] for d in mmv["municipios"].values())
    total_votos = (
        total_validos + total_lista + total_blancos + total_nulos + total_no_marcados
    )
    total_mesas_divipol = sum(v["num_mesas"] for v in divipol["por_muni"].values())
    stats_circ = mmv.get("stats_por_circ", {})
    total_validos_senado = stats_circ.get("0", {}).get("votos_validos_total", 0)
    total_validos_camara = stats_circ.get("1", {}).get("votos_validos_total", 0)

    # ── KPIs generales ──
    section("RESUMEN GENERAL", "public")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi(
            "Votos validos Senado",
            fmt(total_validos_senado),
            f"{pct(total_validos_senado, total_votos)} del total global",
            "#2563EB",
        )
    # Votos válidos Cámara solo Antioquia
    total_validos_camara_ant = 0
    partidos_circ_cam = mmv.get("partidos_por_circ", {}).get("1", {})
    for _cod, pdata in partidos_circ_cam.items():
        dep_votos = pdata.get("por_depto_validos_total", {})
        total_validos_camara_ant += dep_votos.get(COD_ANTIOQUIA, 0)

    with c2:
        kpi(
            "Votos validos Camara Antioquia",
            fmt(total_validos_camara_ant),
            f"{pct(total_validos_camara_ant, total_votos)} del total global",
            "#059669",
        )
    with c3:
        kpi(
            "Mesas reportadas",
            fmt(mmv["mesas_count"]),
            f"de {fmt(total_mesas_divipol)} totales · {pct(mmv['mesas_count'], total_mesas_divipol)}",
            "#059669",
        )
    with c4:
        kpi(
            "Blancos",
            fmt(total_blancos),
            f"{pct(total_blancos, total_votos)} del escrutinio",
            "#D97706",
        )
    with c5:
        kpi(
            "Nulos",
            fmt(total_nulos),
            f"{pct(total_nulos, total_votos)} del escrutinio · No marcados: {fmt(total_no_marcados)}",
            "#6B7280",
        )

    # ── Candidatos CREEMOS ──
    section("CANDIDATOS CREEMOS", "groups")
    cols = st.columns(len(CANDIDATOS_PRINCIPALES))
    for col, (key, meta) in zip(cols, CANDIDATOS_PRINCIPALES.items()):
        cd = mmv["candidatos"].get(key)
        votos = cd["votos_total"] if cd else 0
        dep = len(cd["por_depto"]) if cd else 0
        mun = cd.get("n_municipios", 0) if cd else 0
        cargo_l = meta["cargo"].lower()
        if "senado" in cargo_l:
            den = total_validos_senado
            alcance = "del total válido Senado"
        elif "cámara" in cargo_l or "camara" in cargo_l:
            den = total_validos_camara
            alcance = "del total válido Cámara"
        else:
            den = total_votos
            alcance = "del total"
        with col:
            kpi(
                f"{meta['cargo']} — {meta['nombre']}",
                fmt(votos),
                f"{dep} deptos · {mun} municipios · {pct(votos, den)} {alcance}",
                meta["color"],
            )

    section("TOP 20 CANDIDATOS", "format_list_numbered")

    top_sen_rows = []
    top_cam_rows = []
    for cand_key, d in mmv["candidatos"].items():
        meta = candidatos.get(cand_key)
        if not meta:
            continue

        corp = meta.get("corporacion")
        circ = meta.get("circunscripcion")

        # Senado nacional
        if corp == "001" and circ == "0" and d.get("circunscripcion") == "0":
            votos = d["votos_total"]
            if votos > 0:
                top_sen_rows.append(
                    {
                        "Candidato": nombre_candidato(cand_key, candidatos),
                        "Partido": nombre_partido(d["cod_partido"], partidos)[:28],
                        "Votos": votos,
                    }
                )
        # Cámara territorial departamental
        elif (
            corp == "002"
            and circ == "1"
            and d.get("circunscripcion") == "1"
            and meta.get("cod_depto") == COD_ANTIOQUIA
        ):
            votos_ant = d["por_depto"].get(COD_ANTIOQUIA, 0)
            if votos_ant > 0:
                top_cam_rows.append(
                    {
                        "Candidato": nombre_candidato(cand_key, candidatos),
                        "Partido": nombre_partido(d["cod_partido"], partidos)[:28],
                        "Votos": votos_ant,
                    }
                )

    top_sen_rows = sorted(top_sen_rows, key=lambda x: x["Votos"], reverse=True)[:20]
    top_cam_rows = sorted(top_cam_rows, key=lambda x: x["Votos"], reverse=True)[:20]

    tab_sen_cand, tab_cam_cand = st.tabs(["Senado · Nacional", "Cámara · Antioquia"])

    with tab_sen_cand:
        if not top_sen_rows:
            st.info("No se encontraron candidatos de Senado con votos en este corte.")
        else:
            df_sen = pd.DataFrame(top_sen_rows)
            fig_sen = px.bar(
                df_sen,
                x="Votos",
                y="Candidato",
                orientation="h",
                color="Votos",
                color_continuous_scale=["#F3F4F6", "#DC2626"],
                hover_data=["Partido"],
            )
            fig_sen.update_layout(
                yaxis={"categoryorder": "total ascending"},
                coloraxis_showscale=False,
                height=520,
            )
            st.plotly_chart(plotly_defaults(fig_sen), use_container_width=True)

    with tab_cam_cand:
        if not top_cam_rows:
            st.info(
                "No se encontraron candidatos de Cámara Antioquia con votos en este corte."
            )
        else:
            df_cam = pd.DataFrame(top_cam_rows)
            fig_cam = px.bar(
                df_cam,
                x="Votos",
                y="Candidato",
                orientation="h",
                color="Votos",
                color_continuous_scale=["#F3F4F6", "#2563EB"],
                hover_data=["Partido"],
            )
            fig_cam.update_layout(
                yaxis={"categoryorder": "total ascending"},
                coloraxis_showscale=False,
                height=520,
            )
            st.plotly_chart(plotly_defaults(fig_cam), use_container_width=True)

    section("DISTRIBUCIÓN POR PARTIDO", "how_to_vote")
    # Totales por partido calculados desde MMV línea a línea:
    # Senado: circ 0 (nacional), lista + candidatos válidos.
    # Cámara: circ 1, sólo Antioquia (depto 01), lista + candidatos válidos.
    part_senado = {}
    part_camara_ant = {}
    partidos_por_circ = mmv.get("partidos_por_circ", {})

    for cod, d in partidos_por_circ.get("0", {}).items():
        v = d.get("votos_validos_total", 0)
        if v > 0:
            part_senado[cod] = v

    for cod, d in partidos_por_circ.get("1", {}).items():
        v_ant = d.get("por_depto_validos_total", {}).get(COD_ANTIOQUIA, 0)
        if v_ant > 0:
            part_camara_ant[cod] = v_ant

    total_sen = sum(part_senado.values())  # lista + candidatos válidos (circ 0)
    total_cam = sum(
        part_camara_ant.values()
    )  # lista + candidatos válidos (circ 1, Antioquia)

    # ── Umbral Senado CREEMOS ──
    section("SE SUPERA EL UMBRAL?", "rule")

    cand_sen_key = next(
        (
            k
            for k, m in CANDIDATOS_PRINCIPALES.items()
            if m.get("cargo", "").lower() == "senado"
        ),
        "01070_001",
    )
    party_creemos_sen = cand_sen_key.split("_")[0]
    votos_creemos_sen = part_senado.get(party_creemos_sen, 0)
    umbral_pct = 3.0
    base_umbral_senado = total_validos_senado
    umbral_votos = (
        math.ceil(base_umbral_senado * (umbral_pct / 100))
        if base_umbral_senado > 0
        else 0
    )
    supera_umbral = base_umbral_senado > 0 and votos_creemos_sen >= umbral_votos

    u1, u2, u3 = st.columns(3)
    with u1:
        kpi(
            "CREEMOS Senado",
            fmt(votos_creemos_sen),
            f"{pct(votos_creemos_sen, base_umbral_senado)} del total válido de Senado",
            "#DC2626",
        )
    with u2:
        kpi(
            "Umbral Senado (3%)",
            fmt(umbral_votos),
            f"sobre {fmt(base_umbral_senado)} votos válidos",
            "#2563EB",
        )
    with u3:
        if base_umbral_senado == 0:
            kpi(
                "Resultado",
                "Sin datos",
                "No hay votos válidos de Senado (circ 0) en MMV",
                "#6B7280",
            )
        else:
            estado = "Sí, supera" if supera_umbral else "No supera"
            detalle = (
                f"Ventaja: {fmt(votos_creemos_sen - umbral_votos)} votos"
                if supera_umbral
                else f"Faltan: {fmt(umbral_votos - votos_creemos_sen)} votos"
            )
            kpi("Resultado", estado, detalle, "#059669" if supera_umbral else "#D97706")

    tab_sen, tab_cam = st.tabs(["Senado · Nacional", "Cámara · Antioquia"])

    with tab_sen:
        if total_sen == 0:
            st.info("No se encontraron votos para Senado en este corte.")
        else:
            top_s = sorted(part_senado.items(), key=lambda x: x[1], reverse=True)[:20]
            labels_s = [nombre_partido(c, partidos)[:24] for c, _ in top_s]
            values_s = [v for _, v in top_s]
            otros_s = total_sen - sum(values_s)
            if otros_s > 0:
                labels_s.append("Otros")
                values_s.append(otros_s)
            fig_s = go.Figure(
                go.Pie(
                    labels=labels_s,
                    values=values_s,
                    hole=0.55,
                    textinfo="percent",
                    hovertemplate="%{label}<br>%{value:,} votos · %{percent}<extra></extra>",
                )
            )
            fig_s.update_layout(
                height=310,
                annotations=[
                    dict(
                        text=f"<b>{fmt(total_sen)}</b>",
                        x=0.5,
                        y=0.5,
                        font_size=13,
                        showarrow=False,
                        font_color="#111827",
                    )
                ],
            )
            st.plotly_chart(plotly_defaults(fig_s), use_container_width=True)

    with tab_cam:
        if total_cam == 0:
            st.info("No se encontraron votos para Cámara Antioquia " "en este corte.")
        else:
            top_c = sorted(part_camara_ant.items(), key=lambda x: x[1], reverse=True)[
                :20
            ]
            labels_c = [nombre_partido(c, partidos)[:24] for c, _ in top_c]
            values_c = [v for _, v in top_c]
            otros_c = total_cam - sum(values_c)
            if otros_c > 0:
                labels_c.append("Otros")
                values_c.append(otros_c)
            fig_c = go.Figure(
                go.Pie(
                    labels=labels_c,
                    values=values_c,
                    hole=0.55,
                    textinfo="percent",
                    hovertemplate="%{label}<br>%{value:,} votos · %{percent}<extra></extra>",
                    marker_colors=px.colors.qualitative.Set2,
                )
            )
            fig_c.update_layout(
                height=310,
                annotations=[
                    dict(
                        text=f"<b>{fmt(total_cam)}</b>",
                        x=0.5,
                        y=0.5,
                        font_size=13,
                        showarrow=False,
                        font_color="#111827",
                    )
                ],
            )
            st.plotly_chart(plotly_defaults(fig_c), use_container_width=True)
