"""Cetak daftar titik seed (kode, lat, lon, tautan Google Maps).

Dipakai untuk mengisi backend/data/nama_titik_contoh.json secara manual.
Skrip ini TIDAK menulis ke basis data: titik seed dihitung ulang di SQLite
dalam memori dengan generator acak ber-seed yang sama seperti store._seed().

    python tools/daftar_titik_seed.py           # tabel
    python tools/daftar_titik_seed.py --json    # kerangka JSON kode -> nama
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import store  # noqa: E402


def titik_seed():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(store.SKEMA)
    store._seed(db)
    return db.execute("SELECT kode, nama, lat, lon FROM points ORDER BY kode").fetchall()


def main():
    rows = titik_seed()
    if "--json" in sys.argv:
        nama = store._muat_nama_contoh()
        print(json.dumps({r["kode"]: nama.get(r["kode"], "") for r in rows}, indent=2, ensure_ascii=False))
        return
    print(f"{'kode':<9} {'lat':>11} {'lon':>11}  tautan")
    for r in rows:
        print(
            f"{r['kode']:<9} {r['lat']:>11.6f} {r['lon']:>11.6f}  "
            f"https://www.google.com/maps?q={r['lat']},{r['lon']}"
        )
    print(f"\n{len(rows)} titik seed.")


if __name__ == "__main__":
    main()
