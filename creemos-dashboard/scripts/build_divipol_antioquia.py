#!/usr/bin/env python3
"""
Genera divipol_antioquia.json desde maestros/DIVIPOL.txt incluyendo
todas las filas del departamento 01 (Antioquia), sin excluir
registros con sufijos de circunscripción.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIVIPOL_TXT = ROOT / "maestros" / "DIVIPOL.txt"
OUT_JSON = ROOT / "src" / "assets" / "data" / "divipol_antioquia.json"


def _clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _extract_num_mesas(line: str) -> int:
    # Bloque esperado al final: 23 dígitos (1 + 8 + 8 + 6).
    # Ejemplo: "10000535800007844000039" -> mesas = 39
    tail = line[90:]
    m = re.search(r"(\d{23})", tail)
    if not m:
        return 0
    block = m.group(1)
    return int(block[-6:])


def main() -> None:
    if not DIVIPOL_TXT.exists():
        raise SystemExit(f"No existe: {DIVIPOL_TXT}")

    municipios: dict[str, dict] = {}
    depto_nombre = "ANTIOQUIA"

    for raw in DIVIPOL_TXT.read_text(encoding="latin-1").splitlines():
        line = raw.rstrip("\r\n")
        if len(line) < 91:
            continue

        cod_depto = line[0:2]
        if cod_depto != "01":
            continue

        cod_muni = line[2:5]
        zona = line[5:7]
        cod_puesto = line[7:9]
        nom_depto = _clean_spaces(line[9:20])
        nom_muni = _clean_spaces(line[20:50])
        nom_puesto = _clean_spaces(line[50:90])
        num_mesas = _extract_num_mesas(line)

        if nom_depto:
            depto_nombre = nom_depto

        if cod_muni not in municipios:
            municipios[cod_muni] = {"cod": cod_muni, "nombre": nom_muni, "puestos": []}

        municipios[cod_muni]["puestos"].append(
            {
                "zona": zona,
                "cod_puesto": cod_puesto,
                "nombre": nom_puesto,
                "num_mesas": num_mesas,
            }
        )

    # Orden estable por municipio/zona/puesto
    municipios_list = sorted(municipios.values(), key=lambda m: m["cod"])
    for m in municipios_list:
        m["puestos"] = sorted(m["puestos"], key=lambda p: (p["zona"], p["cod_puesto"]))

    payload = {"depto": {"cod": "01", "nombre": depto_nombre}, "municipios": municipios_list}

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    total_puestos = sum(len(m["puestos"]) for m in municipios_list)
    total_mesas = sum(int(p["num_mesas"] or 0) for m in municipios_list for p in m["puestos"])
    print(f"OK: {OUT_JSON}")
    print(f"Municipios: {len(municipios_list)}")
    print(f"Puestos: {total_puestos}")
    print(f"Mesas: {total_mesas}")


if __name__ == "__main__":
    main()

