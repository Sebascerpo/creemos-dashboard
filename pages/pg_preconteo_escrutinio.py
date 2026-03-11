"""
pages/pg_preconteo_escrutinio.py
────────────────────────────────
Compara Preconteo (PPP_MMV_DD_9999.txt) vs Escrutinio (ESCRUTINIO.txt).
Ambos archivos tienen el mismo formato MMV de 38 caracteres.
"""

from __future__ import annotations

import os
import math
import pandas as pd
import plotly.express as px
import streamlit as st

from core.parser import COD_ANTIOQUIA, procesar_mmv
from pages.shared import (
    DATA_DIR,
    fmt,
    kpi,
    section,
    nombre_partido,
    nombre_candidato,
    formatear_mesa_completa,
    pct,
    plotly_defaults,
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


def _get_mtime(path_str: str) -> float:
    try:
        return os.path.getmtime(path_str)
    except Exception:
        return 0.0


@st.cache_data(show_spinner=False, ttl=3600)
@st.cache_data(show_spinner=False, ttl=3600)
def _cached_mesas_candidato(
    path_str: str,
    cod_partido: str,
    cod_candidato: str,
    circ: str,
    depto: str,
    _mtime: float,
) -> dict[str, int]:
    out: dict[str, int] = {}
    with open(path_str, encoding="latin-1") as f:
        for line in f:
            if not line.strip() or len(line) < 38:
                continue
            if line[0:2] != depto:
                continue
            if line[21:22] != circ:
                continue
            if line[22:27] != cod_partido:
                continue
            if line[27:30] != cod_candidato:
                continue
            votos_str = line[30:38].strip()
            if not votos_str.isdigit():
                continue
            votos = int(votos_str)
            if votos <= 0:
                continue
            mesa_key = f"{line[0:2]}_{line[2:5]}_{line[5:7]}_{line[7:9]}_{line[9:15]}"
            out[mesa_key] = out.get(mesa_key, 0) + votos
    return out


def cargar_mesas_candidato(path: Path, cod_partido: str, cod_candidato: str, circ: str, depto: str) -> dict[str, int]:
    return _cached_mesas_candidato(
        str(path),
        cod_partido,
        cod_candidato,
        circ,
        depto,
        _get_mtime(str(path)),
    )


def _cached_compare_preconteo_escrutinio(
    pre_path_str: str,
    esc_path_str: str,
    circ: str,
    depto: str,
    _mtime_pre: float,
    _mtime_esc: float,
) -> dict:
    # Build mesa set from escrutinio (valid votes only)
    mesas_esc = set()
    cand_esc = {}
    mesa_tot_esc = {}

    with open(esc_path_str, encoding="latin-1") as f:
        for line in f:
            if not line.strip() or len(line) < 38:
                continue
            if line[0:2] != depto:
                continue
            if line[21:22] != circ:
                continue
            cand = line[27:30]
            if cand in ("996", "997", "998"):
                continue
            votos_str = line[30:38].strip()
            if not votos_str.isdigit():
                continue
            votos = int(votos_str)
            if votos <= 0:
                continue
            mesa_key = f"{line[0:2]}_{line[2:5]}_{line[5:7]}_{line[7:9]}_{line[9:15]}"
            mesas_esc.add(mesa_key)
            key = f"{line[22:27]}_{cand}"
            cand_esc[key] = cand_esc.get(key, 0) + votos
            mesa_tot_esc[mesa_key] = mesa_tot_esc.get(mesa_key, 0) + votos

    cand_pre = {}
    mesa_tot_pre = {}

    with open(pre_path_str, encoding="latin-1") as f:
        for line in f:
            if not line.strip() or len(line) < 38:
                continue
            if line[0:2] != depto:
                continue
            if line[21:22] != circ:
                continue
            cand = line[27:30]
            if cand in ("996", "997", "998"):
                continue
            mesa_key = f"{line[0:2]}_{line[2:5]}_{line[5:7]}_{line[7:9]}_{line[9:15]}"
            if mesa_key not in mesas_esc:
                continue
            votos_str = line[30:38].strip()
            if not votos_str.isdigit():
                continue
            votos = int(votos_str)
            if votos <= 0:
                continue
            key = f"{line[22:27]}_{cand}"
            cand_pre[key] = cand_pre.get(key, 0) + votos
            mesa_tot_pre[mesa_key] = mesa_tot_pre.get(mesa_key, 0) + votos

    return {
        "mesas_esc": mesas_esc,
        "cand_pre": cand_pre,
        "cand_esc": cand_esc,
        "mesa_pre": mesa_tot_pre,
        "mesa_esc": mesa_tot_esc,
    }



CURULES_CAMARA_ANTIOQUIA = 17
CIRC_CAMARA_TERRITORIAL = "1"
UMBRAL_FACTOR = 0.5  # 50% del cociente electoral


def _votos_partido_camara_antioquia_escrutinio(mmv: dict) -> dict[str, int]:
    """
    Votos validos por partido en Camara Antioquia (escrutinio):
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
    Retorna curules por partido y cocientes ordenados.
    """
    cocientes: list[dict] = []
    for cod_partido, votos in votos_partido.items():
        for divisor in range(1, total_curules + 1):
            cocientes.append({
                "partido": cod_partido,
                "votos_partido": votos,
                "divisor": divisor,
                "cociente": votos / divisor,
            })

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
    mmv_pre = datos.get("mmv")
    candidatos_meta = datos.get("candidatos", {})
    partidos = datos.get("partidos", {})
    divipol = datos.get("divipol", {})

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
    # §4 — COMPARACION EN TIEMPO REAL (ESCRUTINIO VS PRECONTEO)
    # ═══════════════════════════════════════
    section("COMPARACION EN TIEMPO REAL — CAMARA ANTIOQUIA", "table")
    # (caption removida por solicitud)

    pre_path = DATA_DIR / "PPP_MMV_DD_9999.txt"
    if not pre_path.exists():
        st.warning(f"No se encontro el archivo de preconteo: {pre_path}.")
    else:
        with st.spinner("Comparando mesas de escrutinio contra preconteo..."):
            comp = _cached_compare_preconteo_escrutinio(
                str(pre_path),
                str(esc_path),
                "1",
                "01",
                _get_mtime(str(pre_path)),
                _get_mtime(str(esc_path)),
            )

        mesas_esc = comp["mesas_esc"]
        cand_pre = comp["cand_pre"]
        cand_esc = comp["cand_esc"]
        mesa_pre = comp["mesa_pre"]
        mesa_esc = comp["mesa_esc"]

        total_pre = sum(cand_pre.values())
        total_esc = sum(cand_esc.values())
        total_diff = total_esc - total_pre

        # (cards removidas por solicitud)

        # Mesa-level differences
        rows_mesa = []
        same = 0
        pre_only = 0
        esc_only = 0
        for mesa_key in sorted(mesas_esc):
            p = mesa_pre.get(mesa_key, 0)
            e = mesa_esc.get(mesa_key, 0)
            if p == e:
                same += 1
            else:
                rows_mesa.append({
                    "Mesa": formatear_mesa_completa(mesa_key, divipol),
                    "Preconteo": p,
                    "Escrutinio": e,
                    "Diferencia": e - p,
                })
            if p > 0 and e == 0:
                pre_only += 1
            if e > 0 and p == 0:
                esc_only += 1

        # (cards removidas por solicitud)

        st.markdown("**Diferencias por mesa — German Dario Hoyos (01067-117)**")
        german_pre = cargar_mesas_candidato(pre_path, "01067", "117", "1", "01")
        german_esc = cargar_mesas_candidato(esc_path, "01067", "117", "1", "01")
        mesas_german = sorted(set(german_pre) | set(german_esc))
        rows_german = []
        for mesa_key in mesas_german:
            if mesa_key not in mesas_esc:
                continue
            p = german_pre.get(mesa_key, 0)
            e = german_esc.get(mesa_key, 0)
            if p == e:
                continue
            depto, muni, zona, puesto, mesa = mesa_key.split("_")
            muni_key = f"{depto}_{muni}"
            puesto_key = f"{depto}_{muni}_{zona}_{puesto}"
            rows_german.append({
                "MesaKey": mesa_key,
                "MunicipioKey": muni_key,
                "PuestoKey": puesto_key,
                "MesaNum": mesa,
                "Mesa": formatear_mesa_completa(mesa_key, divipol),
                "Preconteo": p,
                "Escrutinio": e,
                "Diferencia": e - p,
            })

        german_total_pre = sum(german_pre.get(m, 0) for m in mesas_esc)
        german_total_esc = sum(german_esc.get(m, 0) for m in mesas_esc)
        german_total_diff = german_total_esc - german_total_pre
        sum_rows_diff = sum(r["Diferencia"] for r in rows_german)

        st.caption(
            f"Total German en mesas con escrutinio — "
            f"Preconteo: {fmt(german_total_pre)} · "
            f"Escrutinio: {fmt(german_total_esc)} · "
            f"Diferencia: {fmt(german_total_diff)}"
        )
        if sum_rows_diff != german_total_diff:
            st.warning(
                "La suma de diferencias por mesa no coincide con el total. "
                f"Suma mesas: {fmt(sum_rows_diff)} · Total: {fmt(german_total_diff)}"
            )

        if rows_german:
            # Drill-down por municipio -> puesto -> mesa
            muni_data = {}
            for row in rows_german:
                muni_key = row["MunicipioKey"]
                puesto_key = row["PuestoKey"]
                muni_info = divipol.get("por_muni", {}).get(muni_key, {})
                puesto_info = divipol.get("por_puesto", {}).get(puesto_key, {})
                muni_name = muni_info.get("nombre_municipio", muni_key)
                puesto_name = puesto_info.get("nombre_puesto", puesto_key)

                m = muni_data.setdefault(
                    muni_key,
                    {"nombre": muni_name, "total": 0, "diff": 0, "puestos": {}},
                )
                m["total"] += 1
                m["diff"] += row["Diferencia"]
                pmap = m["puestos"].setdefault(
                    puesto_key,
                    {"nombre": puesto_name, "total": 0, "diff": 0, "mesas": []},
                )
                pmap["total"] += 1
                pmap["diff"] += row["Diferencia"]
                mesa_num = row.get("MesaNum", "")
                if str(mesa_num).isdigit():
                    mesa_label = f"Mesa {int(mesa_num)}"
                else:
                    mesa_label = f"Mesa {mesa_num}".strip()
                pmap["mesas"].append({
                    "MesaKey": row["MesaKey"],
                    "Mesa": mesa_label,
                    "Preconteo": row["Preconteo"],
                    "Escrutinio": row["Escrutinio"],
                    "Diferencia": row["Diferencia"],
                })

            st.markdown("---")
            st.markdown("**DRILL-DOWN POR MUNICIPIO**")
            def _fmt_diff(valor: int) -> str:
                signo = "+" if valor > 0 else ""
                return f"{signo}{fmt(valor)}"

            muni_keys = sorted(
                muni_data.keys(),
                key=lambda k: (abs(muni_data[k]["diff"]), muni_data[k]["nombre"]),
                reverse=True,
            )
            sel_muni = st.selectbox(
                "Municipio",
                muni_keys,
                format_func=lambda k: f"{muni_data[k]['nombre']} ({_fmt_diff(muni_data[k]['diff'])})",
                key="german_muni",
            )
            puestos = muni_data[sel_muni]["puestos"] if sel_muni else {}
            puesto_keys = sorted(
                puestos.keys(),
                key=lambda k: (abs(puestos[k]["diff"]), puestos[k]["nombre"]),
                reverse=True,
            )
            sel_puesto = st.selectbox(
                "Puesto de votación",
                puesto_keys,
                format_func=lambda k: f"{puestos[k]['nombre']} ({_fmt_diff(puestos[k]['diff'])})",
                key="german_puesto",
            )
            mesas = puestos[sel_puesto]["mesas"] if sel_puesto else []
            mesa_map = {m["MesaKey"]: m for m in mesas}
            mesa_keys = sorted(
                mesa_map.keys(),
                key=lambda k: (abs(mesa_map[k]["Diferencia"]), mesa_map[k]["Mesa"]),
                reverse=True,
            )
            sel_mesa = st.selectbox(
                "Mesa",
                mesa_keys,
                format_func=lambda k: f"{mesa_map[k]['Mesa']} ({_fmt_diff(mesa_map[k]['Diferencia'])})",
                key="german_mesa",
            )

            if sel_mesa:
                row = mesa_map[sel_mesa]
                st.dataframe(
                    pd.DataFrame(
                        [{
                            "Mesa": row["Mesa"],
                            "Preconteo": row["Preconteo"],
                            "Escrutinio": row["Escrutinio"],
                            "Diferencia": row["Diferencia"],
                        }]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.success("No hay diferencias por mesa para German en los datos actuales del escrutinio.")

        # Candidate/party differences
        all_keys = set(cand_pre) | set(cand_esc)
        rows_cand = []
        party_map = {}

        for key in sorted(all_keys):
            p = cand_pre.get(key, 0)
            e = cand_esc.get(key, 0)
            if p == 0 and e == 0:
                continue
            party, _cand = key.split("_", 1)
            nombre = nombre_candidato(key, candidatos_meta)
            partido_nombre = nombre_partido(party, partidos)
            rows_cand.append({
                "Partido": f"{partido_nombre} ({party})",
                "Candidato": nombre,
                                "Preconteo": p,
                "Escrutinio": e,
                "Diferencia": e - p,
            })
            agg = party_map.get(party, {"Preconteo": 0, "Escrutinio": 0})
            agg["Preconteo"] += p
            agg["Escrutinio"] += e
            party_map[party] = agg

        st.markdown("**Diferencias por candidato (lista + candidato)**")
        if rows_cand:
            df_cand = pd.DataFrame(rows_cand).sort_values("Diferencia", key=abs, ascending=False)
            st.dataframe(df_cand, use_container_width=True, hide_index=True)
        else:
            st.info("No hay diferencias por candidato.")

        st.markdown("**RANKING CREEMOS — PRECONTEO VS ESCRUTINIO**")
        creemos_key = "01067"
        rows_creemos = []
        for key in sorted(all_keys):
            if not key.startswith(creemos_key + "_"):
                continue
            p = cand_pre.get(key, 0)
            e = cand_esc.get(key, 0)
            if p == 0 and e == 0:
                continue
            nombre = nombre_candidato(key, candidatos_meta)
            rows_creemos.append({
                "Candidato": nombre,
                "Preconteo": p,
                "Escrutinio": e,
                "Diff": e - p,
            })

        if rows_creemos:
            df_creemos = pd.DataFrame(rows_creemos)
            st.markdown("Preconteo (Top)")
            st.dataframe(df_creemos.sort_values("Preconteo", ascending=False), use_container_width=True, hide_index=True)
            st.markdown("Escrutinio (Top)")
            st.dataframe(df_creemos.sort_values("Escrutinio", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros de CREEMOS en las mesas con escrutinio.")

        st.markdown("**Diferencias por partido (lista + candidatos)**")
        if party_map:
            rows_party = []
            for party, vals in party_map.items():
                rows_party.append({
                    "Partido": f"{nombre_partido(party, partidos)} ({party})",
                    "Preconteo": vals["Preconteo"],
                    "Escrutinio": vals["Escrutinio"],
                    "Diferencia": vals["Escrutinio"] - vals["Preconteo"],
                })
            df_party = pd.DataFrame(rows_party).sort_values("Diferencia", key=abs, ascending=False)
            st.dataframe(df_party, use_container_width=True, hide_index=True)
        else:
            st.info("No hay diferencias por partido.")

        st.download_button(
            "Descargar diferencias por mesa (German) (CSV)",
            pd.DataFrame(rows_german).to_csv(index=False).encode("utf-8"),
            "diferencias_mesas_german_escrutinio_vs_preconteo.csv",
            "text/csv",
        )
        st.download_button(
            "Descargar diferencias por candidato (CSV)",
            pd.DataFrame(rows_cand).to_csv(index=False).encode("utf-8"),
            "diferencias_candidatos_escrutinio_vs_preconteo.csv",
            "text/csv",
        )
        st.download_button(
            "Descargar diferencias por partido (CSV)",
            pd.DataFrame([{**{"Partido": nombre_partido(p, partidos)}, **v, "Diferencia": v["Escrutinio"] - v["Preconteo"]} for p, v in party_map.items()]).to_csv(index=False).encode("utf-8"),
            "diferencias_partidos_escrutinio_vs_preconteo.csv",
            "text/csv",
        )

    # ═══════════════════════════════════════
    # §5 — CURULES CAMARA ANTIOQUIA (ESCRUTINIO)
    # ═══════════════════════════════════════
    section("CURULES CAMARA ANTIOQUIA — ESCRUTINIO", "gavel")
    st.caption(
        "Base: Camara territorial Antioquia (circunscripcion 1, depto 01). "
        "Votos validos por partido = lista + candidatos."
    )

    votos_partido_esc = _votos_partido_camara_antioquia_escrutinio(mmv_esc)
    if not votos_partido_esc:
        st.info("No hay votos validos de Camara Antioquia en escrutinio para calcular curules.")
    else:
        total_validos_esc = sum(votos_partido_esc.values())
        cociente_electoral = (
            total_validos_esc / CURULES_CAMARA_ANTIOQUIA if CURULES_CAMARA_ANTIOQUIA > 0 else 0
        )
        umbral = cociente_electoral * UMBRAL_FACTOR

        partidos_habilitados = {cod: v for cod, v in votos_partido_esc.items() if v >= umbral}
        partidos_excluidos = {cod: v for cod, v in votos_partido_esc.items() if v < umbral}

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
                fmt(total_validos_esc),
                "Camara Antioquia (escrutinio)",
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

        section("CORTE DE ULTIMAS CURULES (ESCRUTINIO)", "rule")
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

        # Siguientes 3 partidos despues de la curul 17
        if curul_17:
            target_cociente = curul_17["cociente"]
            siguientes = cocientes_all[CURULES_CAMARA_ANTIOQUIA:CURULES_CAMARA_ANTIOQUIA + 3]
            if siguientes:
                rows_next = []
                for item in siguientes:
                    party = item["partido"]
                    divisor = item["divisor"]
                    votos_partido = votos_partido_esc.get(party, 0)
                    # Votos necesarios para alcanzar el cociente de la curul 17 con su divisor actual
                    needed = max(0, math.ceil(target_cociente * divisor) - votos_partido)
                    rows_next.append({
                        "Partido": nombre_partido(party, partidos),
                        "Codigo": party,
                        "Divisor": divisor,
                        "Cociente": round(item["cociente"], 6),
                        "Votos partido": votos_partido,
                        "Votos faltantes para curul 17": needed,
                    })

                st.markdown("**SIGUIENTES 3 PARTIDOS DESPUES DE CURUL 17**")
                st.dataframe(pd.DataFrame(rows_next), use_container_width=True, hide_index=True)
            else:
                st.info("No hay suficientes cocientes para mostrar los siguientes 3 partidos.")
        else:
            st.info("No hay curul 17 asignada; no se puede calcular el ranking siguiente.")

        section("RESULTADO DE ASIGNACION (ESCRUTINIO)", "how_to_vote")
        if not partidos_habilitados:
            st.warning("Ningun partido supera el umbral; no se pueden asignar curules.")
        else:
            rows_res = []
            for cod, votos in partidos_habilitados.items():
                rows_res.append({
                    "Codigo": cod,
                    "Partido": nombre_partido(cod, partidos),
                    "Votos validos": votos,
                    "% votos": pct(votos, total_validos_esc),
                    "Curules": curules.get(cod, 0),
                    "% curules": pct(curules.get(cod, 0), CURULES_CAMARA_ANTIOQUIA),
                })
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

        section("PARTIDOS EXCLUIDOS POR UMBRAL (ESCRUTINIO)", "block")
        if not partidos_excluidos:
            st.success("No hay partidos excluidos por umbral.")
        else:
            rows_exc = [
                {
                    "Codigo": cod,
                    "Partido": nombre_partido(cod, partidos),
                    "Votos validos": votos,
                    "% votos": pct(votos, total_validos_esc),
                }
                for cod, votos in sorted(partidos_excluidos.items(), key=lambda x: x[1], reverse=True)
            ]
            st.dataframe(pd.DataFrame(rows_exc), use_container_width=True, height=300)

        with st.expander("Ver detalle de cocientes (ordenados)"):
            rows_coc = []
            for idx, item in enumerate(cocientes_all, start=1):
                rows_coc.append({
                    "Orden": idx,
                    "Codigo": item["partido"],
                    "Partido": nombre_partido(item["partido"], partidos),
                    "Votos partido": item["votos_partido"],
                    "Divisor": item["divisor"],
                    "Cociente": round(item["cociente"], 6),
                    "Entra curul": "SI" if idx <= CURULES_CAMARA_ANTIOQUIA else "NO",
                })
            st.dataframe(pd.DataFrame(rows_coc), use_container_width=True, height=420)

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
