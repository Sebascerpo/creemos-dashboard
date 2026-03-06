"""
pages/pg_partidos.py
Pagina: Partidos
Dos tabs: Senado Nacional / Camara Antioquia.
Total por partido = votos de lista + votos de candidatos (válidos).
Incluye drill-down hasta mesa para ambos tabs.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st
import pandas as pd

from core.parser import (
    COD_ANTIOQUIA,
    cargar_mesa_partido_circ,
    cargar_mesa_totales_circ,
)
from pages.shared import (
    fmt,
    pct,
    kpi,
    section,
    plotly_defaults,
    nombre_partido,
    nombre_depto,
    nombre_municipio_str,
    resolver_mmv_path,
)


def _filter_prefix(src: dict, prefix: str) -> dict:
    return {k: v for k, v in src.items() if k.startswith(prefix)}


def _build_partidos_agg(mmv: dict) -> tuple[dict, dict]:
    """
    Totales por partido desde MMV ya consolidados por circunscripción:
    - Senado: circ 0 (nacional), votos válidos = lista + candidatos.
    - Cámara: circ 1, sólo Antioquia, votos válidos = lista + candidatos.
    SIN por_mesa (se carga bajo demanda).
    """
    partidos_por_circ = mmv.get("partidos_por_circ", {})
    part_senado = {}
    part_camara = {}

    for cod, d in partidos_por_circ.get("0", {}).items():
        votos = d.get("votos_validos_total", 0)
        if votos <= 0:
            continue
        part_senado[cod] = {
            "votos_total": votos,
            "por_depto": dict(d.get("por_depto_validos_total", {})),
            "por_municipio": dict(d.get("por_municipio_validos_total", {})),
            "por_puesto": dict(d.get("por_puesto_validos_total", {})),
            # por_mesa NO se carga: usar cargar_mesa_partido_circ()
            "_circ": "0",
            "_cod_partido": cod,
        }

    pref = COD_ANTIOQUIA + "_"
    for cod, d in partidos_por_circ.get("1", {}).items():
        v_ant = d.get("por_depto_validos_total", {}).get(COD_ANTIOQUIA, 0)
        if v_ant <= 0:
            continue
        part_camara[cod] = {
            "votos_total": v_ant,
            "por_depto": {COD_ANTIOQUIA: v_ant},
            "por_municipio": _filter_prefix(
                d.get("por_municipio_validos_total", {}), pref
            ),
            "por_puesto": _filter_prefix(d.get("por_puesto_validos_total", {}), pref),
            # por_mesa NO se carga: usar cargar_mesa_partido_circ()
            "_circ": "1",
            "_cod_partido": cod,
        }

    return part_senado, part_camara


def _render_drilldown_partido(
    data: dict,
    color: str,
    key_prefix: str,
    divipol: dict,
    totales_muni: dict,
    totales_puesto: dict,
    mmv_path_str: str,
    circ: str,
    cod_partido: str,
    fixed_dep: str | None = None,
):
    section("DRILL-DOWN HASTA MESA", "travel_explore")
    st.markdown(
        '<p style="color:#94A3B8;font-size:13px;margin-top:-8px;margin-bottom:16px;">'
        "Selecciona para ver el detalle hasta nivel de mesa individual.</p>",
        unsafe_allow_html=True,
    )

    por_muni = data["por_municipio"]
    por_puesto = data["por_puesto"]
    if not por_muni:
        st.info("Sin datos de municipios disponibles.")
        return

    if fixed_dep:
        sel_dep = fixed_dep
        dep_nom = nombre_depto(sel_dep, divipol)
        st.markdown(
            f'<p style="color:#F59E0B;font-size:13px;font-weight:600;">'
            f"Departamento: {dep_nom} [{sel_dep}]</p>",
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
                    "Departamento",
                    list(deptos_opc.keys()),
                    key=f"dd_dep_{key_prefix}",
                )
            ]

    munis_disp = sorted(
        {k: v for k, v in por_muni.items() if k.startswith(sel_dep + "_")}.items(),
        key=lambda x: x[1],
        reverse=True,
    )
    munis_opc = {
        f"{divipol['por_muni'].get(k, {}).get('nombre_municipio', k)} [{k}]": k
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
                    key=f"dd_muni_{key_prefix}",
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
                    "Puesto de votación",
                    list(puestos_opc.keys()),
                    key=f"dd_puesto_{key_prefix}",
                )
            ]
        else:
            st.info("Sin puestos")

    # ── LAZY LOAD: cargar por_mesa solo cuando hay puesto seleccionado ──
    por_mesa = {}
    totales_mesa = {}
    mesas_opc = {}
    if sel_puesto:
        por_mesa_full = cargar_mesa_partido_circ(mmv_path_str, circ, cod_partido)
        if fixed_dep:
            por_mesa = _filter_prefix(por_mesa_full, fixed_dep + "_")
        else:
            por_mesa = por_mesa_full
        totales_mesa = cargar_mesa_totales_circ(mmv_path_str, circ)
        mesas_disp = sorted(
            {k: v for k, v in por_mesa.items() if k.startswith(sel_puesto)}.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        mesas_opc = {f"Mesa {k.split('_')[4]} ({fmt(v)} vts)": k for k, v in mesas_disp}

    with col_mesa:
        if mesas_opc:
            sel_mesa = mesas_opc[
                st.selectbox(
                    "Mesa",
                    list(mesas_opc.keys()),
                    key=f"dd_mesa_{key_prefix}",
                )
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


def render(datos: dict):
    mmv = datos["mmv"]
    partidos = datos["partidos"]
    divipol = datos["divipol"]

    if not mmv:
        st.warning("No hay datos MMV cargados.")
        return

    part_senado, part_camara = _build_partidos_agg(mmv)
    total_sen = sum(d["votos_total"] for d in part_senado.values())
    total_cam = sum(d["votos_total"] for d in part_camara.values())
    totales_circ = mmv.get("totales_validos_por_circ", {})
    sen_totales_muni = totales_circ.get("0", {}).get("por_municipio", {})
    sen_totales_puesto = totales_circ.get("0", {}).get("por_puesto", {})
    cam_totales_muni = totales_circ.get("1", {}).get("por_municipio", {})
    cam_totales_puesto = totales_circ.get("1", {}).get("por_puesto", {})

    mmv_path_str = str(resolver_mmv_path())

    st.caption(
        "Total partido = votos de lista (000) + votos de candidatos "
        "para la corporación/circunscripción objetivo. "
        "No incluye blanco (996), nulo (997) ni no marcado (998)."
    )

    tab_sen, tab_cam = st.tabs(["Senado - Nacional", "Camara - Antioquia"])

    with tab_sen:
        section("PARTIDOS SENADO - NACIONAL", "how_to_vote")
        if not part_senado:
            st.info(
                "No hay datos de partidos para Senado (corporación 001, circunscripción 0)."
            )
        else:
            rows_s = [
                {
                    "Codigo": cod,
                    "Partido": nombre_partido(cod, partidos),
                    "Votos": d["votos_total"],
                    "% sobre Senado": pct(d["votos_total"], total_sen),
                    "Deptos": len(d["por_depto"]),
                    "Municipios": len(d["por_municipio"]),
                }
                for cod, d in sorted(
                    part_senado.items(), key=lambda x: x[1]["votos_total"], reverse=True
                )
            ]
            df_s = pd.DataFrame(rows_s)

            col_l, col_r = st.columns([2, 3])
            with col_l:
                st.dataframe(df_s, use_container_width=True, height=480)
            with col_r:
                fig_s = px.bar(
                    df_s.head(20),
                    x="Votos",
                    y="Partido",
                    orientation="h",
                    color="Votos",
                    color_continuous_scale=["#1C2537", "#E63946"],
                    hover_data=["% sobre Senado", "Deptos"],
                )
                fig_s.update_layout(
                    yaxis={"categoryorder": "total ascending"},
                    coloraxis_showscale=False,
                    height=480,
                )
                st.plotly_chart(plotly_defaults(fig_s), use_container_width=True)

            section("DETALLE PARTIDO - SENADO", "manage_search")
            opc_s = {
                f"{nombre_partido(c, partidos)} ({fmt(d['votos_total'])} votos)": c
                for c, d in sorted(
                    part_senado.items(), key=lambda x: x[1]["votos_total"], reverse=True
                )
            }
            sel_s = st.selectbox("Partido", list(opc_s.keys()), key="sel_sen")
            pd_s = part_senado[opc_s[sel_s]]

            c1, c2 = st.columns(2)
            with c1:
                df_ds = pd.DataFrame(
                    [
                        {
                            "Departamento": nombre_depto(d, divipol),
                            "Cod": d,
                            "Votos": v,
                        }
                        for d, v in sorted(
                            pd_s["por_depto"].items(), key=lambda x: x[1], reverse=True
                        )
                    ]
                )
                if not df_ds.empty:
                    fig_ds = px.bar(
                        df_ds,
                        x="Departamento",
                        y="Votos",
                        color="Votos",
                        color_continuous_scale=["#1C2537", "#E63946"],
                        hover_data=["Cod"],
                    )
                    fig_ds.update_layout(
                        coloraxis_showscale=False, height=300, xaxis_tickangle=-35
                    )
                    st.plotly_chart(plotly_defaults(fig_ds), use_container_width=True)
            with c2:
                top_ms = sorted(
                    pd_s["por_municipio"].items(), key=lambda x: x[1], reverse=True
                )[:20]
                df_ms = pd.DataFrame(
                    [
                        {
                            "Municipio": nombre_municipio_str(k, divipol),
                            "Clave": k,
                            "Votos": v,
                        }
                        for k, v in top_ms
                    ]
                )
                if not df_ms.empty:
                    fig_ms = px.bar(
                        df_ms,
                        x="Votos",
                        y="Municipio",
                        orientation="h",
                        color="Votos",
                        color_continuous_scale=["#1C2537", "#10B981"],
                        hover_data=["Clave"],
                    )
                    fig_ms.update_layout(
                        yaxis={"categoryorder": "total ascending"},
                        coloraxis_showscale=False,
                        height=300,
                    )
                    st.plotly_chart(plotly_defaults(fig_ms), use_container_width=True)

            _render_drilldown_partido(
                pd_s,
                color="#E63946",
                key_prefix=f"sen_{opc_s[sel_s]}",
                divipol=divipol,
                totales_muni=sen_totales_muni,
                totales_puesto=sen_totales_puesto,
                mmv_path_str=mmv_path_str,
                circ="0",
                cod_partido=opc_s[sel_s],
            )

    with tab_cam:
        section("PARTIDOS CAMARA - ANTIOQUIA", "how_to_vote")
        if not part_camara:
            st.info(
                "No hay datos de partidos para Cámara (corporación 002, circunscripción 1)."
            )
        else:
            rows_c = [
                {
                    "Codigo": cod,
                    "Partido": nombre_partido(cod, partidos),
                    "Votos": d["votos_total"],
                    "% sobre Camara Ant.": pct(d["votos_total"], total_cam),
                    "Municipios": len(d["por_municipio"]),
                }
                for cod, d in sorted(
                    part_camara.items(), key=lambda x: x[1]["votos_total"], reverse=True
                )
            ]
            df_c = pd.DataFrame(rows_c)

            col_l, col_r = st.columns([2, 3])
            with col_l:
                st.dataframe(df_c, use_container_width=True, height=480)
            with col_r:
                fig_c = px.bar(
                    df_c.head(20),
                    x="Votos",
                    y="Partido",
                    orientation="h",
                    color="Votos",
                    color_continuous_scale=["#1C2537", "#2196F3"],
                    hover_data=["% sobre Camara Ant.", "Municipios"],
                )
                fig_c.update_layout(
                    yaxis={"categoryorder": "total ascending"},
                    coloraxis_showscale=False,
                    height=480,
                )
                st.plotly_chart(plotly_defaults(fig_c), use_container_width=True)

            section("DETALLE PARTIDO - CAMARA ANTIOQUIA", "manage_search")
            opc_c = {
                f"{nombre_partido(c, partidos)} ({fmt(d['votos_total'])} votos)": c
                for c, d in sorted(
                    part_camara.items(), key=lambda x: x[1]["votos_total"], reverse=True
                )
            }
            sel_c = st.selectbox("Partido", list(opc_c.keys()), key="sel_cam")
            pd_c = part_camara[opc_c[sel_c]]

            top_mc = sorted(
                pd_c["por_municipio"].items(), key=lambda x: x[1], reverse=True
            )[:20]
            df_mc = pd.DataFrame(
                [
                    {
                        "Municipio": nombre_municipio_str(k, divipol),
                        "Clave": k,
                        "Votos": v,
                    }
                    for k, v in top_mc
                ]
            )
            if not df_mc.empty:
                fig_mc = px.bar(
                    df_mc,
                    x="Votos",
                    y="Municipio",
                    orientation="h",
                    color="Votos",
                    color_continuous_scale=["#1C2537", "#2196F3"],
                    hover_data=["Clave"],
                )
                fig_mc.update_layout(
                    yaxis={"categoryorder": "total ascending"},
                    coloraxis_showscale=False,
                    height=400,
                )
                st.plotly_chart(plotly_defaults(fig_mc), use_container_width=True)

            _render_drilldown_partido(
                pd_c,
                color="#2196F3",
                key_prefix=f"cam_{opc_c[sel_c]}",
                divipol=divipol,
                totales_muni=cam_totales_muni,
                totales_puesto=cam_totales_puesto,
                mmv_path_str=mmv_path_str,
                circ="1",
                cod_partido=opc_c[sel_c],
                fixed_dep=COD_ANTIOQUIA,
            )
