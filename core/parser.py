"""
core/parser.py
──────────────
Parsea y agrega el archivo MMV en memoria.
Incluye caché en Parquet para acelerar arranques en Streamlit.

Estructura del archivo (38 chars ancho fijo):
  cod_depto(2) cod_muni(3) zona(2) puesto(2) num_mesa(6)
  cod_jal(2) num_comunicado(4) circunscripcion(1)
  cod_partido(5) cod_candidato(3) votos(8)

circunscripcion:
  1 = Senado (nacional)
  2 = Cámara (departamental)
  (otros valores posibles según el archivo real)

Antioquia = cod_depto "01"
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st

COD_LISTA = "000"
COD_BLANCO = "996"
COD_NULO = "997"
COD_NO_MARC = "998"

COD_ANTIOQUIA = "01"
CACHE_VERSION = 2

_CACHE_FILES = {
    "meta": "meta.parquet",
    "candidatos": "candidatos.parquet",
    "partidos": "partidos.parquet",
    "municipios": "municipios.parquet",
    "deptos": "deptos.parquet",
    "stats_circ": "stats_circ.parquet",
    "totales_circ": "totales_circ.parquet",
    "partidos_circ": "partidos_circ.parquet",
}


def _parsear_linea(linea: str) -> dict | None:
    linea = linea.rstrip("\r\n")
    if len(linea) < 38:
        return None
    try:
        return {
            "cod_depto": linea[0:2],
            "cod_muni": linea[2:5],
            "zona": linea[5:7],
            "puesto": linea[7:9],
            "num_mesa": linea[9:15],
            "cod_jal": linea[15:17],
            "circunscripcion": linea[21:22],
            "cod_partido": linea[22:27],
            "cod_candidato": linea[27:30],
            "votos": int(linea[30:38]) if linea[30:38].strip().isdigit() else 0,
        }
    except Exception:
        return None


def _parquet_disponible() -> bool:
    try:
        import pyarrow  # noqa: F401

        return True
    except Exception:
        return False


def _cache_dirs(mmv_path: Path) -> list[Path]:
    d1 = mmv_path.parent / "cache_parquet" / mmv_path.stem
    d2 = Path("/tmp/electoral-dashboard-cache") / mmv_path.stem
    if d1 == d2:
        return [d1]
    return [d1, d2]


def _source_signature(mmv_path: Path) -> dict:
    stt = mmv_path.stat()
    return {
        "cache_version": CACHE_VERSION,
        "source_name": mmv_path.name,
        "source_size": int(stt.st_size),
        "source_mtime_ns": int(stt.st_mtime_ns),
    }


def _dump_map(d: dict) -> str:
    if not d:
        return "{}"
    return json.dumps(
        {str(k): int(v) for k, v in d.items()},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _load_map(raw) -> dict[str, int]:
    if raw is None:
        return {}
    if isinstance(raw, float) and pd.isna(raw):
        return {}
    try:
        d = json.loads(str(raw))
        return {str(k): int(v) for k, v in d.items()}
    except Exception:
        return {}


def _dump_list(items) -> str:
    if not items:
        return "[]"
    return json.dumps(sorted(str(x) for x in items), ensure_ascii=False, separators=(",", ":"))


def _load_list(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, float) and pd.isna(raw):
        return []
    try:
        arr = json.loads(str(raw))
        if isinstance(arr, list):
            return [str(x) for x in arr]
        return []
    except Exception:
        return []


def _cache_valido(cache_dir: Path, sig: dict) -> bool:
    meta_path = cache_dir / _CACHE_FILES["meta"]
    if not meta_path.exists():
        return False
    for key, fname in _CACHE_FILES.items():
        if key == "meta":
            continue
        if not (cache_dir / fname).exists():
            return False
    try:
        mdf = pd.read_parquet(meta_path)
        if mdf.empty:
            return False
        row = mdf.iloc[0].to_dict()
        return (
            int(row.get("cache_version", -1)) == int(sig["cache_version"])
            and str(row.get("source_name", "")) == str(sig["source_name"])
            and int(row.get("source_size", -1)) == int(sig["source_size"])
            and int(row.get("source_mtime_ns", -1)) == int(sig["source_mtime_ns"])
        )
    except Exception:
        return False


def _cargar_desde_cache_parquet(mmv_path: Path) -> dict | None:
    if not _parquet_disponible() or not mmv_path.exists():
        return None
    sig = _source_signature(mmv_path)

    for cache_dir in _cache_dirs(mmv_path):
        if not _cache_valido(cache_dir, sig):
            continue
        try:
            candidatos = {}
            cdf = pd.read_parquet(cache_dir / _CACHE_FILES["candidatos"])
            for row in cdf.itertuples(index=False):
                candidatos[str(row.cand_key)] = {
                    "votos_total": int(row.votos_total),
                    "por_depto": _load_map(row.por_depto_json),
                    "por_municipio": _load_map(row.por_municipio_json),
                    "por_puesto": _load_map(row.por_puesto_json),
                    "por_mesa": _load_map(row.por_mesa_json),
                    "cod_partido": str(row.cod_partido),
                    "cod_candidato": str(row.cod_candidato),
                    "circunscripcion": str(row.circunscripcion),
                }

            partidos = {}
            pdf = pd.read_parquet(cache_dir / _CACHE_FILES["partidos"])
            for row in pdf.itertuples(index=False):
                partidos[str(row.cod_partido)] = {
                    "votos_total": int(row.votos_total),
                    "por_depto": _load_map(row.por_depto_json),
                    "por_municipio": _load_map(row.por_municipio_json),
                    "por_puesto": _load_map(row.por_puesto_json),
                    "por_mesa": _load_map(row.por_mesa_json),
                    "circunscripcion": str(row.circunscripcion),
                }

            municipios = {}
            mdf = pd.read_parquet(cache_dir / _CACHE_FILES["municipios"])
            for row in mdf.itertuples(index=False):
                municipios[str(row.muni_key)] = {
                    "mesas": set(_load_list(row.mesas_json)),
                    "votos_validos": int(row.votos_validos),
                    "votos_blanco": int(row.votos_blanco),
                    "votos_nulo": int(row.votos_nulo),
                    "votos_no_marcado": int(row.votos_no_marcado),
                    "cod_depto": str(row.cod_depto),
                    "cod_muni": str(row.cod_muni),
                }

            deptos = {}
            ddf = pd.read_parquet(cache_dir / _CACHE_FILES["deptos"])
            for row in ddf.itertuples(index=False):
                deptos[str(row.cod_depto)] = {
                    "municipios": set(_load_list(row.municipios_json)),
                    "mesas": set(_load_list(row.mesas_json)),
                    "votos_validos": int(row.votos_validos),
                    "votos_blanco": int(row.votos_blanco),
                    "votos_nulo": int(row.votos_nulo),
                    "votos_no_marcado": int(row.votos_no_marcado),
                }

            stats_por_circ = {}
            sdf = pd.read_parquet(cache_dir / _CACHE_FILES["stats_circ"])
            for row in sdf.itertuples(index=False):
                stats_por_circ[str(row.circ)] = {
                    "votos_total": int(row.votos_total),
                    "votos_validos_candidatos": int(row.votos_validos_candidatos),
                    "votos_lista": int(row.votos_lista),
                    "votos_validos_total": int(row.votos_validos_total),
                    "votos_blanco": int(row.votos_blanco),
                    "votos_nulo": int(row.votos_nulo),
                    "votos_no_marcado": int(row.votos_no_marcado),
                }

            totales_validos_por_circ = {}
            tdf = pd.read_parquet(cache_dir / _CACHE_FILES["totales_circ"])
            for row in tdf.itertuples(index=False):
                totales_validos_por_circ[str(row.circ)] = {
                    "por_municipio": _load_map(row.por_municipio_json),
                    "por_puesto": _load_map(row.por_puesto_json),
                    "por_mesa": _load_map(row.por_mesa_json),
                }

            partidos_por_circ = {}
            pcf = pd.read_parquet(cache_dir / _CACHE_FILES["partidos_circ"])
            for row in pcf.itertuples(index=False):
                circ = str(row.circ)
                cod = str(row.cod_partido)
                partidos_por_circ.setdefault(circ, {})
                partidos_por_circ[circ][cod] = {
                    "votos_lista": int(row.votos_lista),
                    "votos_candidatos": int(row.votos_candidatos),
                    "votos_validos_total": int(row.votos_validos_total),
                    "por_depto_validos_total": _load_map(row.por_depto_json),
                    "por_municipio_validos_total": _load_map(row.por_municipio_json),
                    "por_puesto_validos_total": _load_map(row.por_puesto_json),
                    "por_mesa_validos_total": _load_map(row.por_mesa_json),
                }

            meta_df = pd.read_parquet(cache_dir / _CACHE_FILES["meta"])
            meta = meta_df.iloc[0].to_dict() if not meta_df.empty else {}

            return {
                "candidatos": candidatos,
                "partidos": partidos,
                "municipios": municipios,
                "deptos": deptos,
                "stats_por_circ": stats_por_circ,
                "partidos_por_circ": partidos_por_circ,
                "totales_validos_por_circ": totales_validos_por_circ,
                "mesas_count": int(meta.get("mesas_count", 0)),
                "total_lineas": int(meta.get("total_lineas", 0)),
            }
        except Exception:
            continue
    return None


def _guardar_cache_parquet(mmv: dict, mmv_path: Path) -> None:
    if not _parquet_disponible() or not mmv_path.exists():
        return
    sig = _source_signature(mmv_path)
    target_dir = None
    for cache_dir in _cache_dirs(mmv_path):
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            target_dir = cache_dir
            break
        except Exception:
            continue
    if target_dir is None:
        return

    def _write_rows(rows: list[dict], columns: list[str], out_path: Path) -> None:
        pd.DataFrame(rows, columns=columns).to_parquet(
            out_path,
            index=False,
            compression="zstd",
        )

    try:
        c_rows = []
        for cand_key, d in mmv.get("candidatos", {}).items():
            c_rows.append(
                {
                    "cand_key": cand_key,
                    "votos_total": int(d.get("votos_total", 0)),
                    "por_depto_json": _dump_map(d.get("por_depto", {})),
                    "por_municipio_json": _dump_map(d.get("por_municipio", {})),
                    "por_puesto_json": _dump_map(d.get("por_puesto", {})),
                    "por_mesa_json": _dump_map(d.get("por_mesa", {})),
                    "cod_partido": str(d.get("cod_partido", "")),
                    "cod_candidato": str(d.get("cod_candidato", "")),
                    "circunscripcion": str(d.get("circunscripcion", "")),
                }
            )
        _write_rows(
            c_rows,
            [
                "cand_key",
                "votos_total",
                "por_depto_json",
                "por_municipio_json",
                "por_puesto_json",
                "por_mesa_json",
                "cod_partido",
                "cod_candidato",
                "circunscripcion",
            ],
            target_dir / _CACHE_FILES["candidatos"],
        )

        p_rows = []
        for cod_partido, d in mmv.get("partidos", {}).items():
            p_rows.append(
                {
                    "cod_partido": cod_partido,
                    "votos_total": int(d.get("votos_total", 0)),
                    "por_depto_json": _dump_map(d.get("por_depto", {})),
                    "por_municipio_json": _dump_map(d.get("por_municipio", {})),
                    "por_puesto_json": _dump_map(d.get("por_puesto", {})),
                    "por_mesa_json": _dump_map(d.get("por_mesa", {})),
                    "circunscripcion": str(d.get("circunscripcion", "")),
                }
            )
        _write_rows(
            p_rows,
            [
                "cod_partido",
                "votos_total",
                "por_depto_json",
                "por_municipio_json",
                "por_puesto_json",
                "por_mesa_json",
                "circunscripcion",
            ],
            target_dir / _CACHE_FILES["partidos"],
        )

        m_rows = []
        for muni_key, d in mmv.get("municipios", {}).items():
            m_rows.append(
                {
                    "muni_key": muni_key,
                    "mesas_json": _dump_list(d.get("mesas", [])),
                    "votos_validos": int(d.get("votos_validos", 0)),
                    "votos_blanco": int(d.get("votos_blanco", 0)),
                    "votos_nulo": int(d.get("votos_nulo", 0)),
                    "votos_no_marcado": int(d.get("votos_no_marcado", 0)),
                    "cod_depto": str(d.get("cod_depto", "")),
                    "cod_muni": str(d.get("cod_muni", "")),
                }
            )
        _write_rows(
            m_rows,
            [
                "muni_key",
                "mesas_json",
                "votos_validos",
                "votos_blanco",
                "votos_nulo",
                "votos_no_marcado",
                "cod_depto",
                "cod_muni",
            ],
            target_dir / _CACHE_FILES["municipios"],
        )

        d_rows = []
        for cod_depto, d in mmv.get("deptos", {}).items():
            d_rows.append(
                {
                    "cod_depto": cod_depto,
                    "municipios_json": _dump_list(d.get("municipios", [])),
                    "mesas_json": _dump_list(d.get("mesas", [])),
                    "votos_validos": int(d.get("votos_validos", 0)),
                    "votos_blanco": int(d.get("votos_blanco", 0)),
                    "votos_nulo": int(d.get("votos_nulo", 0)),
                    "votos_no_marcado": int(d.get("votos_no_marcado", 0)),
                }
            )
        _write_rows(
            d_rows,
            [
                "cod_depto",
                "municipios_json",
                "mesas_json",
                "votos_validos",
                "votos_blanco",
                "votos_nulo",
                "votos_no_marcado",
            ],
            target_dir / _CACHE_FILES["deptos"],
        )

        s_rows = []
        for circ, d in mmv.get("stats_por_circ", {}).items():
            s_rows.append(
                {
                    "circ": str(circ),
                    "votos_total": int(d.get("votos_total", 0)),
                    "votos_validos_candidatos": int(d.get("votos_validos_candidatos", 0)),
                    "votos_lista": int(d.get("votos_lista", 0)),
                    "votos_validos_total": int(d.get("votos_validos_total", 0)),
                    "votos_blanco": int(d.get("votos_blanco", 0)),
                    "votos_nulo": int(d.get("votos_nulo", 0)),
                    "votos_no_marcado": int(d.get("votos_no_marcado", 0)),
                }
            )
        _write_rows(
            s_rows,
            [
                "circ",
                "votos_total",
                "votos_validos_candidatos",
                "votos_lista",
                "votos_validos_total",
                "votos_blanco",
                "votos_nulo",
                "votos_no_marcado",
            ],
            target_dir / _CACHE_FILES["stats_circ"],
        )

        t_rows = []
        for circ, d in mmv.get("totales_validos_por_circ", {}).items():
            t_rows.append(
                {
                    "circ": str(circ),
                    "por_municipio_json": _dump_map(d.get("por_municipio", {})),
                    "por_puesto_json": _dump_map(d.get("por_puesto", {})),
                    "por_mesa_json": _dump_map(d.get("por_mesa", {})),
                }
            )
        _write_rows(
            t_rows,
            ["circ", "por_municipio_json", "por_puesto_json", "por_mesa_json"],
            target_dir / _CACHE_FILES["totales_circ"],
        )

        pc_rows = []
        for circ, partidos_circ in mmv.get("partidos_por_circ", {}).items():
            for cod_partido, d in partidos_circ.items():
                pc_rows.append(
                    {
                        "circ": str(circ),
                        "cod_partido": str(cod_partido),
                        "votos_lista": int(d.get("votos_lista", 0)),
                        "votos_candidatos": int(d.get("votos_candidatos", 0)),
                        "votos_validos_total": int(d.get("votos_validos_total", 0)),
                        "por_depto_json": _dump_map(d.get("por_depto_validos_total", {})),
                        "por_municipio_json": _dump_map(d.get("por_municipio_validos_total", {})),
                        "por_puesto_json": _dump_map(d.get("por_puesto_validos_total", {})),
                        "por_mesa_json": _dump_map(d.get("por_mesa_validos_total", {})),
                    }
                )
        _write_rows(
            pc_rows,
            [
                "circ",
                "cod_partido",
                "votos_lista",
                "votos_candidatos",
                "votos_validos_total",
                "por_depto_json",
                "por_municipio_json",
                "por_puesto_json",
                "por_mesa_json",
            ],
            target_dir / _CACHE_FILES["partidos_circ"],
        )

        meta = {
            **sig,
            "mesas_count": int(mmv.get("mesas_count", 0)),
            "total_lineas": int(mmv.get("total_lineas", 0)),
        }
        pd.DataFrame([meta]).to_parquet(
            target_dir / _CACHE_FILES["meta"],
            index=False,
            compression="zstd",
        )
    except Exception:
        return


def _procesar_mmv_txt(path: str) -> dict:
    candidatos = defaultdict(
        lambda: {
            "votos_total": 0,
            "por_depto": defaultdict(int),
            "por_municipio": defaultdict(int),
            # {depto_muni_zona_puesto: votos}  — para drill-down a puesto
            "por_puesto": defaultdict(int),
            # {mesa_key: votos}  — para drill-down a mesa individual
            "por_mesa": defaultdict(int),
            "cod_partido": "",
            "cod_candidato": "",
            "circunscripcion": "",
        }
    )
    partidos = defaultdict(
        lambda: {
            "votos_total": 0,
            "por_depto": defaultdict(int),
            "por_municipio": defaultdict(int),
            "por_puesto": defaultdict(int),
            "por_mesa": defaultdict(int),
            "circunscripcion": "",
        }
    )
    municipios = defaultdict(
        lambda: {
            "mesas": set(),
            "votos_validos": 0,
            "votos_blanco": 0,
            "votos_nulo": 0,
            "votos_no_marcado": 0,
            "cod_depto": "",
            "cod_muni": "",
        }
    )
    deptos = defaultdict(
        lambda: {
            "municipios": set(),
            "mesas": set(),
            "votos_validos": 0,
            "votos_blanco": 0,
            "votos_nulo": 0,
            "votos_no_marcado": 0,
        }
    )
    stats_por_circ = defaultdict(
        lambda: {
            "votos_total": 0,
            "votos_validos_candidatos": 0,
            "votos_lista": 0,
            "votos_validos_total": 0,  # candidatos + lista
            "votos_blanco": 0,
            "votos_nulo": 0,
            "votos_no_marcado": 0,
        }
    )
    totales_validos_por_circ = defaultdict(
        lambda: {
            "por_municipio": defaultdict(int),
            "por_puesto": defaultdict(int),
            "por_mesa": defaultdict(int),
        }
    )
    partidos_por_circ = defaultdict(
        lambda: defaultdict(
            lambda: {
                "votos_lista": 0,
                "votos_candidatos": 0,
                "votos_validos_total": 0,  # lista + candidatos
                "por_depto_validos_total": defaultdict(int),
                "por_municipio_validos_total": defaultdict(int),
                "por_puesto_validos_total": defaultdict(int),
                "por_mesa_validos_total": defaultdict(int),
            }
        )
    )

    mesas_set = set()
    total_lineas = 0

    with open(path, encoding="latin-1") as f:
        for linea in f:
            if not linea.strip():
                continue
            total_lineas += 1
            r = _parsear_linea(linea)
            if not r:
                continue

            partido = r["cod_partido"]
            candidato = r["cod_candidato"]
            votos = r["votos"]
            depto = r["cod_depto"]
            muni = r["cod_muni"]
            zona = r["zona"]
            puesto = r["puesto"]
            circ = r["circunscripcion"]
            mesa_key = f"{depto}_{muni}_{zona}_{puesto}_{r['num_mesa']}"
            puesto_key = f"{depto}_{muni}_{zona}_{puesto}"
            muni_key = f"{depto}_{muni}"
            cand_key = f"{partido}_{candidato}"
            stats_por_circ[circ]["votos_total"] += votos

            mesas_set.add(mesa_key)
            municipios[muni_key]["cod_depto"] = depto
            municipios[muni_key]["cod_muni"] = muni
            municipios[muni_key]["mesas"].add(mesa_key)
            deptos[depto]["municipios"].add(muni_key)
            deptos[depto]["mesas"].add(mesa_key)

            # Votos especiales
            if candidato == COD_BLANCO:
                municipios[muni_key]["votos_blanco"] += votos
                deptos[depto]["votos_blanco"] += votos
                stats_por_circ[circ]["votos_blanco"] += votos
                continue
            if candidato == COD_NULO:
                municipios[muni_key]["votos_nulo"] += votos
                deptos[depto]["votos_nulo"] += votos
                stats_por_circ[circ]["votos_nulo"] += votos
                continue
            if candidato == COD_NO_MARC:
                municipios[muni_key]["votos_no_marcado"] += votos
                deptos[depto]["votos_no_marcado"] += votos
                stats_por_circ[circ]["votos_no_marcado"] += votos
                continue

            # Votos válidos — no duplicar lista + preferente
            if candidato != COD_LISTA:
                municipios[muni_key]["votos_validos"] += votos
                deptos[depto]["votos_validos"] += votos
                stats_por_circ[circ]["votos_validos_candidatos"] += votos
                stats_por_circ[circ]["votos_validos_total"] += votos
                totales_validos_por_circ[circ]["por_municipio"][muni_key] += votos
                totales_validos_por_circ[circ]["por_puesto"][puesto_key] += votos
                totales_validos_por_circ[circ]["por_mesa"][mesa_key] += votos
                partidos_por_circ[circ][partido]["votos_candidatos"] += votos
                partidos_por_circ[circ][partido]["votos_validos_total"] += votos
                partidos_por_circ[circ][partido]["por_depto_validos_total"][depto] += votos
                partidos_por_circ[circ][partido]["por_municipio_validos_total"][muni_key] += votos
                partidos_por_circ[circ][partido]["por_puesto_validos_total"][puesto_key] += votos
                partidos_por_circ[circ][partido]["por_mesa_validos_total"][mesa_key] += votos
            else:
                stats_por_circ[circ]["votos_lista"] += votos
                stats_por_circ[circ]["votos_validos_total"] += votos
                totales_validos_por_circ[circ]["por_municipio"][muni_key] += votos
                totales_validos_por_circ[circ]["por_puesto"][puesto_key] += votos
                totales_validos_por_circ[circ]["por_mesa"][mesa_key] += votos
                partidos_por_circ[circ][partido]["votos_lista"] += votos
                partidos_por_circ[circ][partido]["votos_validos_total"] += votos
                partidos_por_circ[circ][partido]["por_depto_validos_total"][depto] += votos
                partidos_por_circ[circ][partido]["por_municipio_validos_total"][muni_key] += votos
                partidos_por_circ[circ][partido]["por_puesto_validos_total"][puesto_key] += votos
                partidos_por_circ[circ][partido]["por_mesa_validos_total"][mesa_key] += votos

            # Candidatos (solo preferentes, no cabeceras)
            if candidato != COD_LISTA:
                candidatos[cand_key]["votos_total"] += votos
                candidatos[cand_key]["por_depto"][depto] += votos
                candidatos[cand_key]["por_municipio"][muni_key] += votos
                candidatos[cand_key]["por_puesto"][puesto_key] += votos
                candidatos[cand_key]["por_mesa"][mesa_key] += votos
                candidatos[cand_key]["cod_partido"] = partido
                candidatos[cand_key]["cod_candidato"] = candidato
                candidatos[cand_key]["circunscripcion"] = circ

            # Partidos (solo votos de lista 000)
            if candidato == COD_LISTA:
                partidos[partido]["votos_total"] += votos
                partidos[partido]["por_depto"][depto] += votos
                partidos[partido]["por_municipio"][muni_key] += votos
                partidos[partido]["por_puesto"][puesto_key] += votos
                partidos[partido]["por_mesa"][mesa_key] += votos
                partidos[partido]["circunscripcion"] = circ

    partidos_por_circ_out = {}
    for circ, partidos_circ in partidos_por_circ.items():
        partidos_por_circ_out[circ] = {}
        for cod_partido, d in partidos_circ.items():
            partidos_por_circ_out[circ][cod_partido] = {
                "votos_lista": d["votos_lista"],
                "votos_candidatos": d["votos_candidatos"],
                "votos_validos_total": d["votos_validos_total"],
                "por_depto_validos_total": dict(d["por_depto_validos_total"]),
                "por_municipio_validos_total": dict(d["por_municipio_validos_total"]),
                "por_puesto_validos_total": dict(d["por_puesto_validos_total"]),
                "por_mesa_validos_total": dict(d["por_mesa_validos_total"]),
            }
    totales_validos_por_circ_out = {}
    for circ, d in totales_validos_por_circ.items():
        totales_validos_por_circ_out[circ] = {
            "por_municipio": dict(d["por_municipio"]),
            "por_puesto": dict(d["por_puesto"]),
            "por_mesa": dict(d["por_mesa"]),
        }

    return {
        "candidatos": dict(candidatos),
        "partidos": dict(partidos),
        "municipios": dict(municipios),
        "deptos": dict(deptos),
        "stats_por_circ": dict(stats_por_circ),
        "partidos_por_circ": partidos_por_circ_out,
        "totales_validos_por_circ": totales_validos_por_circ_out,
        "mesas_count": len(mesas_set),
        "total_lineas": total_lineas,
    }


@st.cache_resource(show_spinner=False)
def procesar_mmv(path: str, cache_key: str = "") -> dict:
    """
    Lee MMV y retorna agregados en memoria.
    Flujo:
      1) Intenta cargar agregado desde caché Parquet (rápido).
      2) Si no existe o cambió el TXT, parsea línea por línea.
      3) Persiste el agregado a Parquet para próximos arranques.
    """
    _ = cache_key
    mmv_path = Path(path)
    from_cache = _cargar_desde_cache_parquet(mmv_path)
    if from_cache is not None:
        from_cache["cache_meta"] = {"load_source": "parquet", "cache_key": cache_key}
        return from_cache

    mmv = _procesar_mmv_txt(path)
    _guardar_cache_parquet(mmv, mmv_path)
    mmv["cache_meta"] = {"load_source": "txt", "cache_key": cache_key}
    return mmv
