import sys
import importlib
from pathlib import Path


# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parents[3]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _alias_module(alias: str, target: str):
    """
    Register a module alias so `import alias` resolves to `target`.
    Safe to call multiple times.
    """
    if alias in sys.modules:
        return

    module = importlib.import_module(target)
    sys.modules[alias] = module


# Alias top-level module names used by legacy imports
_alias_module(
    "matchengine",
    "detectionengine.matcher.app.matchengine",
)