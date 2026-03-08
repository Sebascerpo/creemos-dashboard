"""
pages/pg_preconteo_escrutinio.py
────────────────────────────────
Compara Preconteo (PPP_MMV_DD_9999.txt) vs Escrutinio (ESCRUTINIO.txt).
Ambos archivos tienen el mismo formato MMV de 38 caracteres.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.parser import COD_ANTIOQUIA, procesar_mmv
from pages.shared import (
    DATA_DIR,
    fmt,
    kpi,
    section,
)


def _diff_str(pre: int, esc: int) -> str:
    d = esc - pre
    sign = "+" if d > 0 else ""
    return f"{sign}{d:,}"


def _diff_pct(pre: int, esc: int) -> str:
    if pre == 0:
        return "—"
    d = (esc - pre) / pre * 100
    sign = "+" if d > 0 else ""
    return f"{sign}{d:.2f}%"


def _sum_depto_validos(mmv: dict, circ: str) -> int:
    """Suma votos_validos_total de todos los partidos en la circ para Antioquia."""
    total = 0
    for _cod, pdata in mmv.get("partidos_por_circ", {}).get(circ, {}).items():
        total += pdata.get("por_depto_validos_total", {}).get(COD_ANTIOQUIA, 0)
    return total


def _mesas_ant(mmv: dict) -> int:
    """Cuenta mesas regulares de Antioquia (zona != 99)."""
    n = 0
    for muni_key, muni_data in mmv.get("municipios", {}).items():
        if muni_key.startswith(COD_ANTIOQUIA + "_"):
            for m in muni_data.get("mesas", set()):
                parts = m.split("_")
                if len(parts) >= 3 and parts[2] == "99":
                    continue
                n += 1
    return n


def _partido_candidatos(
    mmv: dict, cod_partido: str, candidatos_meta: dict
) -> list[dict]:
    """Devuelve lista de {nombre, votos} para cada candidato + lista del partido."""
    filas = []
    # Lista (000)
    for circ_id, circ_data in mmv.get("partidos_por_circ", {}).items():
        pd_item = circ_data.get(cod_partido, {})
        votos_lista = pd_item.get("votos_lista", 0)
        if votos_lista > 0:
            filas.append(
                {
                    "key": f"{cod_partido}_000",
                    "nombre": "LISTA (000)",
                    "votos": votos_lista,
                }
            )
            break  # Solo una circ relevante

    # Candidatos
    for ckey, cdata in mmv.get("candidatos", {}).items():
        if ckey.startswith(cod_partido + "_") and not ckey.endswith("_000"):
            meta = candidatos_meta.get(ckey, {})
            nombre = meta.get("nombre_completo", ckey)
            filas.append(
                {"key": ckey, "nombre": nombre, "votos": cdata.get("votos_total", 0)}
            )

    filas.sort(key=lambda x: x["votos"], reverse=True)
    return filas


def render(datos: dict):
    mmv_pre = datos.get("mmv")
    candidatos_meta = datos.get("candidatos", {})

    if not mmv_pre:
        st.warning("No hay datos de preconteo cargados.")
        return

    esc_path = DATA_DIR / "ESCRUTINIO.txt"
    if not esc_path.exists():
        st.warning(
            f"No se encontro el archivo de escrutinio: {esc_path}. "
            "Coloca el archivo ESCRUTINIO.txt en la carpeta data/."
        )
        return

    section("PRECONTEO VS ESCRUTINIO", "compare")

    with st.spinner("Cargando datos de escrutinio..."):
        mmv_esc = procesar_mmv(str(esc_path))

    if not mmv_esc:
        st.error("No se pudo procesar el archivo de escrutinio.")
        return

    stats_pre = mmv_pre.get("stats_por_circ", {})
    stats_esc = mmv_esc.get("stats_por_circ", {})

    # ═══════════════════════════════════════
    # §1 — TOTALES NACIONALES SENADO
    # ═══════════════════════════════════════
    section("TOTALES NACIONALES SENADO", "public")

    s_pre = stats_pre.get("0", {})
    s_esc = stats_esc.get("0", {})

    rows_nac = [
        {
            "Concepto": "Votos validos Senado",
            "Preconteo": s_pre.get("votos_validos_total", 0),
            "Escrutinio": s_esc.get("votos_validos_total", 0),
        },
        {
            "Concepto": "Votos blancos Senado",
            "Preconteo": s_pre.get("votos_blanco", 0),
            "Escrutinio": s_esc.get("votos_blanco", 0),
        },
        {
            "Concepto": "Votos nulos Senado",
            "Preconteo": s_pre.get("votos_nulo", 0),
            "Escrutinio": s_esc.get("votos_nulo", 0),
        },
        {
            "Concepto": "Total mesas reportadas",
            "Preconteo": mmv_pre.get("mesas_count", 0),
            "Escrutinio": mmv_esc.get("mesas_count", 0),
        },
    ]

    for r in rows_nac:
        r["Diferencia"] = _diff_str(r["Preconteo"], r["Escrutinio"])
        r["Var %"] = _diff_pct(r["Preconteo"], r["Escrutinio"])
        r["Preconteo"] = f"{r['Preconteo']:,}"
        r["Escrutinio"] = f"{r['Escrutinio']:,}"

    st.dataframe(pd.DataFrame(rows_nac), use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════
    # §2 — TOTALES ANTIOQUIA
    # ═══════════════════════════════════════
    section("TOTALES ANTIOQUIA — SENADO Y CAMARA", "map")

    val_sen_pre = _sum_depto_validos(mmv_pre, "0")
    val_sen_esc = _sum_depto_validos(mmv_esc, "0")
    val_cam_pre = _sum_depto_validos(mmv_pre, "1")
    val_cam_esc = _sum_depto_validos(mmv_esc, "1")
    mesas_ant_pre = _mesas_ant(mmv_pre)
    mesas_ant_esc = _mesas_ant(mmv_esc)

    rows_ant = [
        {
            "Concepto": "Votos validos Senado Antioquia",
            "Preconteo": val_sen_pre,
            "Escrutinio": val_sen_esc,
        },
        {
            "Concepto": "Votos validos Camara Antioquia",
            "Preconteo": val_cam_pre,
            "Escrutinio": val_cam_esc,
        },
        {
            "Concepto": "Mesas reportadas Antioquia",
            "Preconteo": mesas_ant_pre,
            "Escrutinio": mesas_ant_esc,
        },
    ]

    for r in rows_ant:
        r["Diferencia"] = _diff_str(r["Preconteo"], r["Escrutinio"])
        r["Var %"] = _diff_pct(r["Preconteo"], r["Escrutinio"])
        r["Preconteo"] = f"{r['Preconteo']:,}"
        r["Escrutinio"] = f"{r['Escrutinio']:,}"

    st.dataframe(pd.DataFrame(rows_ant), use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════
    # §3 — CREEMOS CANDIDATOS Y LISTAS
    # ═══════════════════════════════════════
    section("CREEMOS — CANDIDATOS Y LISTAS", "groups")

    tab_sen, tab_cam = st.tabs(["Senado (01070)", "Camara Antioquia (01067)"])

    for tab, cod_partido, label in [
        (tab_sen, "01070", "Senado"),
        (tab_cam, "01067", "Camara"),
    ]:
        with tab:
            cands_pre = _partido_candidatos(mmv_pre, cod_partido, candidatos_meta)
            cands_esc = _partido_candidatos(mmv_esc, cod_partido, candidatos_meta)

            # Merge by key
            pre_map = {c["key"]: c for c in cands_pre}
            esc_map = {c["key"]: c for c in cands_esc}
            all_keys = list(
                dict.fromkeys(
                    [c["key"] for c in cands_pre] + [c["key"] for c in cands_esc]
                )
            )

            rows_cand = []
            total_pre = 0
            total_esc = 0
            for ck in all_keys:
                p = pre_map.get(ck, {})
                e = esc_map.get(ck, {})
                nombre = p.get("nombre", e.get("nombre", ck))
                vp = p.get("votos", 0)
                ve = e.get("votos", 0)
                total_pre += vp
                total_esc += ve
                diff = ve - vp
                diff_pct = abs(diff) / max(vp, ve, 1) * 100
                rows_cand.append(
                    {
                        "Candidato": nombre,
                        "Preconteo": vp,
                        "Escrutinio": ve,
                        "Diferencia": diff,
                        "Dif %": round(diff_pct, 2),
                    }
                )

            # Total row
            total_diff = total_esc - total_pre
            total_diff_pct = abs(total_diff) / max(total_pre, total_esc, 1) * 100
            rows_cand.append(
                {
                    "Candidato": f"TOTAL {label.upper()}",
                    "Preconteo": total_pre,
                    "Escrutinio": total_esc,
                    "Diferencia": total_diff,
                    "Dif %": round(total_diff_pct, 2),
                }
            )

            df_cand = pd.DataFrame(rows_cand)

            def _highlight_diff(row):
                if abs(row["Dif %"]) > 1:
                    return ["background-color: #FEF2F2; color: #991B1B"] * len(row)
                return [""] * len(row)

            styled = df_cand.style.apply(_highlight_diff, axis=1).format(
                {
                    "Preconteo": "{:,}",
                    "Escrutinio": "{:,}",
                    "Diferencia": "{:+,}",
                    "Dif %": "{:.2f}%",
                }
            )

            st.dataframe(styled, use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════
    # DESCARGA CSV
    # ═══════════════════════════════════════
    st.markdown("---")
    st.markdown("**DESCARGA CSV**")

    # Build combined CSV
    csv_rows = []
    csv_rows.append(
        {
            "Seccion": "Nacional Senado",
            "Concepto": "",
            "Preconteo": "",
            "Escrutinio": "",
            "Diferencia": "",
            "Var %": "",
        }
    )
    for r in rows_nac:
        csv_rows.append(
            {
                "Seccion": "",
                "Concepto": r["Concepto"],
                "Preconteo": r["Preconteo"],
                "Escrutinio": r["Escrutinio"],
                "Diferencia": r["Diferencia"],
                "Var %": r["Var %"],
            }
        )
    csv_rows.append(
        {
            "Seccion": "Antioquia",
            "Concepto": "",
            "Preconteo": "",
            "Escrutinio": "",
            "Diferencia": "",
            "Var %": "",
        }
    )
    for r in rows_ant:
        csv_rows.append(
            {
                "Seccion": "",
                "Concepto": r["Concepto"],
                "Preconteo": r["Preconteo"],
                "Escrutinio": r["Escrutinio"],
                "Diferencia": r["Diferencia"],
                "Var %": r["Var %"],
            }
        )

    for cod_partido, label in [
        ("01070", "CREEMOS Senado"),
        ("01067", "CREEMOS Camara"),
    ]:
        csv_rows.append(
            {
                "Seccion": label,
                "Concepto": "",
                "Preconteo": "",
                "Escrutinio": "",
                "Diferencia": "",
                "Var %": "",
            }
        )
        cands_pre = _partido_candidatos(mmv_pre, cod_partido, candidatos_meta)
        cands_esc = _partido_candidatos(mmv_esc, cod_partido, candidatos_meta)
        pre_map = {c["key"]: c for c in cands_pre}
        esc_map = {c["key"]: c for c in cands_esc}
        all_keys = list(
            dict.fromkeys([c["key"] for c in cands_pre] + [c["key"] for c in cands_esc])
        )
        for ck in all_keys:
            p = pre_map.get(ck, {})
            e = esc_map.get(ck, {})
            nombre = p.get("nombre", e.get("nombre", ck))
            vp = p.get("votos", 0)
            ve = e.get("votos", 0)
            csv_rows.append(
                {
                    "Seccion": "",
                    "Concepto": nombre,
                    "Preconteo": f"{vp:,}",
                    "Escrutinio": f"{ve:,}",
                    "Diferencia": _diff_str(vp, ve),
                    "Var %": _diff_pct(vp, ve),
                }
            )

    df_csv = pd.DataFrame(csv_rows)
    st.download_button(
        "Descargar comparativa completa CSV",
        df_csv.to_csv(index=False).encode("utf-8"),
        "preconteo_vs_escrutinio.csv",
        "text/csv",
    )
