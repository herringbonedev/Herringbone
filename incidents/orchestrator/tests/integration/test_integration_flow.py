from app.routers import orchestrator


def test_attach_flow(client, monkeypatch):
    class FakeResp:
        def __init__(self, json, code=200):
            self._json = json
            self.status_code = code
        def json(self): return self._json
        def raise_for_status(self): pass

    def fake_post(url, json=None, headers=None, timeout=None):
        if "correlator" in url:
            return FakeResp({"action": "attach", "incident_id": "123"})
        return FakeResp({})

    monkeypatch.setattr(orchestrator.requests, "post", fake_post)

    r = client.post(
        "/incidents/orchestrator/process_detection",
        json={"rule_id": "r1", "event_ids": ["e1"], "detection_id": "d1"},
    )
    assert r.status_code == 200
    assert r.json()["result"] == "attached"
