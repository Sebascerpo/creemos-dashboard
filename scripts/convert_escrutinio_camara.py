#!/usr/bin/env python3
"""
Convierte CSV de escrutinio a formato MMV (38 caracteres) para CAMARA Antioquia.

Formato MMV (38 chars):
  cod_depto(2) cod_muni(3) zona(2) puesto(2) num_mesa(6)
  cod_jal(2) num_comunicado(4) circunscripcion(1)
  cod_partido(5) cod_candidato(3) votos(8)
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


COD_LISTA = "000"
COD_BLANCO = "996"
COD_NULO = "997"
COD_NO_MARC = "998"
COD_PARTIDO_ESPECIAL = "00000"


def pad(value: str | int, length: int) -> str:
    return str(value).zfill(length)


def load_partidos(path: Path) -> set[str]:
    codes: set[str] = set()
    if not path.exists():
        return codes
    for raw in path.read_text(encoding="latin-1").splitlines():
        line = raw.rstrip("\r\n")
        if len(line) < 5:
            continue
        codes.add(line[:5])
    return codes


def load_candidatos(path: Path) -> set[tuple[str, str]]:
    """
    Lee maestros CANDIDATOS.txt (formato fijo).
    Esperado:
      [0:3] corporacion, [3:4] circ, [4:6] depto, [12:16] partido4, [16:19] candidato3
    """
    out: set[tuple[str, str]] = set()
    if not path.exists():
        return out
    for raw in path.read_text(encoding="latin-1").splitlines():
        line = raw.rstrip("\r\n")
        if len(line) < 19:
            continue
        corp = line[0:3]
        circ = line[3:4]
        depto = line[4:6]
        if corp != "002" or circ != "1" or depto != "01":
            continue
        party4 = line[12:16]
        cod_partido = party4.zfill(5)
        cod_candidato = line[16:19]
        out.add((cod_partido, cod_candidato))
    return out


def build_line(
    depto: str,
    muni: str,
    zona: str,
    puesto: str,
    mesa: str,
    circ: str,
    cod_partido: str,
    cod_candidato: str,
    votos: int,
) -> str:
    return (
        pad(depto, 2)
        + pad(muni, 3)
        + pad(zona, 2)
        + pad(puesto, 2)
        + pad(mesa, 6)
        + "00"
        + "9999"
        + pad(circ, 1)
        + pad(cod_partido, 5)
        + pad(cod_candidato, 3)
        + pad(votos, 8)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="CSV escrutinio -> MMV 38 chars (Camara Antioquia)")
    parser.add_argument(
        "--input",
        default=str(ROOT / "escrutinio" / "Mmv20260310.csv"),
        help="Ruta CSV de escrutinio (delimiter ';')",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "escrutinio" / "MMV_ESCRUTINIO_CAMARA_ANTIOQUIA.txt"),
        help="Ruta TXT MMV de salida",
    )
    parser.add_argument(
        "--invalid",
        default=str(ROOT / "escrutinio" / "mmv_invalidas_camara_antioquia.csv"),
        help="Ruta CSV con filas invalidas",
    )
    parser.add_argument(
        "--include-zeros",
        action="store_true",
        help="Incluir filas con totalVotos=0",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    invalid_path = Path(args.invalid)

    partidos_validos = load_partidos(DATA_DIR / "PARTIDOS.txt")
    candidatos_validos = load_candidatos(DATA_DIR / "CANDIDATOS.txt")

    total = 0
    emitidos = 0
    invalidos = 0
    warn_partido = 0
    warn_candidato = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    invalid_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open(newline="", encoding="utf-8") as f_in, output_path.open("w", encoding="latin-1") as f_out, invalid_path.open(
        "w", newline="", encoding="utf-8"
    ) as f_bad:
        reader = csv.DictReader(f_in, delimiter=";")
        bad_writer = csv.DictWriter(f_bad, fieldnames=["motivo", *reader.fieldnames])
        bad_writer.writeheader()

        for row in reader:
            total += 1
            if row.get("corporacionCodigo") != "002":
                continue
            if row.get("circunscripcionCodigo") != "1":
                continue
            if row.get("departamentoCodigo") != "01":
                continue

            try:
                votos = int(row.get("totalVotos") or 0)
            except ValueError:
                votos = 0

            if votos == 0 and not args.include_zeros:
                continue

            depto = row.get("departamentoCodigo", "").strip()
            muni = row.get("municipioCodigo", "").strip()
            zona = row.get("zonaCodigo", "").strip()
            puesto = row.get("puestoCodigo", "").strip()
            mesa = row.get("mesa", "").strip()
            circ = row.get("circunscripcionCodigo", "").strip()
            cod_partido = row.get("partidoCodigo", "").strip()
            cand_raw = row.get("candidatoCodigo", "").strip()

            if not (depto and muni and zona and puesto and mesa and circ and cod_partido and cand_raw):
                invalidos += 1
                bad_writer.writerow({"motivo": "campos_incompletos", **row})
                continue

            # Candidato en CSV puede venir con 5 digitos -> MMV usa 3
            cod_candidato = pad(cand_raw, 5)[-3:]

            # Alertas suaves (no excluyen)
            if cod_partido != COD_PARTIDO_ESPECIAL and cod_partido not in partidos_validos:
                warn_partido += 1
            is_especial = cod_candidato in {COD_LISTA, COD_BLANCO, COD_NULO, COD_NO_MARC}
            if not is_especial:
                if (pad(cod_partido, 5), pad(cod_candidato, 3)) not in candidatos_validos:
                    warn_candidato += 1

            line = build_line(depto, muni, zona, puesto, mesa, circ, cod_partido, cod_candidato, votos)
            if len(line) != 38:
                invalidos += 1
                bad_writer.writerow({"motivo": "longitud_invalida", **row})
                continue

            f_out.write(line + "\n")
            emitidos += 1

    print(f"Total filas CSV: {total}")
    print(f"Filas emitidas: {emitidos}")
    print(f"Filas invalidas: {invalidos}")
    print(f"Alertas partido no maestro: {warn_partido}")
    print(f"Alertas candidato no maestro: {warn_candidato}")
    print(f"Salida: {output_path}")
    print(f"Invalidas: {invalid_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
