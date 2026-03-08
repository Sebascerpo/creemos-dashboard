"""
core/parser.py
──────────────
Parsea y agrega el archivo MMV en memoria.
Incluye caché en Parquet para acelerar arranques en Streamlit.

Estructura del archivo (38 chars ancho fijo):
  cod_depto(2) cod_muni(3) zona(2) puesto(2) num_mesa(6)
  cod_jal(2) num_comunicado(4) circunscripcion(1)
  cod_partido(5) cod_candidato(3) votos(8)

OPTIMIZACIÓN DE MEMORIA (v4):
  Solo se cargan en RAM los datos estrictamente necesarios para
  la vista inicial (votos_total, por_depto, conteos).
  Los datos de por_municipio, por_puesto y por_mesa se almacenan
  en Parquet separados y se cargan bajo demanda (lazy loading).
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st

COD_LISTA = "000"
COD_BLANCO = "996"
COD_NULO = "997"
COD_NO_MARC = "998"

COD_ANTIOQUIA = "01"
CACHE_VERSION = 4  # v4: aggressive lazy loading

# Archivos que se cargan al arranque (livianos)
_CACHE_FILES = {
    "meta": "meta.parquet",
    "candidatos": "candidatos_lite.parquet",
    "partidos": "partidos_lite.parquet",
    "municipios": "municipios.parquet",
    "deptos": "deptos.parquet",
    "stats_circ": "stats_circ.parquet",
    "totales_circ": "totales_circ_lite.parquet",
    "partidos_circ": "partidos_circ_lite.parquet",
}

# Archivos para lazy loading (pesados, se cargan bajo demanda)
_LAZY_FILES = {
    "candidatos_geo": "candidatos_geo.parquet",  # por_municipio + por_puesto
    "candidatos_mesa": "candidatos_mesa.parquet",  # por_mesa
    "partidos_circ_geo": "partidos_circ_geo.parquet",  # por_municipio + por_puesto
    "partidos_circ_mesa": "partidos_circ_mesa.parquet",
    "totales_circ_geo": "totales_circ_geo.parquet",  # por_municipio + por_puesto
    "totales_circ_mesa": "totales_circ_mesa.parquet",
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
    return json.dumps(
        sorted(str(x) for x in items), ensure_ascii=False, separators=(",", ":")
    )


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
    # Check all required files exist
    for fname in _CACHE_FILES.values():
        if not (cache_dir / fname).exists():
            return False
    for fname in _LAZY_FILES.values():
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
        )
    except Exception:
        return False


def _resolve_cache_dir(mmv_path: Path) -> Path | None:
    if not _parquet_disponible() or not mmv_path.exists():
        return None
    sig = _source_signature(mmv_path)
    for cache_dir in _cache_dirs(mmv_path):
        if _cache_valido(cache_dir, sig):
            return cache_dir
    return None


# ──────────────────────────────────────────────
# LAZY LOADING FUNCTIONS
# ──────────────────────────────────────────────


def _get_mtime(path_str: str) -> float:
    try:
        return os.path.getmtime(path_str)
    except Exception:
        return 0.0


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_cargar_geo_candidato(
    mmv_path_str: str, cand_key: str, _mtime: float
) -> dict:
    """Carga por_municipio y por_puesto para un candidato."""
    cache_dir = _resolve_cache_dir(Path(mmv_path_str))
    if cache_dir is None:
        return {"por_municipio": {}, "por_puesto": {}}
    fpath = cache_dir / _LAZY_FILES["candidatos_geo"]
    if not fpath.exists():
        return {"por_municipio": {}, "por_puesto": {}}
    try:
        df = pd.read_parquet(fpath, filters=[("cand_key", "==", cand_key)])
        if df.empty:
            return {"por_municipio": {}, "por_puesto": {}}
        row = df.iloc[0]
        return {
            "por_municipio": _load_map(row["por_municipio_json"]),
            "por_puesto": _load_map(row["por_puesto_json"]),
        }
    except Exception:
        return {"por_municipio": {}, "por_puesto": {}}


def cargar_geo_candidato(mmv_path_str: str, cand_key: str) -> dict:
    return _cached_cargar_geo_candidato(
        mmv_path_str, cand_key, _get_mtime(mmv_path_str)
    )


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_cargar_mesa_candidato(
    mmv_path_str: str, cand_key: str, _mtime: float
) -> dict[str, int]:
    """Carga por_mesa para un candidato."""
    cache_dir = _resolve_cache_dir(Path(mmv_path_str))
    if cache_dir is None:
        return {}
    fpath = cache_dir / _LAZY_FILES["candidatos_mesa"]
    if not fpath.exists():
        return {}
    try:
        df = pd.read_parquet(fpath, filters=[("cand_key", "==", cand_key)])
        if df.empty:
            return {}
        return _load_map(df.iloc[0]["por_mesa_json"])
    except Exception:
        return {}


def cargar_mesa_candidato(mmv_path_str: str, cand_key: str) -> dict[str, int]:
    return _cached_cargar_mesa_candidato(
        mmv_path_str, cand_key, _get_mtime(mmv_path_str)
    )


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_cargar_geo_partido_circ(
    mmv_path_str: str, circ: str, cod_partido: str, _mtime: float
) -> dict:
    """Carga por_municipio y por_puesto para un partido en una circunscripción."""
    cache_dir = _resolve_cache_dir(Path(mmv_path_str))
    if cache_dir is None:
        return {"por_municipio": {}, "por_puesto": {}}
    fpath = cache_dir / _LAZY_FILES["partidos_circ_geo"]
    if not fpath.exists():
        return {"por_municipio": {}, "por_puesto": {}}
    try:
        df = pd.read_parquet(
            fpath, filters=[("circ", "==", circ), ("cod_partido", "==", cod_partido)]
        )
        if df.empty:
            return {"por_municipio": {}, "por_puesto": {}}
        row = df.iloc[0]
        return {
            "por_municipio": _load_map(row["por_municipio_json"]),
            "por_puesto": _load_map(row["por_puesto_json"]),
        }
    except Exception:
        return {"por_municipio": {}, "por_puesto": {}}


def cargar_geo_partido_circ(mmv_path_str: str, circ: str, cod_partido: str) -> dict:
    return _cached_cargar_geo_partido_circ(
        mmv_path_str, circ, cod_partido, _get_mtime(mmv_path_str)
    )


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_cargar_mesa_partido_circ(
    mmv_path_str: str, circ: str, cod_partido: str, _mtime: float
) -> dict[str, int]:
    """Carga por_mesa para un partido en una circunscripción."""
    cache_dir = _resolve_cache_dir(Path(mmv_path_str))
    if cache_dir is None:
        return {}
    fpath = cache_dir / _LAZY_FILES["partidos_circ_mesa"]
    if not fpath.exists():
        return {}
    try:
        df = pd.read_parquet(
            fpath, filters=[("circ", "==", circ), ("cod_partido", "==", cod_partido)]
        )
        if df.empty:
            return {}
        return _load_map(df.iloc[0]["por_mesa_json"])
    except Exception:
        return {}


def cargar_mesa_partido_circ(
    mmv_path_str: str, circ: str, cod_partido: str
) -> dict[str, int]:
    return _cached_cargar_mesa_partido_circ(
        mmv_path_str, circ, cod_partido, _get_mtime(mmv_path_str)
    )


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_cargar_geo_totales_circ(
    mmv_path_str: str, circ: str, _mtime: float
) -> dict:
    """Carga por_municipio y por_puesto totales para una circunscripción."""
    cache_dir = _resolve_cache_dir(Path(mmv_path_str))
    if cache_dir is None:
        return {"por_municipio": {}, "por_puesto": {}}
    fpath = cache_dir / _LAZY_FILES["totales_circ_geo"]
    if not fpath.exists():
        return {"por_municipio": {}, "por_puesto": {}}
    try:
        df = pd.read_parquet(fpath, filters=[("circ", "==", circ)])
        if df.empty:
            return {"por_municipio": {}, "por_puesto": {}}
        row = df.iloc[0]
        return {
            "por_municipio": _load_map(row["por_municipio_json"]),
            "por_puesto": _load_map(row["por_puesto_json"]),
        }
    except Exception:
        return {"por_municipio": {}, "por_puesto": {}}


def cargar_geo_totales_circ(mmv_path_str: str, circ: str) -> dict:
    return _cached_cargar_geo_totales_circ(mmv_path_str, circ, _get_mtime(mmv_path_str))


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_cargar_mesa_totales_circ(
    mmv_path_str: str, circ: str, _mtime: float
) -> dict[str, int]:
    """Carga por_mesa totales para una circunscripción."""
    cache_dir = _resolve_cache_dir(Path(mmv_path_str))
    if cache_dir is None:
        return {}
    fpath = cache_dir / _LAZY_FILES["totales_circ_mesa"]
    if not fpath.exists():
        return {}
    try:
        df = pd.read_parquet(fpath, filters=[("circ", "==", circ)])
        if df.empty:
            return {}
        return _load_map(df.iloc[0]["por_mesa_json"])
    except Exception:
        return {}


def cargar_mesa_totales_circ(mmv_path_str: str, circ: str) -> dict[str, int]:
    return _cached_cargar_mesa_totales_circ(
        mmv_path_str, circ, _get_mtime(mmv_path_str)
    )


# ──────────────────────────────────────────────
# CARGA DESDE CACHÉ PARQUET (solo datos livianos)
# ──────────────────────────────────────────────


def _cargar_desde_cache_parquet(mmv_path: Path) -> dict | None:
    if not _parquet_disponible() or not mmv_path.exists():
        return None
    sig = _source_signature(mmv_path)

    for cache_dir in _cache_dirs(mmv_path):
        if not _cache_valido(cache_dir, sig):
            continue
        try:
            # ── Candidatos LITE: solo votos_total, por_depto, n_municipios ──
            candidatos = {}
            cdf = pd.read_parquet(cache_dir / _CACHE_FILES["candidatos"])
            for row in cdf.itertuples(index=False):
                candidatos[str(row.cand_key)] = {
                    "votos_total": int(row.votos_total),
                    "por_depto": _load_map(row.por_depto_json),
                    "n_municipios": int(row.n_municipios),
                    "cod_partido": str(row.cod_partido),
                    "cod_candidato": str(row.cod_candidato),
                    "circunscripcion": str(row.circunscripcion),
                }

            # ── Partidos LITE ──
            partidos = {}
            pdf = pd.read_parquet(cache_dir / _CACHE_FILES["partidos"])
            for row in pdf.itertuples(index=False):
                partidos[str(row.cod_partido)] = {
                    "votos_total": int(row.votos_total),
                    "por_depto": _load_map(row.por_depto_json),
                    "circunscripcion": str(row.circunscripcion),
                }

            # ── Municipios ──
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

            # ── Deptos ──
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

            # ── Stats circ ──
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

            # ── Totales circ LITE (sin por_municipio/por_puesto/por_mesa) ──
            totales_validos_por_circ = {}
            tdf = pd.read_parquet(cache_dir / _CACHE_FILES["totales_circ"])
            for row in tdf.itertuples(index=False):
                totales_validos_por_circ[str(row.circ)] = {}

            # ── Partidos circ LITE (solo por_depto) ──
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


# ──────────────────────────────────────────────
# GUARDAR CACHÉ
# ──────────────────────────────────────────────


def _guardar_cache_parquet(mmv: dict, mmv_path: Path, heavy: dict) -> None:
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

    def _w(rows, cols, out):
        pd.DataFrame(rows, columns=cols).to_parquet(
            out, index=False, compression="zstd"
        )

    try:
        # ── Candidatos LITE ──
        _w(
            [
                {
                    "cand_key": k,
                    "votos_total": int(d["votos_total"]),
                    "por_depto_json": _dump_map(d["por_depto"]),
                    "n_municipios": int(d.get("n_municipios", 0)),
                    "cod_partido": str(d["cod_partido"]),
                    "cod_candidato": str(d["cod_candidato"]),
                    "circunscripcion": str(d["circunscripcion"]),
                }
                for k, d in mmv.get("candidatos", {}).items()
            ],
            [
                "cand_key",
                "votos_total",
                "por_depto_json",
                "n_municipios",
                "cod_partido",
                "cod_candidato",
                "circunscripcion",
            ],
            target_dir / _CACHE_FILES["candidatos"],
        )

        # ── Candidatos GEO (lazy) ──
        _w(
            [
                {
                    "cand_key": k,
                    "por_municipio_json": _dump_map(d.get("por_municipio", {})),
                    "por_puesto_json": _dump_map(d.get("por_puesto", {})),
                }
                for k, d in heavy.get("candidatos_geo", {}).items()
            ],
            ["cand_key", "por_municipio_json", "por_puesto_json"],
            target_dir / _LAZY_FILES["candidatos_geo"],
        )

        # ── Candidatos MESA (lazy) ──
        _w(
            [
                {"cand_key": k, "por_mesa_json": _dump_map(d)}
                for k, d in heavy.get("candidatos_mesa", {}).items()
            ],
            ["cand_key", "por_mesa_json"],
            target_dir / _LAZY_FILES["candidatos_mesa"],
        )

        # ── Partidos LITE ──
        _w(
            [
                {
                    "cod_partido": k,
                    "votos_total": int(d["votos_total"]),
                    "por_depto_json": _dump_map(d["por_depto"]),
                    "circunscripcion": str(d["circunscripcion"]),
                }
                for k, d in mmv.get("partidos", {}).items()
            ],
            ["cod_partido", "votos_total", "por_depto_json", "circunscripcion"],
            target_dir / _CACHE_FILES["partidos"],
        )

        # ── Municipios ──
        _w(
            [
                {
                    "muni_key": k,
                    "mesas_json": _dump_list(d.get("mesas", [])),
                    "votos_validos": int(d["votos_validos"]),
                    "votos_blanco": int(d["votos_blanco"]),
                    "votos_nulo": int(d["votos_nulo"]),
                    "votos_no_marcado": int(d["votos_no_marcado"]),
                    "cod_depto": str(d["cod_depto"]),
                    "cod_muni": str(d["cod_muni"]),
                }
                for k, d in mmv.get("municipios", {}).items()
            ],
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

        # ── Deptos ──
        _w(
            [
                {
                    "cod_depto": k,
                    "municipios_json": _dump_list(d.get("municipios", [])),
                    "mesas_json": _dump_list(d.get("mesas", [])),
                    "votos_validos": int(d["votos_validos"]),
                    "votos_blanco": int(d["votos_blanco"]),
                    "votos_nulo": int(d["votos_nulo"]),
                    "votos_no_marcado": int(d["votos_no_marcado"]),
                }
                for k, d in mmv.get("deptos", {}).items()
            ],
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

        # ── Stats circ ──
        _w(
            [
                {
                    "circ": str(k),
                    "votos_total": int(d["votos_total"]),
                    "votos_validos_candidatos": int(d["votos_validos_candidatos"]),
                    "votos_lista": int(d["votos_lista"]),
                    "votos_validos_total": int(d["votos_validos_total"]),
                    "votos_blanco": int(d["votos_blanco"]),
                    "votos_nulo": int(d["votos_nulo"]),
                    "votos_no_marcado": int(d["votos_no_marcado"]),
                }
                for k, d in mmv.get("stats_por_circ", {}).items()
            ],
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

        # ── Totales circ LITE (just circ keys) ──
        _w(
            [{"circ": str(k)} for k in mmv.get("totales_validos_por_circ", {}).keys()],
            ["circ"],
            target_dir / _CACHE_FILES["totales_circ"],
        )

        # ── Totales circ GEO (lazy) ──
        _w(
            [
                {
                    "circ": str(k),
                    "por_municipio_json": _dump_map(d.get("por_municipio", {})),
                    "por_puesto_json": _dump_map(d.get("por_puesto", {})),
                }
                for k, d in heavy.get("totales_circ_geo", {}).items()
            ],
            ["circ", "por_municipio_json", "por_puesto_json"],
            target_dir / _LAZY_FILES["totales_circ_geo"],
        )

        # ── Totales circ MESA (lazy) ──
        _w(
            [
                {"circ": str(k), "por_mesa_json": _dump_map(d)}
                for k, d in heavy.get("totales_circ_mesa", {}).items()
            ],
            ["circ", "por_mesa_json"],
            target_dir / _LAZY_FILES["totales_circ_mesa"],
        )

        # ── Partidos circ LITE (solo por_depto) ──
        pc_rows = []
        for circ, pmap in mmv.get("partidos_por_circ", {}).items():
            for cod, d in pmap.items():
                pc_rows.append(
                    {
                        "circ": str(circ),
                        "cod_partido": str(cod),
                        "votos_lista": int(d["votos_lista"]),
                        "votos_candidatos": int(d["votos_candidatos"]),
                        "votos_validos_total": int(d["votos_validos_total"]),
                        "por_depto_json": _dump_map(
                            d.get("por_depto_validos_total", {})
                        ),
                    }
                )
        _w(
            pc_rows,
            [
                "circ",
                "cod_partido",
                "votos_lista",
                "votos_candidatos",
                "votos_validos_total",
                "por_depto_json",
            ],
            target_dir / _CACHE_FILES["partidos_circ"],
        )

        # ── Partidos circ GEO (lazy) ──
        _w(
            [
                {
                    "circ": str(circ),
                    "cod_partido": str(cod),
                    "por_municipio_json": _dump_map(d.get("por_municipio", {})),
                    "por_puesto_json": _dump_map(d.get("por_puesto", {})),
                }
                for (circ, cod), d in heavy.get("partidos_circ_geo", {}).items()
            ],
            ["circ", "cod_partido", "por_municipio_json", "por_puesto_json"],
            target_dir / _LAZY_FILES["partidos_circ_geo"],
        )

        # ── Partidos circ MESA (lazy) ──
        _w(
            [
                {
                    "circ": str(circ),
                    "cod_partido": str(cod),
                    "por_mesa_json": _dump_map(d),
                }
                for (circ, cod), d in heavy.get("partidos_circ_mesa", {}).items()
            ],
            ["circ", "cod_partido", "por_mesa_json"],
            target_dir / _LAZY_FILES["partidos_circ_mesa"],
        )

        # ── Meta ──
        pd.DataFrame(
            [
                {
                    **sig,
                    "mesas_count": int(mmv.get("mesas_count", 0)),
                    "total_lineas": int(mmv.get("total_lineas", 0)),
                }
            ]
        ).to_parquet(target_dir / _CACHE_FILES["meta"], index=False, compression="zstd")
    except Exception:
        return


# ──────────────────────────────────────────────
# PARSEO TXT
# ──────────────────────────────────────────────


def _procesar_mmv_txt(path: str) -> tuple[dict, dict]:
    """
    Parsea el TXT y retorna:
      - mmv: dict liviano (solo votos_total, por_depto, conteos)
      - heavy: dict pesado (por_municipio, por_puesto, por_mesa) para guardar aparte
    """
    # Lightweight accumulators (stay in memory)
    cand_lite = defaultdict(
        lambda: {
            "votos_total": 0,
            "por_depto": defaultdict(int),
            "n_municipios_set": set(),  # temp, converted to count
            "cod_partido": "",
            "cod_candidato": "",
            "circunscripcion": "",
        }
    )
    part_lite = defaultdict(
        lambda: {
            "votos_total": 0,
            "por_depto": defaultdict(int),
            "circunscripcion": "",
        }
    )

    # Heavy accumulators (saved to parquet then discarded)
    cand_muni = defaultdict(lambda: defaultdict(int))
    cand_puesto = defaultdict(lambda: defaultdict(int))
    cand_mesa = defaultdict(lambda: defaultdict(int))

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
            "votos_validos_total": 0,
            "votos_blanco": 0,
            "votos_nulo": 0,
            "votos_no_marcado": 0,
        }
    )

    totales_muni = defaultdict(lambda: defaultdict(int))
    totales_puesto = defaultdict(lambda: defaultdict(int))
    totales_mesa = defaultdict(lambda: defaultdict(int))

    pcirc_lite = defaultdict(
        lambda: defaultdict(
            lambda: {
                "votos_lista": 0,
                "votos_candidatos": 0,
                "votos_validos_total": 0,
                "por_depto_validos_total": defaultdict(int),
            }
        )
    )
    pcirc_muni = defaultdict(lambda: defaultdict(int))  # key: (circ, partido)
    pcirc_puesto = defaultdict(lambda: defaultdict(int))
    pcirc_mesa = defaultdict(lambda: defaultdict(int))

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
            pc_key = (circ, partido)

            stats_por_circ[circ]["votos_total"] += votos
            mesas_set.add(mesa_key)
            municipios[muni_key]["cod_depto"] = depto
            municipios[muni_key]["cod_muni"] = muni
            municipios[muni_key]["mesas"].add(mesa_key)
            deptos[depto]["municipios"].add(muni_key)
            deptos[depto]["mesas"].add(mesa_key)

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

            if candidato != COD_LISTA:
                municipios[muni_key]["votos_validos"] += votos
                deptos[depto]["votos_validos"] += votos
                stats_por_circ[circ]["votos_validos_candidatos"] += votos
                stats_por_circ[circ]["votos_validos_total"] += votos
                totales_muni[circ][muni_key] += votos
                totales_puesto[circ][puesto_key] += votos
                totales_mesa[circ][mesa_key] += votos
                pcirc_lite[circ][partido]["votos_candidatos"] += votos
                pcirc_lite[circ][partido]["votos_validos_total"] += votos
                pcirc_lite[circ][partido]["por_depto_validos_total"][depto] += votos
                pcirc_muni[pc_key][muni_key] += votos
                pcirc_puesto[pc_key][puesto_key] += votos
                pcirc_mesa[pc_key][mesa_key] += votos
            else:
                stats_por_circ[circ]["votos_lista"] += votos
                stats_por_circ[circ]["votos_validos_total"] += votos
                totales_muni[circ][muni_key] += votos
                totales_puesto[circ][puesto_key] += votos
                totales_mesa[circ][mesa_key] += votos
                pcirc_lite[circ][partido]["votos_lista"] += votos
                pcirc_lite[circ][partido]["votos_validos_total"] += votos
                pcirc_lite[circ][partido]["por_depto_validos_total"][depto] += votos
                pcirc_muni[pc_key][muni_key] += votos
                pcirc_puesto[pc_key][puesto_key] += votos
                pcirc_mesa[pc_key][mesa_key] += votos

            if candidato != COD_LISTA:
                cand_lite[cand_key]["votos_total"] += votos
                cand_lite[cand_key]["por_depto"][depto] += votos
                cand_lite[cand_key]["n_municipios_set"].add(muni_key)
                cand_lite[cand_key]["cod_partido"] = partido
                cand_lite[cand_key]["cod_candidato"] = candidato
                cand_lite[cand_key]["circunscripcion"] = circ
                cand_muni[cand_key][muni_key] += votos
                cand_puesto[cand_key][puesto_key] += votos
                cand_mesa[cand_key][mesa_key] += votos

            if candidato == COD_LISTA:
                part_lite[partido]["votos_total"] += votos
                part_lite[partido]["por_depto"][depto] += votos
                part_lite[partido]["circunscripcion"] = circ

    # Build output
    candidatos_out = {}
    for k, d in cand_lite.items():
        candidatos_out[k] = {
            "votos_total": d["votos_total"],
            "por_depto": dict(d["por_depto"]),
            "n_municipios": len(d["n_municipios_set"]),
            "cod_partido": d["cod_partido"],
            "cod_candidato": d["cod_candidato"],
            "circunscripcion": d["circunscripcion"],
        }

    partidos_out = {}
    for k, d in part_lite.items():
        partidos_out[k] = {
            "votos_total": d["votos_total"],
            "por_depto": dict(d["por_depto"]),
            "circunscripcion": d["circunscripcion"],
        }

    pcirc_out = {}
    for circ, pmap in pcirc_lite.items():
        pcirc_out[circ] = {}
        for cod, d in pmap.items():
            pcirc_out[circ][cod] = {
                "votos_lista": d["votos_lista"],
                "votos_candidatos": d["votos_candidatos"],
                "votos_validos_total": d["votos_validos_total"],
                "por_depto_validos_total": dict(d["por_depto_validos_total"]),
            }

    totales_out = {circ: {} for circ in totales_muni.keys()}

    mmv = {
        "candidatos": candidatos_out,
        "partidos": partidos_out,
        "municipios": dict(municipios),
        "deptos": dict(deptos),
        "stats_por_circ": dict(stats_por_circ),
        "partidos_por_circ": pcirc_out,
        "totales_validos_por_circ": totales_out,
        "mesas_count": len(mesas_set),
        "total_lineas": total_lineas,
    }

    heavy = {
        "candidatos_geo": {
            k: {"por_municipio": dict(cand_muni[k]), "por_puesto": dict(cand_puesto[k])}
            for k in cand_muni
        },
        "candidatos_mesa": {k: dict(v) for k, v in cand_mesa.items()},
        "totales_circ_geo": {
            circ: {
                "por_municipio": dict(totales_muni[circ]),
                "por_puesto": dict(totales_puesto[circ]),
            }
            for circ in totales_muni
        },
        "totales_circ_mesa": {circ: dict(v) for circ, v in totales_mesa.items()},
        "partidos_circ_geo": {
            k: {
                "por_municipio": dict(pcirc_muni[k]),
                "por_puesto": dict(pcirc_puesto[k]),
            }
            for k in pcirc_muni
        },
        "partidos_circ_mesa": {k: dict(v) for k, v in pcirc_mesa.items()},
    }

    return mmv, heavy


@st.cache_resource(show_spinner=False)
def procesar_mmv(path: str, cache_key: str = "") -> dict:
    """
    Lee MMV y retorna datos livianos en memoria.
    Los datos geográficos detallados se cargan bajo demanda.
    """
    _ = cache_key
    mmv_path = Path(path)
    from_cache = _cargar_desde_cache_parquet(mmv_path)
    if from_cache is not None:
        from_cache["cache_meta"] = {"load_source": "parquet", "cache_key": cache_key}
        return from_cache

    mmv, heavy = _procesar_mmv_txt(path)
    _guardar_cache_parquet(mmv, mmv_path, heavy)
    del heavy  # liberar memoria inmediatamente
    mmv["cache_meta"] = {"load_source": "txt", "cache_key": cache_key}
    return mmv
