from fastapi.testclient import TestClient
from app.main import app
from app.routers.extractor import extractor_call_scope

PARSE_PATH = "/parser/extractor/parse"


def override_extractor_scope():
    return {
        "service": "test",
        "scopes": ["extractor:call"],
    }


app.dependency_overrides[extractor_call_scope] = override_extractor_scope

client = TestClient(app)
