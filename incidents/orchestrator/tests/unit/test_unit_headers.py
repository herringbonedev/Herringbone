from app.routers import orchestrator


def test_service_auth_headers_cached(monkeypatch):
    monkeypatch.setattr(orchestrator, "_service_token_cache", "abc")
    h = orchestrator.service_auth_headers()
    assert h["Authorization"] == "Bearer abc"
