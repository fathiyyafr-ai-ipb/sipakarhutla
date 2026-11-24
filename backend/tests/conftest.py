import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import store  # noqa: E402


@pytest.fixture(scope="session")
def db_seed_template(tmp_path_factory):
    """Basis data seed dibuat sekali (inferensi model butuh beberapa detik), lalu disalin per tes."""
    path = tmp_path_factory.mktemp("template") / "seed.db"
    asli = store.DB_PATH
    store.DB_PATH = path
    try:
        store.init_db()
    finally:
        store.DB_PATH = asli
    # Pindahkan isi WAL ke file utama supaya cukup file .db yang disalin.
    db = sqlite3.connect(path)
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.close()
    return path


@pytest.fixture
def db_path(tmp_path, monkeypatch, db_seed_template):
    path = tmp_path / "sipakarhutla.db"
    shutil.copy(db_seed_template, path)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "_initialized", False)
    return path
