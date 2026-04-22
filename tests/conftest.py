# tests/conftest.py
import shutil
from pathlib import Path
import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_repo(tmp_path):
    def _make(name: str) -> Path:
        src = FIXTURE_DIR / name
        if not src.exists():
            raise FileNotFoundError(f"fixture {name} not found at {src}")
        dst = tmp_path / name
        shutil.copytree(src, dst)
        return dst
    return _make
