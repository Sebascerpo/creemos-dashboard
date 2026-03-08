"""
pages/pg_mesas_sin_votos.py
───────────────────────────
Mesas de Antioquia donde CREEMOS no tiene votos registrados.
Cruza DIVIPOL (universo) vs MMV (mesas con votos CREEMOS).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st

from core.parser import COD_ANTIOQUIA
from pages.shared import (
    DATA_DIR,
    fmt,
    pct,
    kpi,
    section,
)

# Partidos CREEMOS
_PARTIDOS_CREEMOS = {"01070", "01067"}


# ─────────────────────────── helpers ────────────────────────────


def _divipol_mesas_antioquia() -> dict[str, dict]:
    """
    Lee DIVIPOL.txt y construye un dict de TODAS las mesas regulares
    de Antioquia (sin puestos especiales).

    Retorna:
      {
        "01_001_01_01_000001": {
          "cod_muni": "001", "nom_muni": "MEDELLIN",
          "cod_zona": "01", "cod_puesto": "01",
          "nom_puesto": "SEC. ESC. LA ESPERANZA No 2",
          "num_mesa": "000001"
        },
        ...
      }
    """
    divipol_path = DATA_DIR / "DIVIPOL.txt"
    if not divipol_path.exists():
        return {}

    # Paso 1: leer puestos regulares con su num_mesas
    puestos: list[dict] = []
    with open(divipol_path, encoding="latin-1") as f:
        for line in f:
            line = line.rstrip("\n")
            if len(line) < 114:
                continue
            if line[0:2] != COD_ANTIOQUIA:
                continue
            # Puestos especiales tienen CIRCUNSCRIPCIÓN después de pos 114
            if line[114:].strip():
                continue

            cod_muni = line[2:5].strip()
            cod_zona = line[5:7].strip()
            cod_puesto = line[7:9].strip()
            nom_muni = line[21:51].strip()
            nom_puesto = line[51:91].strip()
            nm_str = line[108:114].strip()
            num_mesas = int(nm_str) if nm_str.isdigit() else 0

            puestos.append(
                {
                    "cod_muni": cod_muni,
                    "cod_zona": cod_zona,
                    "cod_puesto": cod_puesto,
                    "nom_muni": nom_muni,
                    "nom_puesto": nom_puesto,
                    "num_mesas": num_mesas,
                }
            )

    # Paso 2: expandir a mesas individuales
    resultado = {}
    for p in puestos:
        for i in range(1, p["num_mesas"] + 1):
            num_mesa = f"{i:06d}"
            mesa_key = (
                f"{COD_ANTIOQUIA}_{p['cod_muni']}"
                f"_{p['cod_zona']}_{p['cod_puesto']}_{num_mesa}"
            )
            resultado[mesa_key] = {
                "cod_muni": p["cod_muni"],
                "nom_muni": p["nom_muni"],
                "cod_zona": p["cod_zona"],
                "cod_puesto": p["cod_puesto"],
                "nom_puesto": p["nom_puesto"],
                "num_mesa": num_mesa,
            }
    return resultado


def _mesas_creemos_antioquia(mmv_path: Path) -> set[str]:
    """
    Escanea el MMV y devuelve el set de mesa_keys de Antioquia donde
    CREEMOS (partidos 01070 o 01067) tiene votos > 0 para cualquier
    candidato (incluyendo lista 000).
    """
    mesas = set()
    if not mmv_path.exists():
        return mesas

    with open(mmv_path, encoding="latin-1") as f:
        for linea in f:
            linea = linea.rstrip("\r\n")
            if len(linea) < 38:
                continue
            depto = linea[0:2]
            if depto != COD_ANTIOQUIA:
                continue
            partido = linea[22:27]
            if partido not in _PARTIDOS_CREEMOS:
                continue
            votos_str = linea[30:38].strip()
            votos = int(votos_str) if votos_str.isdigit() else 0
            if votos <= 0:
                continue
            muni = linea[2:5]
            zona = linea[5:7]
            puesto = linea[7:9]
            num_mesa = linea[9:15]
            mesa_key = f"{depto}_{muni}_{zona}_{puesto}_{num_mesa}"
            mesas.add(mesa_key)
    return mesas


def _to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


# ─────────────────────────── render ─────────────────────────────


def render(datos: dict):
    mmv = datos.get("mmv")
    if not mmv:
        st.warning("No hay datos MMV cargados.")
        return

    mmv_path = DATA_DIR / "PPP_MMV_DD_9999.txt"

    section("MESAS SIN VOTOS CREEMOS — ANTIOQUIA", "do_not_disturb_on")
    st.caption(
        "Identifica mesas habilitadas en Antioquia donde CREEMOS "
        "(partidos 01070 Senado y 01067 Camara) no tiene ningun voto registrado. "
        "Fuentes: DIVIPOL (universo) vs MMV oficial (votos)."
    )

    # ── Calcular ──
    with st.spinner("Calculando mesas sin votos CREEMOS..."):
        divipol_mesas = _divipol_mesas_antioquia()
        creemos_mesas = _mesas_creemos_antioquia(mmv_path)

    all_keys = set(divipol_mesas.keys())
    sin_votos_keys = all_keys - creemos_mesas
    con_votos_keys = all_keys & creemos_mesas

    n_total = len(all_keys)
    n_con = len(con_votos_keys)
    n_sin = len(sin_votos_keys)
    pct_sin = (n_sin / n_total * 100) if n_total > 0 else 0

    # ── KPIs ──
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Total mesas Antioquia", fmt(n_total), "DIVIPOL sin especiales", "#2563EB")
    with c2:
        kpi(
            "Con votos CREEMOS",
            fmt(n_con),
            f"{pct(n_con, n_total)} del total",
            "#059669",
        )
    with c3:
        kpi(
            "Sin votos CREEMOS",
            fmt(n_sin),
            f"{pct(n_sin, n_total)} del total",
            "#DC2626",
        )
    with c4:
        kpi(
            "% sin votos",
            f"{pct_sin:.1f}%",
            f"{fmt(n_sin)} de {fmt(n_total)}",
            "#D97706",
        )

    if n_sin == 0:
        st.success("Todas las mesas de Antioquia tienen votos CREEMOS.")
        return

    # ── Construir resumen por municipio y puesto ──
    muni_data: dict[str, dict] = {}  # cod_muni → {nom, total, sin}
    puesto_data: dict[str, dict] = (
        {}
    )  # cod_muni_zona_puesto → {nom, nom_muni, total, sin, mesas_sin}

    for mk in all_keys:
        info = divipol_mesas[mk]
        cm = info["cod_muni"]
        puesto_key = f"{cm}_{info['cod_zona']}_{info['cod_puesto']}"

        if cm not in muni_data:
            muni_data[cm] = {"nom_muni": info["nom_muni"], "total": 0, "sin": 0}
        muni_data[cm]["total"] += 1

        if puesto_key not in puesto_data:
            puesto_data[puesto_key] = {
                "cod_muni": cm,
                "nom_muni": info["nom_muni"],
                "nom_puesto": info["nom_puesto"],
                "total": 0,
                "sin": 0,
                "mesas_sin": [],
            }
        puesto_data[puesto_key]["total"] += 1

        if mk in sin_votos_keys:
            muni_data[cm]["sin"] += 1
            puesto_data[puesto_key]["sin"] += 1
            puesto_data[puesto_key]["mesas_sin"].append(mk)

    # ── Resumen por municipio ──
    df_muni = (
        pd.DataFrame(
            [
                {
                    "Municipio": d["nom_muni"],
                    "Cod": cm,
                    "Total mesas": d["total"],
                    "Sin votos CREEMOS": d["sin"],
                    "% sin votos": (
                        round(d["sin"] / d["total"] * 100, 1) if d["total"] > 0 else 0
                    ),
                }
                for cm, d in muni_data.items()
            ]
        )
        .sort_values("Sin votos CREEMOS", ascending=False)
        .reset_index(drop=True)
    )

    # ── Detalle por puesto ──
    df_puesto = (
        pd.DataFrame(
            [
                {
                    "Municipio": d["nom_muni"],
                    "Puesto": d["nom_puesto"],
                    "Total mesas": d["total"],
                    "Sin votos CREEMOS": d["sin"],
                    "% sin votos": (
                        round(d["sin"] / d["total"] * 100, 1) if d["total"] > 0 else 0
                    ),
                }
                for pk, d in puesto_data.items()
                if d["sin"] > 0
            ]
        )
        .sort_values("Sin votos CREEMOS", ascending=False)
        .reset_index(drop=True)
    )

    # ── Listado de mesas ──
    mesas_list = []
    for mk in sorted(sin_votos_keys):
        info = divipol_mesas[mk]
        n_mesa = int(info["num_mesa"])
        mesas_list.append(
            {
                "Municipio": info["nom_muni"],
                "Puesto": info["nom_puesto"],
                "Mesa": f"Mesa {n_mesa}",
            }
        )
    df_mesas = pd.DataFrame(mesas_list)

    # ── Descargas ──
    st.markdown("---")
    st.markdown("**DESCARGAS CSV**")
    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "Resumen por municipio",
            _to_csv(df_muni),
            "mesas_sin_votos_municipio.csv",
            "text/csv",
        )
    with d2:
        st.download_button(
            "Detalle por puesto",
            _to_csv(df_puesto),
            "mesas_sin_votos_puesto.csv",
            "text/csv",
        )
    with d3:
        st.download_button(
            "Listado completo de mesas",
            _to_csv(df_mesas),
            "mesas_sin_votos_listado.csv",
            "text/csv",
        )

    # ── Drill-down: Municipio → Puesto → Mesa ──
    st.markdown("---")
    st.markdown("**DRILL-DOWN POR MUNICIPIO**")

    for _, row in df_muni.iterrows():
        cm = row["Cod"]
        label = f"{row['Municipio']}  —  {row['Sin votos CREEMOS']} / {row['Total mesas']}  ({row['% sin votos']}%)"
        with st.expander(label):
            # Puestos de este municipio
            puestos_muni = {
                pk: d
                for pk, d in puesto_data.items()
                if d["cod_muni"] == cm and d["sin"] > 0
            }
            if not puestos_muni:
                st.info("Este municipio no tiene mesas sin votos CREEMOS.")
                continue

            for pk in sorted(
                puestos_muni, key=lambda x: puestos_muni[x]["sin"], reverse=True
            ):
                pd_item = puestos_muni[pk]
                puesto_label = (
                    f"{pd_item['nom_puesto']}  —  "
                    f"{pd_item['sin']} / {pd_item['total']} sin votos"
                )
                with st.expander(puesto_label):
                    if pd_item["mesas_sin"]:
                        mesa_display = [
                            {"Mesa": f"Mesa {int(divipol_mesas[m]['num_mesa'])}"}
                            for m in sorted(pd_item["mesas_sin"])
                        ]
                        st.dataframe(
                            pd.DataFrame(mesa_display),
                            use_container_width=True,
                            height=min(200, 35 * len(mesa_display) + 38),
                        )
