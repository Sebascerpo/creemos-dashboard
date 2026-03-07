"""
pages/pg_curules_camara_antioquia.py
Pagina: Curules Camara Antioquia
Calculo de curules por cifra repartidora (D'Hondt).
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from core.parser import COD_ANTIOQUIA
from pages.shared import (
    CANDIDATOS_PRINCIPALES,
    fmt,
    pct,
    kpi,
    section,
    plotly_defaults,
    nombre_candidato,
    nombre_partido,
)

CURULES_CAMARA_ANTIOQUIA = 17
CIRC_CAMARA_TERRITORIAL = "1"
UMBRAL_FACTOR = 0.5  # 50% del cociente electoral


def _votos_partido_camara_antioquia(mmv: dict) -> dict[str, int]:
    """
    Votos validos por partido en Camara Antioquia:
    lista (000) + candidatos, circunscripcion 1, departamento 01.
    """
    out: dict[str, int] = {}
    partidos_circ = mmv.get("partidos_por_circ", {}).get(CIRC_CAMARA_TERRITORIAL, {})
    for cod_partido, d in partidos_circ.items():
        votos = int(d.get("por_depto_validos_total", {}).get(COD_ANTIOQUIA, 0) or 0)
        if votos > 0:
            out[cod_partido] = votos
    return out


def _reparto_dhondt(votos_partido: dict[str, int], total_curules: int) -> tuple[dict[str, int], list[dict]]:
    """
    D'Hondt para reparto de curules.
    Retorna:
    - curules por partido
    - cocientes ordenados de mayor a menor
    """
    cocientes: list[dict] = []
    for cod_partido, votos in votos_partido.items():
        for divisor in range(1, total_curules + 1):
            cocientes.append(
                {
                    "partido": cod_partido,
                    "votos_partido": votos,
                    "divisor": divisor,
                    "cociente": votos / divisor,
                }
            )

    cocientes = sorted(
        cocientes,
        key=lambda x: (-x["cociente"], -x["votos_partido"], x["partido"]),
    )
    top = cocientes[:total_curules]

    curules = {cod: 0 for cod in votos_partido.keys()}
    for item in top:
        curules[item["partido"]] += 1

    return curules, cocientes


def render(datos: dict):
    mmv = datos["mmv"]
    partidos = datos["partidos"]
    candidatos = datos["candidatos"]

    if not mmv:
        st.warning("No hay datos MMV cargados.")
        return

    section("CURULES CAMARA ANTIOQUIA (CIFRA REPARTIDORA)", "gavel")
    st.caption(
        "Base: Camara territorial Antioquia (circunscripcion 1, depto 01). "
        "Votos validos por partido = lista + candidatos."
    )

    votos_partido = _votos_partido_camara_antioquia(mmv)
    if not votos_partido:
        st.info("No hay votos validos de Camara Antioquia para calcular curules.")
        return

    total_validos = sum(votos_partido.values())
    cociente_electoral = (
        total_validos / CURULES_CAMARA_ANTIOQUIA if CURULES_CAMARA_ANTIOQUIA > 0 else 0
    )
    umbral = cociente_electoral * UMBRAL_FACTOR

    partidos_habilitados = {cod: v for cod, v in votos_partido.items() if v >= umbral}
    partidos_excluidos = {cod: v for cod, v in votos_partido.items() if v < umbral}

    curules = {}
    cocientes_all: list[dict] = []
    if partidos_habilitados:
        curules, cocientes_all = _reparto_dhondt(partidos_habilitados, CURULES_CAMARA_ANTIOQUIA)

    curul_17 = cocientes_all[CURULES_CAMARA_ANTIOQUIA - 1] if len(cocientes_all) >= CURULES_CAMARA_ANTIOQUIA else None
    curul_18 = cocientes_all[CURULES_CAMARA_ANTIOQUIA] if len(cocientes_all) > CURULES_CAMARA_ANTIOQUIA else None

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi(
            "Total votos validos",
            fmt(total_validos),
            "Camara Antioquia (lista + candidatos)",
            "#2563EB",
        )
    with c2:
        kpi(
            "Cociente electoral",
            f"{cociente_electoral:,.2f}".replace(",", "."),
            f"Total / {CURULES_CAMARA_ANTIOQUIA} curules",
            "#059669",
        )
    with c3:
        kpi(
            "Umbral calculado",
            f"{umbral:,.2f}".replace(",", "."),
            "50% del cociente electoral",
            "#D97706",
        )
    with c4:
        kpi(
            "Partidos habilitados",
            fmt(len(partidos_habilitados)),
            f"Excluidos por umbral: {fmt(len(partidos_excluidos))}",
            "#DC2626",
        )

    section("CORTE DE ULTIMAS CURULES", "rule")
    r1, r2 = st.columns(2)
    with r1:
        if curul_17:
            kpi(
                "Curul 17 (ultima asignada)",
                f"{curul_17['cociente']:.2f}",
                (
                    f"{nombre_partido(curul_17['partido'], partidos)} "
                    f"[{curul_17['partido']}] · divisor {curul_17['divisor']}"
                ),
                "#059669",
            )
        else:
            kpi("Curul 17 (ultima asignada)", "Sin datos", "No hubo reparto", "#6B7280")
    with r2:
        if curul_18:
            kpi(
                "Curul 18 (primera por fuera)",
                f"{curul_18['cociente']:.2f}",
                (
                    f"{nombre_partido(curul_18['partido'], partidos)} "
                    f"[{curul_18['partido']}] · divisor {curul_18['divisor']}"
                ),
                "#D97706",
            )
        else:
            kpi("Curul 18 (primera por fuera)", "Sin datos", "No hay cociente 18", "#6B7280")

    section("RESULTADO DE ASIGNACION", "how_to_vote")
    if not partidos_habilitados:
        st.warning("Ningun partido supera el umbral; no se pueden asignar curules.")
        return

    rows_res = []
    for cod, votos in partidos_habilitados.items():
        rows_res.append(
            {
                "Codigo": cod,
                "Partido": nombre_partido(cod, partidos),
                "Votos validos": votos,
                "% votos": pct(votos, total_validos),
                "Curules": curules.get(cod, 0),
                "% curules": pct(curules.get(cod, 0), CURULES_CAMARA_ANTIOQUIA),
            }
        )
    df_res = pd.DataFrame(rows_res).sort_values(
        by=["Curules", "Votos validos"],
        ascending=[False, False],
    )

    col_t, col_g = st.columns([2, 3])
    with col_t:
        st.dataframe(df_res, use_container_width=True, height=520)
    with col_g:
        df_plot = df_res.sort_values("Curules", ascending=True)
        fig = px.bar(
            df_plot,
            x="Curules",
            y="Partido",
            orientation="h",
            color="Curules",
            color_continuous_scale=["#F3F4F6", "#2563EB"],
            hover_data=["Codigo", "Votos validos", "% votos"],
            title=f"Curules asignadas (total = {CURULES_CAMARA_ANTIOQUIA})",
        )
        fig.update_layout(coloraxis_showscale=False, height=520)
        st.plotly_chart(plotly_defaults(fig), use_container_width=True)

    st.caption(
        f"Total curules asignadas: {fmt(sum(curules.values()))} de {fmt(CURULES_CAMARA_ANTIOQUIA)}."
    )

    section("PARTIDOS EXCLUIDOS POR UMBRAL", "block")
    if not partidos_excluidos:
        st.success("No hay partidos excluidos por umbral.")
    else:
        rows_exc = [
            {
                "Codigo": cod,
                "Partido": nombre_partido(cod, partidos),
                "Votos validos": votos,
                "% votos": pct(votos, total_validos),
            }
            for cod, votos in sorted(partidos_excluidos.items(), key=lambda x: x[1], reverse=True)
        ]
        st.dataframe(pd.DataFrame(rows_exc), use_container_width=True, height=300)

    with st.expander("Ver detalle de cocientes (ordenados)"):
        rows_coc = []
        for idx, item in enumerate(cocientes_all, start=1):
            rows_coc.append(
                {
                    "Orden": idx,
                    "Codigo": item["partido"],
                    "Partido": nombre_partido(item["partido"], partidos),
                    "Votos partido": item["votos_partido"],
                    "Divisor": item["divisor"],
                    "Cociente": round(item["cociente"], 6),
                    "Entra curul": "SI" if idx <= CURULES_CAMARA_ANTIOQUIA else "NO",
                }
            )
        st.dataframe(pd.DataFrame(rows_coc), use_container_width=True, height=420)

    # ── Ranking interno CREEMOS (voto individual candidato) ──
    section("RANKING INTERNO CREEMOS - CANDIDATOS", "groups")
    cand_cam_key = next(
        (k for k, m in CANDIDATOS_PRINCIPALES.items() if "camara" in m.get("cargo", "").lower()),
        "01067_117",
    )
    party_creemos = cand_cam_key.split("_")[0]

    rows_creemos = []
    for cand_key, d in mmv.get("candidatos", {}).items():
        if d.get("cod_partido") != party_creemos:
            continue
        if d.get("circunscripcion") != CIRC_CAMARA_TERRITORIAL:
            continue
        votos_ind = int(d.get("por_depto", {}).get(COD_ANTIOQUIA, 0) or 0)
        if votos_ind <= 0:
            continue
        rows_creemos.append(
            {
                "Codigo candidato": d.get("cod_candidato", cand_key.split("_")[1] if "_" in cand_key else cand_key),
                "Candidato": nombre_candidato(cand_key, candidatos),
                "Votos individuales": votos_ind,
            }
        )

    if not rows_creemos:
        st.info("No hay votos individuales de candidatos CREEMOS en Camara Antioquia.")
    else:
        df_creemos = pd.DataFrame(rows_creemos).sort_values(
            by="Votos individuales",
            ascending=False,
        ).reset_index(drop=True)
        df_creemos.insert(0, "Rank", df_creemos.index + 1)
        total_creemos_ind = int(df_creemos["Votos individuales"].sum())
        df_creemos["% sobre CREEMOS (individual)"] = df_creemos["Votos individuales"].apply(
            lambda x: pct(x, total_creemos_ind)
        )
        df_creemos["% sobre total Camara Antioquia"] = df_creemos["Votos individuales"].apply(
            lambda x: pct(x, total_validos)
        )
        st.caption(
            "Este ranking usa solo voto individual a candidato "
            "(excluye voto de lista 000)."
        )
        st.dataframe(df_creemos, use_container_width=True, height=420)
