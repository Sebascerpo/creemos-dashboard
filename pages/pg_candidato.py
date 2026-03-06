"""
pages/pg_candidato.py
Pagina individual de candidato.
German Dario: solo_antioquia=True (drill-down fijo en Antioquia)
Juliana:      solo_antioquia=False (drill-down nacional)
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st
import pandas as pd

from core.parser import COD_ANTIOQUIA, cargar_mesa_candidato, cargar_mesa_totales_circ
from pages.shared import (
    fmt,
    pct,
    kpi,
    section,
    badge,
    plotly_defaults,
    nombre_partido,
    nombre_municipio_str,
    nombre_depto,
    resolver_mmv_path,
)


def render(
    datos,
    cand_key,
    nombre,
    cargo,
    color,
    solo_antioquia,
    expected_corporacion: str | None = None,
    expected_circ: str | None = None,
    expected_depto: str | None = None,
):
    mmv = datos["mmv"]
    partidos = datos["partidos"]
    candidatos = datos["candidatos"]
    divipol = datos["divipol"]

    if not mmv:
        st.warning("No hay datos MMV cargados.")
        return

    cd = mmv["candidatos"].get(cand_key)
    meta = candidatos.get(cand_key)

    cargo_b = badge("camara" if cargo == "Camara" or cargo == "Cámara" else "senado")
    scope_b = badge("antioquia" if solo_antioquia else "nacional")
    st.markdown(
        f'<div class="section-title">'
        f'<span style="font-size:20px">&#xe7fd;</span>'
        f"<span>{nombre}</span>{cargo_b}{scope_b}</div>",
        unsafe_allow_html=True,
    )

    if meta:
        warnings = []
        if expected_corporacion and meta.get("corporacion") != expected_corporacion:
            warnings.append(
                f"corporación esperada {expected_corporacion}, encontrada {meta.get('corporacion', '-')}"
            )
        if expected_circ and meta.get("circunscripcion") != expected_circ:
            warnings.append(
                f"circunscripción esperada {expected_circ}, encontrada {meta.get('circunscripcion', '-')}"
            )
        if expected_depto and meta.get("cod_depto") not in {"", "00", expected_depto}:
            warnings.append(
                f"depto esperado {expected_depto}, encontrado {meta.get('cod_depto', '-')}"
            )
        if warnings:
            st.warning("Validación catálogo candidato: " + " | ".join(warnings))

    if not cd:
        if cand_key in candidatos:
            st.warning(
                "El candidato existe en CANDIDATOS, pero no tiene registros en "
                "el MMV activo para el corte actual."
            )
        else:
            st.info("No se encontraron votos para este candidato en el archivo actual.")
        return

    st.caption(
        "Los valores mostrados son votos individuales del candidato "
        "(excluye voto de lista 000, blanco 996, nulo 997 y no marcado 998)."
    )

    if solo_antioquia:
        votos_total = cd["por_depto"].get(COD_ANTIOQUIA, 0)
        por_muni = {
            k: v
            for k, v in cd["por_municipio"].items()
            if k.startswith(COD_ANTIOQUIA + "_")
        }
        por_puesto = {
            k: v
            for k, v in cd["por_puesto"].items()
            if k.startswith(COD_ANTIOQUIA + "_")
        }
        deptos_data = {COD_ANTIOQUIA: cd["por_depto"].get(COD_ANTIOQUIA, 0)}

        if votos_total == 0 and cd["votos_total"] > 0:
            st.warning(
                f"Sin votos en el departamento configurado ({COD_ANTIOQUIA}). "
                f"Este candidato tiene {fmt(cd['votos_total'])} votos a nivel general."
            )
    else:
        votos_total = cd["votos_total"]
        por_muni = dict(cd["por_municipio"])
        por_puesto = dict(cd["por_puesto"])
        deptos_data = dict(cd["por_depto"])

    # Denominadores reales del territorio para el drill-down:
    # votos válidos (lista + candidatos) por circunscripción.
    circ_ref = (
        expected_circ
        or cd.get("circunscripcion")
        or (meta or {}).get("circunscripcion", "")
    ).strip()
    totales_circ = mmv.get("totales_validos_por_circ", {}).get(circ_ref, {})
    totales_muni = totales_circ.get("por_municipio", {})
    totales_puesto = totales_circ.get("por_puesto", {})
    stats_circ = mmv.get("stats_por_circ", {}).get(circ_ref, {})
    if solo_antioquia:
        total_ref = sum(
            v for k, v in totales_muni.items() if k.startswith(COD_ANTIOQUIA + "_")
        )
        total_ref_label = f"del total válido en Antioquia ({fmt(total_ref)})"
    else:
        total_ref = stats_circ.get("votos_validos_total", 0)
        total_ref_label = f"del total válido nacional ({fmt(total_ref)})"
    if total_ref <= 0:
        total_ref = 1
        total_ref_label = "sin base válida disponible"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi(
            "Total votos",
            fmt(votos_total),
            nombre_partido(cd["cod_partido"], partidos)[:40],
            color,
        )
    with c2:
        kpi("% sobre total", pct(votos_total, total_ref), total_ref_label, color)
    with c3:
        kpi("Departamentos", str(len(deptos_data)), "con al menos 1 voto", "#2196F3")
    with c4:
        kpi("Municipios", str(len(por_muni)), "con al menos 1 voto", "#10B981")

    section("TOP 30 MUNICIPIOS", "emoji_events")
    top30 = sorted(por_muni.items(), key=lambda x: x[1], reverse=True)[:30]
    df_top30 = pd.DataFrame(
        [
            {
                "#": i + 1,
                "Municipio": nombre_municipio_str(k, divipol),
                "Votos": v,
                "% candidato": pct(v, max(votos_total, 1)),
                "% municipio": pct(
                    v, mmv["municipios"].get(k, {}).get("votos_validos", 1)
                ),
            }
            for i, (k, v) in enumerate(top30)
        ]
    )
    st.dataframe(df_top30, use_container_width=True, height=400)

    if not solo_antioquia:
        col_l, col_r = st.columns(2)
        with col_l:
            section("VOTOS POR DEPARTAMENTO", "location_city")
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
                fig = px.bar(
                    df_dep,
                    x="Departamento",
                    y="Votos",
                    color="Votos",
                    color_continuous_scale=["#1C2537", color],
                    hover_data=["Cod"],
                )
                fig.update_layout(
                    coloraxis_showscale=False, height=320, xaxis_tickangle=-35
                )
                st.plotly_chart(plotly_defaults(fig), use_container_width=True)

        with col_r:
            section("TOP 20 MUNICIPIOS", "location_on")
            top20 = sorted(por_muni.items(), key=lambda x: x[1], reverse=True)[:20]
            df_mun = pd.DataFrame(
                [
                    {
                        "Municipio": nombre_municipio_str(k, divipol),
                        "Clave": k,
                        "Votos": v,
                    }
                    for k, v in top20
                ]
            )
            if not df_mun.empty:
                fig2 = px.bar(
                    df_mun,
                    x="Votos",
                    y="Municipio",
                    orientation="h",
                    color="Votos",
                    color_continuous_scale=["#1C2537", color],
                    hover_data=["Clave"],
                )
                fig2.update_layout(
                    yaxis={"categoryorder": "total ascending"},
                    coloraxis_showscale=False,
                    height=320,
                )
                st.plotly_chart(plotly_defaults(fig2), use_container_width=True)
    else:
        section("TOP 20 MUNICIPIOS", "location_on")
        top20 = sorted(por_muni.items(), key=lambda x: x[1], reverse=True)[:20]
        df_mun = pd.DataFrame(
            [
                {
                    "Municipio": nombre_municipio_str(k, divipol),
                    "Clave": k,
                    "Votos": v,
                }
                for k, v in top20
            ]
        )
        if not df_mun.empty:
            fig2 = px.bar(
                df_mun,
                x="Votos",
                y="Municipio",
                orientation="h",
                color="Votos",
                color_continuous_scale=["#1C2537", color],
                hover_data=["Clave"],
            )
            fig2.update_layout(
                yaxis={"categoryorder": "total ascending"},
                coloraxis_showscale=False,
                height=320,
            )
            st.plotly_chart(plotly_defaults(fig2), use_container_width=True)

    section("DRILL-DOWN HASTA MESA", "travel_explore")
    st.markdown(
        '<p style="color:#94A3B8;font-size:13px;margin-top:-8px;margin-bottom:16px;">'
        "Selecciona para ver el detalle hasta nivel de mesa individual.</p>",
        unsafe_allow_html=True,
    )

    if not por_muni:
        st.info("Sin datos de municipios disponibles.")
        return

    if solo_antioquia:
        sel_dep = COD_ANTIOQUIA
        dep_nom = nombre_depto(COD_ANTIOQUIA, divipol)
        st.markdown(
            f'<p style="color:#F59E0B;font-size:13px;font-weight:600;">'
            f"Departamento: {dep_nom}</p>",
            unsafe_allow_html=True,
        )
        col_muni, col_puesto, col_mesa = st.columns(3)
    else:
        deptos_disp = sorted(set(k.split("_")[0] for k in por_muni.keys()))
        deptos_opc = {f"{nombre_depto(d, divipol)} [{d}]": d for d in deptos_disp}
        col_dep, col_muni, col_puesto, col_mesa = st.columns(4)
        with col_dep:
            sel_dep = deptos_opc[
                st.selectbox(
                    "Departamento", list(deptos_opc.keys()), key=f"dd_dep_{cand_key}"
                )
            ]

    munis_disp = sorted(
        {k: v for k, v in por_muni.items() if k.startswith(sel_dep + "_")}.items(),
        key=lambda x: x[1],
        reverse=True,
    )
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
                    "Municipio", list(munis_opc.keys()), key=f"dd_muni_{cand_key}"
                )
            ]
        else:
            st.info("Sin municipios")
            return

    puestos_disp = sorted(
        {k: v for k, v in por_puesto.items() if k.startswith(sel_muni + "_")}.items(),
        key=lambda x: x[1],
        reverse=True,
    )
    puestos_opc = {}
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
                    "Puesto de votacion",
                    list(puestos_opc.keys()),
                    key=f"dd_puesto_{cand_key}",
                )
            ]
        else:
            st.info("Sin puestos")

    # ── LAZY LOAD: cargar por_mesa solo cuando hay puesto seleccionado ──
    mmv_path_str = str(resolver_mmv_path())
    por_mesa = {}
    totales_mesa = {}
    mesas_opc = {}
    if sel_puesto:
        por_mesa = cargar_mesa_candidato(mmv_path_str, cand_key)
        if solo_antioquia:
            por_mesa = {
                k: v for k, v in por_mesa.items() if k.startswith(COD_ANTIOQUIA + "_")
            }
        totales_mesa = cargar_mesa_totales_circ(mmv_path_str, circ_ref)
        mesas_disp = sorted(
            {k: v for k, v in por_mesa.items() if k.startswith(sel_puesto)}.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        mesas_opc = {f"Mesa {k.split('_')[4]} ({v} vts)": k for k, v in mesas_disp}

    with col_mesa:
        if mesas_opc:
            sel_mesa = mesas_opc[
                st.selectbox("Mesa", list(mesas_opc.keys()), key=f"dd_mesa_{cand_key}")
            ]
        else:
            st.info("Sin mesas")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    r1, r2, r3 = st.columns(3)

    votos_muni = por_muni.get(sel_muni, 0) if sel_muni else 0
    votos_puesto = por_puesto.get(sel_puesto, 0) if sel_puesto else 0
    votos_mesa = por_mesa.get(sel_mesa, 0) if sel_mesa else 0
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
