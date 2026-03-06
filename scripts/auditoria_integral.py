#!/usr/bin/env python3
"""
Auditoria integral de datos electorales (consola).

Objetivo:
- Contar partidos y candidatos de Senado (catalogo CANDIDATOS).
- Auditar TODOS los votos del MMV sin filtros (global).
- Explicar de donde salen los ~16M de votos validos de candidatos.
- Validar coherencia contra el parser de la app (core/parser.py).

Basado en layout fijo de `data/Estructuras Basicas.pdf`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MMV_CANDIDATE_FILES = [
    "PPP_MMV_DD_9999_test.txt",
    "PPP_MMV_DD_9999.txt",
]


def resolver_mmv_path() -> Path:
    for fname in MMV_CANDIDATE_FILES:
        p = DATA_DIR / fname
        if p.exists():
            return p
    return DATA_DIR / MMV_CANDIDATE_FILES[0]


MMV_PATH = resolver_mmv_path()
PARTIDOS_PATH = DATA_DIR / "PARTIDOS.txt"
CANDIDATOS_PATH = DATA_DIR / "CANDIDATOS.txt"
CORPORACION_PATH = DATA_DIR / "CORPORACION.txt"
CIRC_PATH = DATA_DIR / "CIRCUNSCRIPCION.txt"

COD_LISTA = "000"
COD_BLANCO = "996"
COD_NULO = "997"
COD_NO_MARC = "998"
CODS_ESPECIALES = {COD_LISTA, COD_BLANCO, COD_NULO, COD_NO_MARC}

# Regla de negocio vigente en la app:
SENADO_CORP = "001"
SENADO_CIRC = "0"


@dataclass
class MMVStats:
    total_lineas_no_vacias: int = 0
    lineas_parseables: int = 0
    lineas_invalidas: int = 0
    total_votos_todos: int = 0
    total_votos_candidatos_validos: int = 0
    total_votos_lista: int = 0
    total_votos_blanco: int = 0
    total_votos_nulo: int = 0
    total_votos_no_marcado: int = 0


def fmt(num: int) -> str:
    return f"{num:,}".replace(",", ".")


def title(txt: str) -> None:
    print("\n" + "=" * 96)
    print(txt)
    print("=" * 96)


def parse_simple_catalog(path: Path, code_len: int, desc_len: int | None = None) -> dict[str, str]:
    out: dict[str, str] = {}
    with path.open("r", encoding="latin-1") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if len(line) < code_len:
                continue
            code = line[:code_len].strip()
            if desc_len is None:
                desc = line[code_len:].strip()
            else:
                desc = line[code_len:code_len + desc_len].strip()
            if code:
                out[code] = desc
    return out


def parse_candidatos(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="latin-1") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if len(line) < 20:
                continue
            row = {
                "corporacion": line[0:3].strip(),
                "circunscripcion": line[3:4].strip(),
                "cod_depto": line[4:6].strip(),
                "cod_muni": line[6:9].strip(),
                "cod_comuna": line[9:11].strip(),
                "cod_partido": line[11:16].strip(),
                "cod_candidato": line[16:19].strip(),
                "preferente_tipo": line[19:20].strip(),
                "nombre": line[20:70].strip(),
                "apellido": line[70:120].strip() if len(line) >= 120 else "",
                "cedula": line[120:135].strip() if len(line) >= 135 else "",
                "genero": line[135:136].strip() if len(line) >= 136 else "",
                "sorteo": line[136:138].strip() if len(line) >= 138 else "",
            }
            row["cand_key"] = f"{row['cod_partido']}_{row['cod_candidato']}"
            row["nombre_completo"] = f"{row['nombre']} {row['apellido']}".strip()
            rows.append(row)
    return rows


def safe_int(txt: str) -> int:
    txt = txt.strip()
    return int(txt) if txt.isdigit() else 0


def parse_mmv(path: Path) -> tuple[MMVStats, dict[str, Counter], set[str]]:
    stats = MMVStats()
    acc: dict[str, Counter] = {
        "rows_by_circ": Counter(),
        "votes_by_circ": Counter(),
        "rows_by_party": Counter(),
        "votes_by_party_all": Counter(),
        "votes_by_party_valid": Counter(),
        "votes_by_party_lista": Counter(),
        "votes_by_party_blanco": Counter(),
        "votes_by_party_nulo": Counter(),
        "votes_by_party_no_marc": Counter(),
        "votes_valid_by_circ": Counter(),
        "votes_total_by_circ": Counter(),
        "top_candidate_key_votes": Counter(),
        "votes_by_circ_party": Counter(),
    }
    mesas_set: set[str] = set()

    with path.open("r", encoding="latin-1") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if not line.strip():
                continue

            stats.total_lineas_no_vacias += 1
            if len(line) < 38:
                stats.lineas_invalidas += 1
                continue

            stats.lineas_parseables += 1

            cod_depto = line[0:2]
            cod_muni = line[2:5]
            zona = line[5:7]
            puesto = line[7:9]
            num_mesa = line[9:15]
            circ = line[21:22].strip()
            cod_partido = line[22:27].strip()
            cod_candidato = line[27:30].strip()
            votos = safe_int(line[30:38])

            mesa_key = f"{cod_depto}_{cod_muni}_{zona}_{puesto}_{num_mesa}"
            mesas_set.add(mesa_key)

            stats.total_votos_todos += votos
            acc["rows_by_circ"][circ] += 1
            acc["votes_by_circ"][circ] += votos
            acc["rows_by_party"][cod_partido] += 1
            acc["votes_by_party_all"][cod_partido] += votos
            acc["votes_by_circ_party"][f"{circ}|{cod_partido}"] += votos
            acc["votes_total_by_circ"][circ] += votos

            if cod_candidato == COD_LISTA:
                stats.total_votos_lista += votos
                acc["votes_by_party_lista"][cod_partido] += votos
                continue
            if cod_candidato == COD_BLANCO:
                stats.total_votos_blanco += votos
                acc["votes_by_party_blanco"][cod_partido] += votos
                continue
            if cod_candidato == COD_NULO:
                stats.total_votos_nulo += votos
                acc["votes_by_party_nulo"][cod_partido] += votos
                continue
            if cod_candidato == COD_NO_MARC:
                stats.total_votos_no_marcado += votos
                acc["votes_by_party_no_marc"][cod_partido] += votos
                continue

            # Voto valido a candidato individual
            stats.total_votos_candidatos_validos += votos
            acc["votes_by_party_valid"][cod_partido] += votos
            acc["votes_valid_by_circ"][circ] += votos
            acc["top_candidate_key_votes"][f"{cod_partido}_{cod_candidato}"] += votos

    return stats, acc, mesas_set


def print_top_parties(
    counter: Counter,
    partidos: dict[str, str],
    top_n: int = 20,
    heading: str = "TOP PARTIDOS",
) -> None:
    print(f"\n{heading}")
    print("-" * 96)
    print(f"{'#':>2}  {'COD':<5}  {'VOTOS':>12}  {'PARTIDO'}")
    for i, (cod, votos) in enumerate(counter.most_common(top_n), start=1):
        print(f"{i:>2}  {cod:<5}  {fmt(votos):>12}  {partidos.get(cod, '[SIN CATALOGO]')}")


def print_counter(counter: Counter, mapping: dict[str, str], heading: str) -> None:
    print(f"\n{heading}")
    print("-" * 96)
    print(f"{'COD':<4}  {'VOTOS':>12}  {'DESCRIPCION'}")
    for cod, votos in counter.most_common():
        print(f"{cod:<4}  {fmt(votos):>12}  {mapping.get(cod, '[SIN CATALOGO]')}")


def validate_against_app_parser(stats: MMVStats, mesas_set: set[str]) -> None:
    title("VALIDACION CONTRA core/parser.py")
    try:
        from core.parser import procesar_mmv
    except Exception as exc:
        print(f"No se pudo importar core.parser: {exc}")
        return

    parsed = procesar_mmv(str(MMV_PATH))

    app_valid = sum(d["votos_validos"] for d in parsed["municipios"].values())
    app_blanco = sum(d["votos_blanco"] for d in parsed["municipios"].values())
    app_nulo = sum(d["votos_nulo"] for d in parsed["municipios"].values())
    app_no_marc = sum(d["votos_no_marcado"] for d in parsed["municipios"].values())
    app_lista = sum(d["votos_total"] for d in parsed["partidos"].values())

    checks = [
        (
            "Votos validos candidatos",
            stats.total_votos_candidatos_validos,
            app_valid,
        ),
        ("Votos blanco", stats.total_votos_blanco, app_blanco),
        ("Votos nulo", stats.total_votos_nulo, app_nulo),
        ("Votos no marcado", stats.total_votos_no_marcado, app_no_marc),
        ("Votos lista (cand 000)", stats.total_votos_lista, app_lista),
        ("Mesas unicas", len(mesas_set), parsed.get("mesas_count", -1)),
    ]

    ok_all = True
    for label, expected, got in checks:
        ok = expected == got
        ok_all = ok_all and ok
        status = "OK" if ok else "ERROR"
        print(f"[{status}] {label:<28} -> script={fmt(expected)} | app={fmt(got)}")

    print("\nResultado global:", "CONSISTENTE" if ok_all else "INCONSISTENCIAS DETECTADAS")


def main() -> None:
    title("AUDITORIA INTEGRAL DE IMPLEMENTACION")
    print(f"Proyecto : {PROJECT_ROOT}")
    print(f"Data dir : {DATA_DIR}")

    required = [MMV_PATH, PARTIDOS_PATH, CANDIDATOS_PATH, CORPORACION_PATH, CIRC_PATH]
    missing = [p for p in required if not p.exists()]
    if missing:
        print("\nFALTAN ARCHIVOS:")
        for p in missing:
            print(f"- {p}")
        raise SystemExit(1)

    partidos = parse_simple_catalog(PARTIDOS_PATH, 5, 200)
    corporaciones = parse_simple_catalog(CORPORACION_PATH, 3, 200)
    circ_map = parse_simple_catalog(CIRC_PATH, 1)
    candidatos_rows = parse_candidatos(CANDIDATOS_PATH)

    title("CATALOGOS (SEGUN ESTRUCTURAS BASICAS)")
    print(f"Partidos catalogo total            : {fmt(len(partidos))}")
    print(f"Candidatos catalogo total (filas)  : {fmt(len(candidatos_rows))}")

    sen_rows = [
        r for r in candidatos_rows
        if r["corporacion"] == SENADO_CORP and r["circunscripcion"] == SENADO_CIRC
    ]
    sen_parties = {r["cod_partido"] for r in sen_rows}
    sen_real_candidates = [r for r in sen_rows if r["cod_candidato"] != COD_LISTA]
    sen_list_headers = [r for r in sen_rows if r["cod_candidato"] == COD_LISTA]

    print("\n[Senado segun regla app: corporacion=001, circ=0]")
    print(f"Partidos unicos Senado             : {fmt(len(sen_parties))}")
    print(f"Candidatos reales Senado           : {fmt(len(sen_real_candidates))}")
    print(f"Cabeceras de lista Senado (000)    : {fmt(len(sen_list_headers))}")

    corp_counts = Counter(r["corporacion"] for r in candidatos_rows)
    print("\nCandidatos por corporacion (catalogo CANDIDATOS):")
    for corp, cnt in sorted(corp_counts.items(), key=lambda x: x[0]):
        print(f"- {corp}: {fmt(cnt)}  ({corporaciones.get(corp, '[SIN CATALOGO]')})")

    stats, acc, mesas_set = parse_mmv(MMV_PATH)

    title("MMV GLOBAL (SIN FILTROS)")
    print(f"Lineas no vacias                   : {fmt(stats.total_lineas_no_vacias)}")
    print(f"Lineas parseables (len>=38)        : {fmt(stats.lineas_parseables)}")
    print(f"Lineas invalidas                   : {fmt(stats.lineas_invalidas)}")
    print(f"Mesas unicas detectadas            : {fmt(len(mesas_set))}")

    print("\n[Totales de votos MMV]")
    print(f"Votos totales (todos)              : {fmt(stats.total_votos_todos)}")
    print(f"Votos validos candidatos           : {fmt(stats.total_votos_candidatos_validos)}")
    print(f"Votos lista (cand=000)             : {fmt(stats.total_votos_lista)}")
    print(f"Votos blanco (996)                 : {fmt(stats.total_votos_blanco)}")
    print(f"Votos nulo (997)                   : {fmt(stats.total_votos_nulo)}")
    print(f"Votos no marcado (998)             : {fmt(stats.total_votos_no_marcado)}")

    recomposed = (
        stats.total_votos_candidatos_validos
        + stats.total_votos_lista
        + stats.total_votos_blanco
        + stats.total_votos_nulo
        + stats.total_votos_no_marcado
    )
    print(f"Chequeo suma componentes           : {fmt(recomposed)}")
    print(f"Coincide con total MMV             : {'SI' if recomposed == stats.total_votos_todos else 'NO'}")

    title("DE DONDE SALEN LOS ~16M VOTOS")
    print(
        "En la app, ese numero corresponde a 'votos validos de candidatos'\n"
        "(excluye lista 000, blanco 996, nulo 997 y no marcado 998)."
    )
    print(f"Total exacto en este corte         : {fmt(stats.total_votos_candidatos_validos)}")

    print_counter(acc["votes_valid_by_circ"], circ_map, "Desglose de los 16M por circunscripcion (solo votos validos candidatos)")

    # Totales por partido: separado y combinado para entender composicion real.
    total_valid_plus_lista_by_party = Counter()
    for cod, votos in acc["votes_by_party_valid"].items():
        total_valid_plus_lista_by_party[cod] += votos
    for cod, votos in acc["votes_by_party_lista"].items():
        total_valid_plus_lista_by_party[cod] += votos

    print_top_parties(
        acc["votes_by_party_valid"],
        partidos,
        top_n=20,
        heading="TOP 20 PARTIDOS POR VOTOS VALIDOS DE CANDIDATOS (los ~16M)",
    )

    print_top_parties(
        total_valid_plus_lista_by_party,
        partidos,
        top_n=20,
        heading="TOP 20 PARTIDOS POR VOTOS VALIDOS + LISTA",
    )

    print("\nTOP 10 Circunscripcion + Partido por votos totales (todas las clases de voto)")
    print("-" * 96)
    print(f"{'#':>2}  {'CIRC':<4}  {'PART':<5}  {'VOTOS':>12}  {'CIRC_DESC':<20}  PARTIDO")
    for i, (k, votos) in enumerate(acc["votes_by_circ_party"].most_common(10), start=1):
        circ, cod = k.split("|", 1)
        print(
            f"{i:>2}  {circ:<4}  {cod:<5}  {fmt(votos):>12}  "
            f"{circ_map.get(circ, '[SIN CATALOGO]'):<20}  {partidos.get(cod, '[SIN CATALOGO]')}"
        )

    print("\nTOP 20 CANDIDATOS (cod_partido_cod_candidato) por votos validos")
    print("-" * 96)
    print(f"{'#':>2}  {'CAND_KEY':<10}  {'VOTOS':>12}")
    for i, (cand_key, votos) in enumerate(acc["top_candidate_key_votes"].most_common(20), start=1):
        print(f"{i:>2}  {cand_key:<10}  {fmt(votos):>12}")

    title("FORMULAS / CONSULTAS DE VALIDACION")
    print("Q1. votos_validos_candidatos = SUM(votos) WHERE cod_candidato NOT IN (000,996,997,998)")
    print("Q2. votos_lista              = SUM(votos) WHERE cod_candidato = 000")
    print("Q3. votos_blanco             = SUM(votos) WHERE cod_candidato = 996")
    print("Q4. votos_nulo               = SUM(votos) WHERE cod_candidato = 997")
    print("Q5. votos_no_marcado         = SUM(votos) WHERE cod_candidato = 998")
    print("Q6. votos_totales_mmv        = Q1 + Q2 + Q3 + Q4 + Q5")
    print("Q7. partidos_senado          = COUNT(DISTINCT cod_partido) en CANDIDATOS WHERE corporacion=001 AND circ=0")
    print("Q8. candidatos_senado        = COUNT(*) en CANDIDATOS WHERE corporacion=001 AND circ=0 AND cod_candidato<>000")

    validate_against_app_parser(stats, mesas_set)


if __name__ == "__main__":
    main()
