import os
import sys

import pytest

RAKIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAKIT)

from inferensi import Penduga  # noqa: E402

FOLDER = os.environ.get("SIPAKARHUTLA_DATA", os.path.join(RAKIT, "data"))
MODEL = os.path.join(FOLDER, "model_indo.pt")


def pytest_configure(config):
    config.addinivalue_line("markers", "butuh_data: uji ini memerlukan model_indo.pt dan berkas K*_data.tif")


@pytest.fixture(scope="session")
def folder():
    if not os.path.exists(MODEL):
        pytest.skip(f"model_indo.pt tidak ada di {FOLDER} (atur SIPAKARHUTLA_DATA)")
    return FOLDER


@pytest.fixture(scope="session")
def penduga(folder):
    p = Penduga(MODEL, folder)
    if not p.kejadian:
        pytest.skip("Tidak ada berkas K*_data.tif di folder data")
    return p
