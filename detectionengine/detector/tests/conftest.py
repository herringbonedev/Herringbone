import pytest
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

@pytest.fixture(autouse=True)
def detector_env(monkeypatch):
    monkeypatch.setenv("MATCHER_API", "http://matcher.local/find_match")
    monkeypatch.setenv("ORCHESTRATOR_URL", "http://orchestrator.local")
