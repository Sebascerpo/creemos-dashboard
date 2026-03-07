"""
pages/pg_curules_senado.py
Pagina: Curules Senado
Calculo de curules por cifra repartidora (D'Hondt).
"""
from __future__ import annotations

import math

import pandas as pd
import plotly.express as px
import streamlit as st

from pages.shared import (
    fmt,
    pct,
    kpi,
    section,
    plotly_defaults,
    nombre_partido,
)

CURULES_SENADO = 100
UMBRAL_PCT = 3.0
CIRC_SENADO_NACIONAL = "0"


def _votos_partido_senado_nacional(mmv: dict) -> dict[str, int]:
    """
    Votos validos de Senado nacional por partido:
    lista (000) + candidatos, excluyendo blanco/nulo/no marcado.
    """
    out: dict[str, int] = {}
    partidos_circ = mmv.get("partidos_por_circ", {}).get(CIRC_SENADO_NACIONAL, {})
    for cod_partido, d in partidos_circ.items():
        votos = int(d.get("votos_validos_total", 0) or 0)
        if votos > 0:
            out[cod_partido] = votos
    return out


def _reparto_dhondt(
    votos_partido: dict[str, int],
    total_curules: int,
) -> tuple[dict[str, int], list[dict], dict | None]:
    """
    Calcula curules por D'Hondt y retorna:
    - curules por partido
    - top de cocientes usados en la adjudicacion
    - ultimo cociente adjudicado (curul N)
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

    ultimo = top[-1] if top else None
    return curules, top, ultimo


def render(datos: dict):
    mmv = datos["mmv"]
    partidos = datos["partidos"]

    if not mmv:
        st.warning("No hay datos MMV cargados.")
        return

    section("CURULES SENADO (CIFRA REPARTIDORA)", "gavel")
    st.caption(
        "Base: Senado nacional (circunscripcion 0). "
        "Votos validos por partido = lista + candidatos."
    )

    votos_partido = _votos_partido_senado_nacional(mmv)
    if not votos_partido:
        st.info("No hay votos validos de Senado nacional para calcular curules.")
        return

    total_validos_senado = sum(votos_partido.values())
    umbral_votos = math.ceil(total_validos_senado * (UMBRAL_PCT / 100))

    partidos_habilitados = {
        cod: v for cod, v in votos_partido.items() if v >= umbral_votos
    }
    partidos_excluidos = {
        cod: v for cod, v in votos_partido.items() if v < umbral_votos
    }

    curules = {}
    cocientes_top: list[dict] = []
    ultimo_cociente = None
    if partidos_habilitados:
        curules, cocientes_top, ultimo_cociente = _reparto_dhondt(
            partidos_habilitados,
            CURULES_SENADO,
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi(
            "Total votos validos Senado",
            fmt(total_validos_senado),
            "Lista + candidatos",
            "#DC2626",
        )
    with c2:
        kpi(
            "Umbral calculado (3%)",
            fmt(umbral_votos),
            f"Sobre {fmt(total_validos_senado)} votos validos",
            "#2563EB",
        )
    with c3:
        kpi(
            "Partidos que superan umbral",
            fmt(len(partidos_habilitados)),
            f"Excluidos: {fmt(len(partidos_excluidos))}",
            "#059669",
        )
    with c4:
        if ultimo_cociente:
            kpi(
                "Ultimo cociente con curul (100)",
                f"{ultimo_cociente['cociente']:.2f}",
                f"{nombre_partido(ultimo_cociente['partido'], partidos)} [{ultimo_cociente['partido']}]",
                "#D97706",
            )
        else:
            kpi(
                "Ultimo cociente con curul (100)",
                "Sin datos",
                "Ningun partido supero el umbral",
                "#6B7280",
            )

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
                "% votos": pct(votos, total_validos_senado),
                "Curules": curules.get(cod, 0),
                "% curules": pct(curules.get(cod, 0), CURULES_SENADO),
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
            color_continuous_scale=["#F3F4F6", "#DC2626"],
            hover_data=["Codigo", "Votos validos", "% votos"],
            title=f"Curules asignadas (total = {CURULES_SENADO})",
        )
        fig.update_layout(coloraxis_showscale=False, height=520)
        st.plotly_chart(plotly_defaults(fig), use_container_width=True)

    st.caption(
        f"Total curules asignadas: {fmt(sum(curules.values()))} de {fmt(CURULES_SENADO)}."
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
                "% votos": pct(votos, total_validos_senado),
            }
            for cod, votos in sorted(
                partidos_excluidos.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ]
        st.dataframe(pd.DataFrame(rows_exc), use_container_width=True, height=300)

    with st.expander("Ver detalle de cocientes adjudicados (top 100)"):
        rows_coc = []
        for idx, item in enumerate(cocientes_top, start=1):
            rows_coc.append(
                {
                    "Curul": idx,
                    "Codigo": item["partido"],
                    "Partido": nombre_partido(item["partido"], partidos),
                    "Votos partido": item["votos_partido"],
                    "Divisor": item["divisor"],
                    "Cociente": round(item["cociente"], 6),
                }
            )
        st.dataframe(pd.DataFrame(rows_coc), use_container_width=True, height=420)
