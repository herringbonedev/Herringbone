from bson import ObjectId
from app.routers import correlator


def test_http_attach(client, fake_mongo, monkeypatch):
    monkeypatch.setattr(
        correlator,
        "fetch_event",
        lambda eid: {"src": {"ip": "1.2.3.4"}},
    )

    fake_mongo.candidates = [{"_id": ObjectId()}]

    r = client.post(
        "/incidents/correlator/correlate",
        json={
            "rule_id": "rule-1",
            "correlate_on": ["src.ip"],
            "event_ids": ["evt-1"],
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "attach"
    assert "incident_id" in body


def test_http_missing_rule_id_400(client):
    r = client.post("/incidents/correlator/correlate", json={})
    assert r.status_code == 400
