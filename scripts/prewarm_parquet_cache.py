"""
Precalienta la caché Parquet del MMV para acelerar arranque en Streamlit.

Uso:
  python scripts/prewarm_parquet_cache.py
  python scripts/prewarm_parquet_cache.py --mmv data/PPP_MMV_DD_9999.txt
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.parser import procesar_mmv


def _resolver_default_mmv() -> Path:
    data_dir = Path("data")
    for name in ("PPP_MMV_DD_9999_test.txt", "PPP_MMV_DD_9999.txt"):
        p = data_dir / name
        if p.exists():
            return p
    return data_dir / "PPP_MMV_DD_9999.txt"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mmv", type=str, default=None, help="Ruta del archivo MMV TXT")
    args = parser.parse_args()

    mmv_path = Path(args.mmv) if args.mmv else _resolver_default_mmv()
    if not mmv_path.exists():
        raise SystemExit(f"No existe MMV: {mmv_path}")

    t0 = time.perf_counter()
    mmv = procesar_mmv(str(mmv_path))
    dt = time.perf_counter() - t0

    print("MMV procesado.")
    print(f"Archivo: {mmv_path}")
    print(f"Lineas: {mmv.get('total_lineas', 0):,}")
    print(f"Mesas : {mmv.get('mesas_count', 0):,}")
    print(f"Tiempo: {dt:.2f}s")
    print("Caché Parquet lista si no hubo errores.")


if __name__ == "__main__":
    main()
