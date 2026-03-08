"""
pages/pg_mesas_diferencia.py
────────────────────────────
Mesas de Antioquia donde la diferencia porcentual entre votos CREEMOS
Senado (01070) y Cámara (01067) supera un umbral configurable.
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

_PARTIDO_SENADO = "01070"
_PARTIDO_CAMARA = "01067"


# ─────────────────────────── helpers ────────────────────────────


def _cargar_votos_mesa(mmv_path: Path) -> dict[str, dict]:
    """
    Escanea el MMV y acumula votos CREEMOS por mesa para Senado y Cámara.
    Retorna {mesa_key: {"senado": int, "camara": int}}
    Solo mesas de Antioquia.
    """
    mesas: dict[str, dict] = {}

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
            if partido not in (_PARTIDO_SENADO, _PARTIDO_CAMARA):
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

            if mesa_key not in mesas:
                mesas[mesa_key] = {"senado": 0, "camara": 0}

            if partido == _PARTIDO_SENADO:
                mesas[mesa_key]["senado"] += votos
            else:
                mesas[mesa_key]["camara"] += votos

    return mesas


def _cargar_puestos_divipol() -> dict[str, dict]:
    """Lee nombres de puestos y municipios del DIVIPOL para Antioquia."""
    resultado = {}
    divipol_path = DATA_DIR / "DIVIPOL.txt"
    if not divipol_path.exists():
        return resultado
    with open(divipol_path, encoding="latin-1") as f:
        for line in f:
            line = line.rstrip("\n")
            if len(line) < 114:
                continue
            if line[0:2] != COD_ANTIOQUIA:
                continue
            cod_muni = line[2:5].strip()
            cod_zona = line[5:7].strip()
            cod_puesto = line[7:9].strip()
            nom_muni = line[21:51].strip()
            nom_puesto = line[51:91].strip()
            puesto_key = f"{cod_muni}_{cod_zona}_{cod_puesto}"
            resultado[puesto_key] = {
                "cod_muni": cod_muni,
                "nom_muni": nom_muni,
                "nom_puesto": nom_puesto,
            }
    return resultado


def _to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


# ─────────────────────────── render ─────────────────────────────


def render(datos: dict):
    mmv = datos.get("mmv")
    if not mmv:
        st.warning("No hay datos MMV cargados.")
        return

    mmv_path = DATA_DIR / "PPP_MMV_DD_9999.txt"

    section("MESAS CON DIFERENCIA SENADO VS CAMARA — CREEMOS", "warning")
    st.caption(
        "Compara votos CREEMOS entre Senado (01070) y Camara (01067) por mesa. "
        "Diferencias grandes pueden indicar comportamiento atipico. "
        "Mesas con votos en solo una corporacion entran automaticamente."
    )

    # ── Umbral ──
    umbral = st.slider(
        "Umbral de diferencia porcentual",
        min_value=5,
        max_value=50,
        value=10,
        step=1,
        format="%d%%",
    )

    # ── Calcular ──
    with st.spinner("Analizando diferencias por mesa..."):
        votos_mesa = _cargar_votos_mesa(mmv_path)
        puestos_info = _cargar_puestos_divipol()

    # Construir detalle por mesa
    filas = []
    for mesa_key, v in votos_mesa.items():
        vs = v["senado"]
        vc = v["camara"]
        maximo = max(vs, vc)
        diff_abs = abs(vs - vc)
        diff_pct = (diff_abs / maximo * 100) if maximo > 0 else 0

        parts = mesa_key.split("_")
        cod_muni = parts[1] if len(parts) >= 2 else ""
        cod_zona = parts[2] if len(parts) >= 3 else ""
        cod_puesto = parts[3] if len(parts) >= 4 else ""
        num_mesa = parts[4] if len(parts) >= 5 else ""
        puesto_key = f"{cod_muni}_{cod_zona}_{cod_puesto}"

        pi = puestos_info.get(puesto_key, {})
        nom_muni = pi.get("nom_muni", cod_muni)
        nom_puesto = pi.get("nom_puesto", puesto_key)
        n_mesa = int(num_mesa) if num_mesa.isdigit() else 0

        filas.append(
            {
                "mesa_key": mesa_key,
                "cod_muni": cod_muni,
                "Municipio": nom_muni,
                "Puesto": nom_puesto,
                "Mesa": f"Mesa {n_mesa}",
                "Votos Senado": vs,
                "Votos Camara": vc,
                "Diferencia": diff_abs,
                "Diferencia %": round(diff_pct, 1),
                "puesto_key": puesto_key,
            }
        )

    df_all = pd.DataFrame(filas)
    if df_all.empty:
        st.info("No se encontraron mesas con votos CREEMOS en Antioquia.")
        return

    n_total = len(df_all)
    df_alerta = df_all[df_all["Diferencia %"] > umbral].copy()
    n_alerta = len(df_alerta)
    n_ok = n_total - n_alerta
    pct_alerta = (n_alerta / n_total * 100) if n_total > 0 else 0

    # ── KPIs ──
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi(
            "Mesas analizadas",
            fmt(n_total),
            "con votos CREEMOS en Antioquia",
            "#2563EB",
        )
    with c2:
        kpi(
            f"Diferencia <= {umbral}%",
            fmt(n_ok),
            f"{pct(n_ok, n_total)} del total",
            "#059669",
        )
    with c3:
        kpi(
            f"Diferencia > {umbral}%",
            fmt(n_alerta),
            f"{pct(n_alerta, n_total)} del total",
            "#DC2626",
        )
    with c4:
        kpi(
            "% alertadas",
            f"{pct_alerta:.1f}%",
            f"{fmt(n_alerta)} de {fmt(n_total)}",
            "#D97706",
        )

    if n_alerta == 0:
        st.success(f"Ninguna mesa supera el umbral de {umbral}%.")
        return

    df_alerta = df_alerta.sort_values("Diferencia %", ascending=False).reset_index(
        drop=True
    )

    # ── Resumen por municipio ──
    muni_agg = defaultdict(lambda: {"nom": "", "total": 0, "alerta": 0})
    for _, row in df_all.iterrows():
        cm = row["cod_muni"]
        muni_agg[cm]["nom"] = row["Municipio"]
        muni_agg[cm]["total"] += 1
    for _, row in df_alerta.iterrows():
        muni_agg[row["cod_muni"]]["alerta"] += 1

    df_muni = (
        pd.DataFrame(
            [
                {
                    "Municipio": d["nom"],
                    "Cod": cm,
                    "Mesas analizadas": d["total"],
                    f"Diferencia > {umbral}%": d["alerta"],
                    "% alertadas": (
                        round(d["alerta"] / d["total"] * 100, 1)
                        if d["total"] > 0
                        else 0
                    ),
                }
                for cm, d in muni_agg.items()
                if d["alerta"] > 0
            ]
        )
        .sort_values(f"Diferencia > {umbral}%", ascending=False)
        .reset_index(drop=True)
    )

    # ── Resumen por puesto ──
    puesto_agg = defaultdict(
        lambda: {
            "nom_muni": "",
            "nom_puesto": "",
            "cod_muni": "",
            "total": 0,
            "alerta": 0,
        }
    )
    for _, row in df_all.iterrows():
        pk = row["puesto_key"]
        puesto_agg[pk]["nom_muni"] = row["Municipio"]
        puesto_agg[pk]["nom_puesto"] = row["Puesto"]
        puesto_agg[pk]["cod_muni"] = row["cod_muni"]
        puesto_agg[pk]["total"] += 1
    for _, row in df_alerta.iterrows():
        puesto_agg[row["puesto_key"]]["alerta"] += 1

    df_puesto = (
        pd.DataFrame(
            [
                {
                    "Municipio": d["nom_muni"],
                    "Puesto": d["nom_puesto"],
                    "Mesas analizadas": d["total"],
                    f"Diferencia > {umbral}%": d["alerta"],
                    "% alertadas": (
                        round(d["alerta"] / d["total"] * 100, 1)
                        if d["total"] > 0
                        else 0
                    ),
                }
                for pk, d in puesto_agg.items()
                if d["alerta"] > 0
            ]
        )
        .sort_values(f"Diferencia > {umbral}%", ascending=False)
        .reset_index(drop=True)
    )

    # ── CSV de detalle ──
    df_csv = df_alerta[
        [
            "Municipio",
            "Puesto",
            "Mesa",
            "Votos Senado",
            "Votos Camara",
            "Diferencia",
            "Diferencia %",
        ]
    ].copy()

    # ── Descargas ──
    st.markdown("---")
    st.markdown("**DESCARGAS CSV**")
    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "Resumen por municipio",
            _to_csv(df_muni),
            "mesas_diferencia_municipio.csv",
            "text/csv",
        )
    with d2:
        st.download_button(
            "Resumen por puesto",
            _to_csv(df_puesto),
            "mesas_diferencia_puesto.csv",
            "text/csv",
        )
    with d3:
        st.download_button(
            "Detalle completo por mesa",
            _to_csv(df_csv),
            "mesas_diferencia_detalle.csv",
            "text/csv",
        )

    # ── Drill-down ──
    st.markdown("---")
    st.markdown("**DRILL-DOWN POR MUNICIPIO**")

    for _, muni_row in df_muni.iterrows():
        cm = muni_row["Cod"]
        n_al = muni_row[f"Diferencia > {umbral}%"]
        n_an = muni_row["Mesas analizadas"]
        pct_v = muni_row["% alertadas"]
        label = f"{muni_row['Municipio']}  —  {n_al} / {n_an}  ({pct_v}%)"

        with st.expander(label):
            mesas_muni = df_alerta[df_alerta["cod_muni"] == cm]
            puestos_en_muni = mesas_muni["puesto_key"].unique()

            for pk in sorted(puestos_en_muni):
                pa = puesto_agg[pk]
                mesas_puesto = mesas_muni[mesas_muni["puesto_key"] == pk]
                puesto_label = f"{pa['nom_puesto']}  —  " f"{len(mesas_puesto)} alertas"
                with st.expander(puesto_label):
                    display_df = (
                        mesas_puesto[
                            [
                                "Mesa",
                                "Votos Senado",
                                "Votos Camara",
                                "Diferencia",
                                "Diferencia %",
                            ]
                        ]
                        .sort_values("Diferencia %", ascending=False)
                        .reset_index(drop=True)
                    )
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        height=min(300, 35 * len(display_df) + 38),
                    )
