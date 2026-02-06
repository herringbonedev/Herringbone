import sys
import importlib
from pathlib import Path

# Ensure repo root is on path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Alias top-level `matchengine` to the real module location
if "matchengine" not in sys.modules:
    sys.modules["matchengine"] = importlib.import_module(
        "detectionengine.matcher.app.matchengine"
    )
