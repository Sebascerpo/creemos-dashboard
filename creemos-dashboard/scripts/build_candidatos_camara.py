#!/usr/bin/env python3
"""
Genera el catalogo de candidatos para Camara Antioquia a partir de maestros.

Entrada:
  - maestros/CANDIDATOS.txt
  - maestros/PARTIDOS.txt

Salida:
  - src/assets/data/candidatos_creemos.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAESTROS_DIR = ROOT / "maestros"
CANDIDATOS_TXT = MAESTROS_DIR / "CANDIDATOS.txt"
PARTIDOS_TXT = MAESTROS_DIR / "PARTIDOS.txt"
OUT_JSON = ROOT / "src/assets/data/candidatos_creemos.json"


def _clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _parse_partidos(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out

    for raw in path.read_text(encoding="latin-1").splitlines():
        line = raw.rstrip("\r\n")
        if len(line) < 5:
            continue
        cod = line[:5]
        nombre = _clean_spaces(line[5:])
        # En algunos maestros viene un flag final ("N").
        nombre = re.sub(r"\s+[A-Z]$", "", nombre).strip()
        if cod and nombre:
            out[cod] = nombre
    return out


def _parse_candidatos(path: Path, partidos_map: dict[str, str]) -> tuple[list[dict], dict[str, str]]:
    candidatos: list[dict] = []
    party_names = dict(partidos_map)

    for raw in path.read_text(encoding="latin-1").splitlines():
        line = raw.rstrip("\r\n")
        if len(line) < 20:
            continue

        # Formato fijo conocido de CANDIDATOS maestros:
        # [0:3] corporacion, [3:4] circ, [4:6] depto, [12:16] partido4, [16:19] candidato3
        corp = line[0:3]
        circ = line[3:4]
        depto = line[4:6]
        if corp != "002" or circ != "1" or depto != "01":
            continue

        party4 = line[12:16]
        cod_partido = party4.zfill(5)
        cod_candidato = line[16:19]
        es_lista = cod_candidato == "000"

        padded = line.ljust(140)
        nombre_raw = f"{padded[20:70]} {padded[70:120]}"
        nombre = _clean_spaces(nombre_raw)
        if not nombre:
            continue

        if es_lista:
            party_names[cod_partido] = nombre

        candidatos.append(
            {
                "cod_partido": cod_partido,
                "cod_candidato": cod_candidato,
                "nombre_completo": nombre,
                "nombre_partido": "",
                "es_lista": es_lista,
            }
        )

    for c in candidatos:
        c["nombre_partido"] = party_names.get(c["cod_partido"], c["cod_partido"])

    candidatos.sort(
        key=lambda c: (
            c["cod_partido"],
            0 if c["es_lista"] else 1,
            int(c["cod_candidato"]) if str(c["cod_candidato"]).isdigit() else 999,
            c["nombre_completo"],
        )
    )
    return candidatos, party_names


def main() -> None:
    partidos_map = _parse_partidos(PARTIDOS_TXT)
    candidatos, party_names = _parse_candidatos(CANDIDATOS_TXT, partidos_map)

    partidos = [
        {"cod_partido": cod, "nombre": nombre}
        for cod, nombre in sorted(party_names.items(), key=lambda x: x[0])
    ]

    payload = {
        "camara_antioquia": {
            "corporacion": "002",
            "circunscripcion": "1",
            "circunscripcion_nombre": "TERRITORIAL DEPARTAMENTAL",
            "cod_depto": "01",
            "partidos": partidos,
            "candidatos": candidatos,
        }
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {OUT_JSON}")
    print(f"Partidos: {len(partidos)}")
    print(f"Candidatos: {len(candidatos)}")


if __name__ == "__main__":
    main()

