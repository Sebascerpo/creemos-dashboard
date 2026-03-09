"""
pages/pg_cruce_votos.py
────────────────────────
Página: Cruce Testigos vs Oficial
Cruza votos reportados por testigos (RESULTADOS_MMV.txt) con
los votos oficiales del boletín MMV.

5 secciones:
  §1 Cobertura
  §2 Discrepancias
  §3 Análisis de patrones
  §4 Impacto acumulado (umbral + D'Hondt)
  §5 Lista de acción jurídica
"""

from __future__ import annotations

import math
from collections import defaultdict

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from core.parser import (
    COD_ANTIOQUIA,
    cargar_mesa_candidato,
    cargar_mesa_partido_circ,
    cargar_mesa_totales_circ,
)
from core.parser_testigos import parsear_testigos
from pages.shared import (
    DATA_DIR,
    CANDIDATOS_PRINCIPALES,
    fmt,
    pct,
    kpi,
    section,
    plotly_defaults,
    nombre_partido,
    nombre_candidato,
    nombre_depto,
    nombre_municipio_str,
    formatear_mesa_completa,
    resolver_mmv_path,
)

# ── Claves candidatos y Partidos ──
PARTIDOS_OBJETIVO = {
    "01067": {"nombre": "CREEMOS", "color": "#2563EB"},
    "00002": {"nombre": "CONSERVADOR", "color": "#2196F3"},
    "03055": {"nombre": "PACTO HISTORICO", "color": "#9C27B0"},
    "00011": {"nombre": "CENTRO DEMOCRATICO", "color": "#DC2626"},
}
CURULES_CAMARA = 17  # Antioquia
UMBRAL_PCT = 50.0 / CURULES_CAMARA  # Cociente electoral simplificado o cifra umbral
CIRC_CAMARA = "1"


def _votos_partido_camara(mmv: dict) -> dict[str, int]:
    """Votos válidos por partido Cámara Antioquia."""
    out: dict[str, int] = {}
    pc = mmv.get("partidos_por_circ", {}).get(CIRC_CAMARA, {})
    for cod, d in pc.items():
        v = int(d.get("por_depto_validos_total", {}).get(COD_ANTIOQUIA, 0) or 0)
        if v > 0:
            out[cod] = v
    return out


def _reparto_dhondt(
    votos_partido: dict[str, int], total_curules: int
) -> dict[str, int]:
    """D'Hondt simplificado, retorna curules por partido."""
    cocientes = []
    for cod, votos in votos_partido.items():
        for div in range(1, total_curules + 1):
            cocientes.append((votos / div, votos, cod))
    cocientes.sort(key=lambda x: (-x[0], -x[1], x[2]))
    curules = {cod: 0 for cod in votos_partido}
    for _, _, cod in cocientes[:total_curules]:
        curules[cod] += 1
    return curules


def _resolver_circ_partido(cod_partido: str, mmv: dict) -> str:
    """
    Determina la circunscripción de un partido buscando en los candidatos
    que pertenecen a ese partido.
    """
    for cand_key, cand_data in mmv.get("candidatos", {}).items():
        if cand_data.get("cod_partido") == cod_partido:
            return cand_data.get("circunscripcion", "0")
    # Fallback: buscar en partidos_por_circ
    for circ in ["0", "1"]:
        if cod_partido in mmv.get("partidos_por_circ", {}).get(circ, {}):
            return circ
    return "0"


def _build_cruce(
    testigos: dict,
    mmv: dict,
    mmv_path_str: str,
    candidatos_meta: dict,
) -> list[dict]:
    """
    Construye la lista de cruce mesa-por-mesa, candidato-por-candidato.
    Solo cruza mesas que existan en ambas fuentes.
    Para votos de lista (candidato 000), carga datos oficiales desde
    cargar_mesa_partido_circ en vez de cargar_mesa_candidato.
    """
    mesas_testigo = testigos["por_mesa_candidato"]

    # Recolectar todos los cand_keys que necesitamos del testigo
    all_cands = set()
    for mesa_cands in mesas_testigo.values():
        all_cands.update(mesa_cands.keys())

    # Separar lista (000) de candidatos individuales
    lista_keys = {k for k in all_cands if k.endswith("_000")}
    cand_keys = all_cands - lista_keys

    # Cargar mesas por candidato individual
    cand_mesa_cache: dict[str, dict[str, int]] = {}
    for cand_key in cand_keys:
        cand_mesa_cache[cand_key] = cargar_mesa_candidato(mmv_path_str, cand_key)

    # Cargar mesas por partido (para votos de lista 000)
    # La key de lista es "PARTIDO_000", el partido es PARTIDO
    for lista_key in lista_keys:
        cod_partido = lista_key.split("_")[0]
        circ = _resolver_circ_partido(cod_partido, mmv)
        mesa_data = cargar_mesa_partido_circ(mmv_path_str, circ, cod_partido)
        # mesa_data contiene votos_lista + votos_candidatos sumados
        # Necesitamos solo los votos de lista: restar los de candidatos
        # Pero el parquet de partido_circ_mesa tiene el total (lista + candidatos)
        # Alternativa: usar el dato directo como referencia del total
        # El testigo reporta votos de lista por separado, así que
        # necesitamos extraer solo votos de lista del oficial.
        # Los votos de lista oficial por mesa NO están separados en el cache
        # de partido, están sumados. Entonces cargamos desde el parser
        # que sí los guarda separados como parte de pcirc_mesa.
        # En realidad, en el parser, pcirc_mesa incluye AMBOS lista y candidatos.
        # Para obtener solo lista por mesa, debemos restar los candidatos.
        # Mejor enfoque: cargar todos los candidatos de ese partido y restar.
        cands_del_partido = [ck for ck in cand_keys if ck.split("_")[0] == cod_partido]
        votos_cands_por_mesa: dict[str, int] = defaultdict(int)
        for ck in cands_del_partido:
            for mesa, v in cand_mesa_cache.get(ck, {}).items():
                votos_cands_por_mesa[mesa] += v
        # lista = total_partido - candidatos
        lista_oficial: dict[str, int] = {}
        for mesa, total in mesa_data.items():
            lista_oficial[mesa] = total - votos_cands_por_mesa.get(mesa, 0)
        cand_mesa_cache[lista_key] = lista_oficial

    rows = []
    for mesa_key, cands_testigo in mesas_testigo.items():
        parts = mesa_key.split("_")
        depto = parts[0]
        muni_key = f"{parts[0]}_{parts[1]}"
        puesto_key = f"{parts[0]}_{parts[1]}_{parts[2]}_{parts[3]}"
        num_mesa = parts[4] if len(parts) > 4 else ""

        for cand_key, votos_t in cands_testigo.items():
            votos_o = cand_mesa_cache.get(cand_key, {}).get(mesa_key, 0)
            diff = votos_t - votos_o

            cod_partido = cand_key.split("_")[0] if "_" in cand_key else ""
            cod_candidato = cand_key.split("_")[1] if "_" in cand_key else ""

            # Determinar circunscripción/corporación
            if cod_candidato == "000":
                # Es voto de lista: inferir circ del partido
                circ_mmv = _resolver_circ_partido(cod_partido, mmv)
            else:
                meta = candidatos_meta.get(cand_key, {})
                cand_mmv = mmv["candidatos"].get(cand_key, {})
                circ_mmv = cand_mmv.get(
                    "circunscripcion", meta.get("circunscripcion", "")
                )

            es_senado = circ_mmv == "0"

            rows.append(
                {
                    "mesa_key": mesa_key,
                    "cand_key": cand_key,
                    "cod_depto": depto,
                    "muni_key": muni_key,
                    "puesto_key": puesto_key,
                    "num_mesa": num_mesa,
                    "cod_partido": cod_partido,
                    "cod_candidato": cod_candidato,
                    "corporacion": "Senado" if es_senado else "Camara",
                    "votos_testigo": votos_t,
                    "votos_oficial": votos_o,
                    "diferencia": diff,
                }
            )

    return rows


def render(datos: dict):
    mmv = datos["mmv"]
    partidos = datos["partidos"]
    candidatos_meta = datos["candidatos"]
    divipol = datos["divipol"]

    if not mmv:
        st.warning("No hay datos MMV cargados.")
        return

    section("CRUCE TESTIGOS VS OFICIAL", "sync_alt")
    st.caption(
        "Cruza los votos reportados por testigos del partido (E-14 físico) "
        "con los votos del boletín oficial (MMV). "
        "La discrepancia = votos testigo − votos oficial."
    )

    testigos = parsear_testigos(str(DATA_DIR))
    if testigos is None:
        st.warning(
            "No se encontró el archivo `data/RESULTADOS_MMV.txt`. "
            "Sube el archivo de resultados de testigos para activar esta página."
        )
        return

    if not testigos["mesas"]:
        st.info("El archivo de testigos está vacío o no contiene datos válidos.")
        return

    mmv_path_str = str(resolver_mmv_path())

    # ════════════════════════════════════════════
    # §1 — COBERTURA
    # ════════════════════════════════════════════
    section("§1 — COBERTURA", "fact_check")

    def _es_mesa_regular(mesa_key: str) -> bool:
        """Excluir mesas especiales (zona 99)."""
        parts = mesa_key.split("_")
        if len(parts) >= 3:
            return parts[2] != "99"
        return True

    mesas_testigo = {m for m in testigos["mesas"] if _es_mesa_regular(m)}
    # Solo contar mesas de Antioquia (monitoreo), sin mesas especiales
    mesas_oficial = set()
    for muni_key, muni_data in mmv["municipios"].items():
        if muni_key.startswith(COD_ANTIOQUIA + "_"):
            mesas_oficial.update(
                m for m in muni_data.get("mesas", set()) if _es_mesa_regular(m)
            )

    mesas_ambas = mesas_testigo & mesas_oficial
    mesas_solo_testigo = mesas_testigo - mesas_oficial
    n_test = len(mesas_testigo)
    n_ofic = len(mesas_oficial)
    n_ambas = len(mesas_ambas)
    # Universo total de mesas regulares Antioquia
    # (DIVIPOL: puestos sin contenido extra al final = regulares)
    n_universo = 0
    divipol_path = DATA_DIR / "DIVIPOL.txt"
    if divipol_path.exists():
        with open(divipol_path, encoding="latin-1") as _f:
            for _line in _f:
                _line = _line.rstrip("\n")
                if len(_line) < 114:
                    continue
                if _line[0:2] != COD_ANTIOQUIA:
                    continue
                # Puestos especiales tienen texto CIRCUNSCRIPCIÓN después de pos. 114
                if _line[114:].strip():
                    continue
                _nm = _line[108:114].strip()
                n_universo += int(_nm) if _nm.isdigit() else 0

    cobertura_pct = (n_ambas / n_universo * 100) if n_universo > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi(
            "Mesas testigo",
            fmt(n_test),
            f"{testigos['lineas']} lineas procesadas",
            "#2563EB",
        )
    with c2:
        kpi(
            "Total mesas Antioquia",
            fmt(n_universo),
            "segun DIVIPOL · sin mesas especiales",
            "#DC2626",
        )
    with c3:
        kpi("Mesas cruzables", fmt(n_ambas), "presentes en ambas fuentes", "#059669")
    with c4:
        kpi(
            "Cobertura",
            f"{cobertura_pct:.1f}%",
            f"{fmt(n_ambas)} de {fmt(n_universo)} mesas totales",
            "#D97706",
        )

    if cobertura_pct < 10:
        st.error(
            f"Cobertura muy baja ({cobertura_pct:.1f}%). "
            "Los resultados del cruce no son representativos."
        )
    elif cobertura_pct < 50:
        st.warning(
            f"Cobertura parcial ({cobertura_pct:.1f}%). "
            "Interpretar resultados con precaución."
        )
    else:
        st.success(
            f"Cobertura alta ({cobertura_pct:.1f}%). El cruce es representativo."
        )

    if mesas_solo_testigo:
        with st.expander(
            f"Mesas solo en testigos ({len(mesas_solo_testigo)}) — sin dato oficial"
        ):
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Mesa": formatear_mesa_completa(m, divipol)}
                        for m in sorted(mesas_solo_testigo)
                    ]
                ),
                use_container_width=True,
                height=200,
            )

    # Cobertura por municipio
    muni_test = defaultdict(int)
    muni_ofic = defaultdict(int)
    muni_ambas_count = defaultdict(int)
    for m in mesas_testigo:
        parts = m.split("_")
        mk = f"{parts[0]}_{parts[1]}"
        muni_test[mk] += 1
    for m in mesas_oficial:
        parts = m.split("_")
        mk = f"{parts[0]}_{parts[1]}"
        muni_ofic[mk] += 1
    for m in mesas_ambas:
        parts = m.split("_")
        mk = f"{parts[0]}_{parts[1]}"
        muni_ambas_count[mk] += 1

    all_munis = sorted(set(muni_test.keys()) | set(muni_ofic.keys()))
    cob_rows = []
    for mk in all_munis:
        t = muni_test.get(mk, 0)
        o = muni_ofic.get(mk, 0)
        a = muni_ambas_count.get(mk, 0)
        if t > 0:  # solo mostrar municipios donde hay testigo
            cob_rows.append(
                {
                    "Municipio": nombre_municipio_str(mk, divipol),
                    "Clave": mk,
                    "Mesas testigo": t,
                    "Mesas oficial": o,
                    "Cruzables": a,
                    "% cobertura": pct(a, o),
                }
            )
    if cob_rows:
        with st.expander("Cobertura por municipio"):
            st.dataframe(
                pd.DataFrame(cob_rows).sort_values("Cruzables", ascending=False),
                use_container_width=True,
                height=300,
            )

    if n_ambas == 0:
        st.warning("No hay mesas que existan en ambas fuentes. No se puede cruzar.")
        return

    # ════════════════════════════════════════════
    # §2 — DISCREPANCIAS
    # ════════════════════════════════════════════
    section("§2 — DISCREPANCIAS", "find_in_page")

    cruce_rows = _build_cruce(testigos, mmv, mmv_path_str, candidatos_meta)
    if not cruce_rows:
        st.info("No se encontraron registros cruzables.")
        return

    df_cruce = pd.DataFrame(cruce_rows)
    # Filtrar solo mesas cruzables
    df_cruce = df_cruce[df_cruce["mesa_key"].isin(mesas_ambas)]

    if df_cruce.empty:
        st.info("No hay datos cruzables entre testigos y oficial.")
        return

    coincidencias = df_cruce[df_cruce["diferencia"] == 0]
    disc_pos = df_cruce[df_cruce["diferencia"] > 0]
    disc_neg = df_cruce[df_cruce["diferencia"] < 0]

    n_total_reg = len(df_cruce)
    n_coinc = len(coincidencias)
    n_pos = len(disc_pos)
    n_neg = len(disc_neg)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi("Registros cruzados", fmt(n_total_reg), f"candidato×mesa", "#2563EB")
    with k2:
        kpi(
            "Coincidencias",
            fmt(n_coinc),
            f"{pct(n_coinc, n_total_reg)} del total",
            "#059669",
        )
    with k3:
        kpi(
            "Disc. positivas",
            fmt(n_pos),
            "testigo > oficial (posibles votos sustraídos)",
            "#DC2626",
        )
    with k4:
        kpi(
            "Disc. negativas",
            fmt(n_neg),
            "testigo < oficial (posibles votos adicionados)",
            "#D97706",
        )

    # Filtrar solo corporación Cámara (Antioquia)
    df_cruce = df_cruce[df_cruce["corporacion"] == "Camara"]
    df_cruce = df_cruce[df_cruce["cod_partido"].isin(PARTIDOS_OBJETIVO.keys())]

    if df_cruce.empty:
        st.info("No hay datos cruzables para los 4 partidos en Cámara.")
        return

    def _render_discrepancias_tab(df_tab: pd.DataFrame, color: str):
        if df_tab.empty:
            st.info("Sin datos para esta corporación.")
            return

        # Resumen por candidato
        resumen = (
            df_tab.groupby("cand_key")
            .agg(
                votos_testigo=("votos_testigo", "sum"),
                votos_oficial=("votos_oficial", "sum"),
                diferencia=("diferencia", "sum"),
                mesas=("mesa_key", "nunique"),
            )
            .reset_index()
            .sort_values("diferencia", key=abs, ascending=False)
        )
        resumen["Candidato"] = resumen["cand_key"].apply(
            lambda k: nombre_candidato(k, candidatos_meta)
        )
        resumen["Partido"] = resumen["cand_key"].apply(
            lambda k: nombre_partido(k.split("_")[0], partidos)[:24]
        )

        st.markdown("**Resumen por candidato / lista**")
        st.dataframe(
            resumen[
                [
                    "Candidato",
                    "Partido",
                    "votos_testigo",
                    "votos_oficial",
                    "diferencia",
                    "mesas",
                ]
            ].rename(
                columns={
                    "votos_testigo": "Votos testigo",
                    "votos_oficial": "Votos oficial",
                    "diferencia": "Diferencia",
                    "mesas": "Mesas",
                }
            ),
            use_container_width=True,
            height=300,
        )

        disc_pos_tab = df_tab[df_tab["diferencia"] > 0].sort_values(
            "diferencia", ascending=False
        )
        disc_neg_tab = df_tab[df_tab["diferencia"] < 0].sort_values("diferencia")

        def _fmt_disc_table(df_d):
            return pd.DataFrame(
                [
                    {
                        "Mesa": formatear_mesa_completa(r["mesa_key"], divipol),
                        "Municipio": nombre_municipio_str(r["muni_key"], divipol),
                        "Candidato": nombre_candidato(r["cand_key"], candidatos_meta),
                        "V. Testigo": r["votos_testigo"],
                        "V. Oficial": r["votos_oficial"],
                        "Diferencia": r["diferencia"],
                    }
                    for _, r in df_d.iterrows()
                ]
            )

        col_p, col_n = st.columns(2)
        with col_p:
            st.markdown(f"**Disc. positivas** ({len(disc_pos_tab)} registros)")
            if not disc_pos_tab.empty:
                st.dataframe(
                    _fmt_disc_table(disc_pos_tab), use_container_width=True, height=280
                )
            else:
                st.success("Sin discrepancias positivas")
        with col_n:
            st.markdown(f"**Disc. negativas** ({len(disc_neg_tab)} registros)")
            if not disc_neg_tab.empty:
                st.dataframe(
                    _fmt_disc_table(disc_neg_tab), use_container_width=True, height=280
                )
            else:
                st.success("Sin discrepancias negativas")

    # Render único para Cámara
    _render_discrepancias_tab(df_cruce, "#2563EB")

    # ════════════════════════════════════════════
    # §3 — ANÁLISIS DE PATRONES
    # ════════════════════════════════════════════
    section("§3 — ANÁLISIS DE PATRONES", "analytics")

    df_disc = df_cruce[df_cruce["diferencia"] != 0].copy()

    if df_disc.empty:
        st.success("No hay discrepancias — todos los registros coinciden.")
    else:
        col_hist, col_sesgo = st.columns(2)

        with col_hist:
            st.markdown("**Top discrepancias por magnitud**")
            # Mostrar las top 20 discrepancias más grandes como barras
            df_top_disc = df_disc.copy()
            df_top_disc["abs_diff"] = df_top_disc["diferencia"].abs()
            df_top_disc = df_top_disc.nlargest(20, "abs_diff")
            df_top_disc["label"] = df_top_disc.apply(
                lambda r: f"{r['mesa_key'][:15]}|{r['cand_key']}", axis=1
            )
            df_top_disc["color"] = df_top_disc["diferencia"].apply(
                lambda d: "Positiva (+)" if d > 0 else "Negativa (-)"
            )
            fig_hist = px.bar(
                df_top_disc,
                x="diferencia",
                y="label",
                orientation="h",
                color="color",
                color_discrete_map={
                    "Positiva (+)": "#DC2626",
                    "Negativa (-)": "#D97706",
                },
                labels={"diferencia": "Diferencia (testigo - oficial)", "label": ""},
            )
            fig_hist.update_layout(
                height=350, showlegend=True, yaxis={"categoryorder": "total ascending"}
            )
            st.plotly_chart(plotly_defaults(fig_hist), use_container_width=True)

            mean_diff = df_disc["diferencia"].mean()
            median_diff = df_disc["diferencia"].median()
            sum_diff = df_disc["diferencia"].sum()
            st.caption(
                f"Total registros con discrepancia: {len(df_disc)} | "
                f"Suma: {sum_diff:+,} | Media: {mean_diff:+.2f} | Mediana: {median_diff:+.0f}"
            )

        with col_sesgo:
            st.markdown("**Sesgo direccional**")
            n_pos_d = len(df_disc[df_disc["diferencia"] > 0])
            n_neg_d = len(df_disc[df_disc["diferencia"] < 0])
            total_d = n_pos_d + n_neg_d
            pct_pos = (n_pos_d / total_d * 100) if total_d > 0 else 0
            pct_neg = (n_neg_d / total_d * 100) if total_d > 0 else 0

            fig_sesgo = go.Figure(
                go.Bar(
                    x=[n_pos_d, n_neg_d],
                    y=["Positivas (+)", "Negativas (−)"],
                    orientation="h",
                    marker_color=["#DC2626", "#D97706"],
                    text=[f"{n_pos_d} ({pct_pos:.0f}%)", f"{n_neg_d} ({pct_neg:.0f}%)"],
                    textposition="auto",
                )
            )
            fig_sesgo.update_layout(height=200, showlegend=False)
            st.plotly_chart(plotly_defaults(fig_sesgo), use_container_width=True)

            if pct_pos > 70:
                st.error(
                    f"SESGO SISTEMATICO: {pct_pos:.0f}% de las discrepancias son positivas. "
                    "Patrón consistente de votos sustraídos."
                )
            elif pct_neg > 70:
                st.error(
                    f"SESGO SISTEMATICO: {pct_neg:.0f}% de las discrepancias son negativas. "
                    "Patrón consistente de votos adicionados."
                )
            else:
                st.info(
                    f"Distribución mixta ({pct_pos:.0f}% positivas / {pct_neg:.0f}% negativas). "
                    "No se detecta sesgo sistemático claro."
                )

        # Concentración geográfica
        st.markdown("**Concentración geográfica de discrepancias**")
        geo_disc = (
            df_disc.groupby("muni_key")
            .agg(
                discrepancias=("diferencia", "count"),
                mesas_con_disc=("mesa_key", "nunique"),
                diff_acumulada=("diferencia", "sum"),
                diff_media=("diferencia", "mean"),
            )
            .reset_index()
            .sort_values("diff_acumulada", key=abs, ascending=False)
        )
        # Agregar total de mesas del testigo en ese municipio
        geo_disc["Municipio"] = geo_disc["muni_key"].apply(
            lambda mk: nombre_municipio_str(mk, divipol)
        )
        total_mesas_muni = {}
        for m in mesas_ambas:
            mk = f"{m.split('_')[0]}_{m.split('_')[1]}"
            total_mesas_muni[mk] = total_mesas_muni.get(mk, 0) + 1
        geo_disc["mesas_cruzadas"] = (
            geo_disc["muni_key"].map(total_mesas_muni).fillna(0).astype(int)
        )
        geo_disc["% mesas con disc"] = geo_disc.apply(
            lambda r: pct(r["mesas_con_disc"], r["mesas_cruzadas"]), axis=1
        )

        st.dataframe(
            geo_disc[
                [
                    "Municipio",
                    "muni_key",
                    "mesas_cruzadas",
                    "mesas_con_disc",
                    "% mesas con disc",
                    "discrepancias",
                    "diff_acumulada",
                    "diff_media",
                ]
            ].rename(
                columns={
                    "muni_key": "Clave",
                    "mesas_cruzadas": "Mesas cruzadas",
                    "mesas_con_disc": "Mesas c/disc",
                    "discrepancias": "Registros",
                    "diff_acumulada": "Diff acumulada",
                    "diff_media": "Diff media",
                }
            ),
            use_container_width=True,
            height=300,
        )

        # Consistencia por puesto
        st.markdown("**Consistencia por puesto de votación**")
        puesto_disc = (
            df_disc.groupby("puesto_key")
            .agg(
                mesas=("mesa_key", "nunique"),
                sum_diff=("diferencia", "sum"),
                positivas=("diferencia", lambda x: (x > 0).sum()),
                negativas=("diferencia", lambda x: (x < 0).sum()),
            )
            .reset_index()
        )
        puesto_disc["todas_misma_dir"] = puesto_disc.apply(
            lambda r: (r["positivas"] > 0 and r["negativas"] == 0)
            or (r["negativas"] > 0 and r["positivas"] == 0),
            axis=1,
        )
        alertas_puesto = puesto_disc[
            (puesto_disc["todas_misma_dir"]) & (puesto_disc["mesas"] > 1)
        ]
        if not alertas_puesto.empty:
            st.error(
                f"{len(alertas_puesto)} puestos con TODAS las mesas con discrepancia "
                "en la misma dirección:"
            )
            alertas_puesto["Puesto"] = alertas_puesto["puesto_key"]
            alertas_puesto["Dirección"] = alertas_puesto["sum_diff"].apply(
                lambda x: "Positiva (+)" if x > 0 else "Negativa (−)"
            )
            st.dataframe(
                alertas_puesto[["Puesto", "mesas", "sum_diff", "Dirección"]].rename(
                    columns={"mesas": "Mesas", "sum_diff": "Diff total"}
                ),
                use_container_width=True,
                height=200,
            )
        else:
            st.info(
                "No se detectan puestos con discrepancia consistente en todas sus mesas."
            )

    # ════════════════════════════════════════════
    # §4 — IMPACTO ACUMULADO : MULTI-PARTIDO
    # ════════════════════════════════════════════
    section("§4 — IMPACTO ACUMULADO", "trending_up")

    st.markdown("**Comparación Oficial vs Testigo por Partido (Cámara Antioquia)**")

    cols_imp = st.columns(4)
    votos_oficial_cam = _votos_partido_camara(mmv)

    for idx, (cod_p, info) in enumerate(PARTIDOS_OBJETIVO.items()):
        col = cols_imp[idx]
        df_cand = df_cruce[df_cruce["cod_partido"] == cod_p]
        v_diff = df_cand["diferencia"].sum() if not df_cand.empty else 0
        v_ofic = votos_oficial_cam.get(cod_p, 0)
        v_test = v_ofic + v_diff

        with col:
            st.markdown(f"**{info['nombre']}**", unsafe_allow_html=True)
            kpi(
                f"Oficial",
                fmt(v_ofic),
                f"Suma válida MMV",
                "#6B7280",
            )
            kpi(
                f"Testigo",
                fmt(v_test),
                f"Dif total: {v_diff:+,.0f}",
                info["color"],
            )
            if v_diff > 0:
                st.error(f"Faltan {fmt(v_diff)} votos")
            elif v_diff < 0:
                st.warning(f"Exceden {fmt(abs(v_diff))} votos")
            else:
                st.success("Correcto")

    # (Curules projection eliminated)

    # ════════════════════════════════════════════
    # §5 — LISTA DE ACCIÓN JURÍDICA
    # ════════════════════════════════════════════
    section("§5 — LISTA DE ACCION JURIDICA", "gavel")

    # Solo discrepancias de los partidos objetivo
    df_disc_full = df_cruce[df_cruce["diferencia"] != 0].copy()

    st.caption("Muestra solo discrepancias de los 4 partidos clave analizados.")

    if df_disc_full.empty:
        st.success("No hay discrepancias — no se requiere acción jurídica.")
        return

    # Prioridad
    df_disc_full["abs_diff"] = df_disc_full["diferencia"].abs()

    # Determinar si el puesto tiene consistencia (todas misma dirección)
    puesto_consist = {}
    for pk, group in df_disc_full.groupby("puesto_key"):
        all_pos = (group["diferencia"] > 0).all()
        all_neg = (group["diferencia"] < 0).all()
        puesto_consist[pk] = all_pos or all_neg
    df_disc_full["puesto_consistente"] = df_disc_full["puesto_key"].map(puesto_consist)

    def _prioridad(row):
        score = 0
        score += min(row["abs_diff"] * 2, 20)  # magnitud
        if row["puesto_consistente"]:
            score += 10  # puesto consistente
        if row["diferencia"] > 0:
            score += 5  # positiva (votos sustraídos)
        if score >= 20:
            return "Alta"
        elif score >= 10:
            return "Media"
        return "Baja"

    df_disc_full["Prioridad"] = df_disc_full.apply(_prioridad, axis=1)
    df_disc_full = df_disc_full.sort_values(
        ["Prioridad", "abs_diff"],
        key=lambda x: (
            x.map({"Alta": 0, "Media": 1, "Baja": 2}) if x.name == "Prioridad" else -x
        ),
        ascending=True,
    )

    # Filtros
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        filt_corp = st.selectbox(
            "Corporación", ["Todas", "Senado", "Camara"], key="jur_corp"
        )
    with f2:
        filt_dir = st.selectbox(
            "Dirección", ["Todas", "Positiva (+)", "Negativa (−)"], key="jur_dir"
        )
    with f3:
        munis_disponibles = ["Todos"] + sorted(
            df_disc_full["muni_key"].unique().tolist()
        )
        munis_labels = ["Todos"] + [
            nombre_municipio_str(mk, divipol) for mk in munis_disponibles[1:]
        ]
        muni_map = dict(zip(munis_labels, munis_disponibles))
        filt_muni_label = st.selectbox("Municipio", munis_labels, key="jur_muni")
        filt_muni = muni_map[filt_muni_label]
    with f4:
        filt_min_diff = st.number_input(
            "Diferencia mínima", min_value=0, value=0, key="jur_min"
        )

    df_filtrado = df_disc_full.copy()
    if filt_corp != "Todas":
        df_filtrado = df_filtrado[df_filtrado["corporacion"] == filt_corp]
    if filt_dir == "Positiva (+)":
        df_filtrado = df_filtrado[df_filtrado["diferencia"] > 0]
    elif filt_dir == "Negativa (−)":
        df_filtrado = df_filtrado[df_filtrado["diferencia"] < 0]
    if filt_muni != "Todos":
        df_filtrado = df_filtrado[df_filtrado["muni_key"] == filt_muni]
    if filt_min_diff > 0:
        df_filtrado = df_filtrado[df_filtrado["abs_diff"] >= filt_min_diff]

    # Tabla final
    df_display = pd.DataFrame(
        [
            {
                "Prioridad": r["Prioridad"],
                "Mesa": formatear_mesa_completa(r["mesa_key"], divipol),
                "Municipio": nombre_municipio_str(r["muni_key"], divipol),
                "Puesto": r["puesto_key"],
                "Corporación": r["corporacion"],
                "Candidato": nombre_candidato(r["cand_key"], candidatos_meta),
                "Partido": nombre_partido(r["cod_partido"], partidos)[:20],
                "V. Testigo": r["votos_testigo"],
                "V. Oficial": r["votos_oficial"],
                "Diferencia": r["diferencia"],
            }
            for _, r in df_filtrado.iterrows()
        ]
    )

    kpi(
        "Registros filtrados",
        fmt(len(df_display)),
        f"de {fmt(len(df_disc_full))} con discrepancia",
        "#2563EB",
    )

    if not df_display.empty:
        st.dataframe(df_display, use_container_width=True, height=400)

        # Export CSV
        csv_data = df_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Descargar lista jurídica CSV",
            csv_data,
            "lista_accion_juridica.csv",
            "text/csv",
            use_container_width=True,
            icon=":material/download:",
        )

        # Resumen por municipio
        with st.expander("Resumen por municipio"):
            resumen_muni = (
                df_filtrado.groupby("muni_key")
                .agg(
                    registros=("diferencia", "count"),
                    diff_acumulada=("diferencia", "sum"),
                    mesas=("mesa_key", "nunique"),
                )
                .reset_index()
                .sort_values("diff_acumulada", key=abs, ascending=False)
            )
            resumen_muni["Municipio"] = resumen_muni["muni_key"].apply(
                lambda mk: nombre_municipio_str(mk, divipol)
            )
            st.dataframe(
                resumen_muni[
                    ["Municipio", "muni_key", "registros", "diff_acumulada", "mesas"]
                ].rename(
                    columns={
                        "muni_key": "Clave",
                        "registros": "Registros",
                        "diff_acumulada": "Diff acumulada",
                        "mesas": "Mesas",
                    }
                ),
                use_container_width=True,
                height=250,
            )

        # Resumen por candidato
        with st.expander("Resumen por candidato"):
            resumen_cand = (
                df_filtrado.groupby("cand_key")
                .agg(
                    registros=("diferencia", "count"),
                    diff_acumulada=("diferencia", "sum"),
                    mesas=("mesa_key", "nunique"),
                )
                .reset_index()
                .sort_values("diff_acumulada", key=abs, ascending=False)
            )
            resumen_cand["Candidato"] = resumen_cand["cand_key"].apply(
                lambda k: nombre_candidato(k, candidatos_meta)
            )
            st.dataframe(
                resumen_cand[
                    ["Candidato", "cand_key", "registros", "diff_acumulada", "mesas"]
                ].rename(
                    columns={
                        "cand_key": "Clave",
                        "registros": "Registros",
                        "diff_acumulada": "Diff acumulada",
                        "mesas": "Mesas",
                    }
                ),
                use_container_width=True,
                height=250,
            )
    else:
        st.info("Sin registros que coincidan con los filtros.")
