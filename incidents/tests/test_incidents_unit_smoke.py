from fastapi import FastAPI
from starlette.testclient import TestClient
from bson import ObjectId

# Import routers
from incidentset.app.routers import incidentset
from correlator.app.routers import correlator
from orchestrator.app.routers import orchestrator


def build_test_app():
    app = FastAPI()

    # Register all Incidents-unit routers
    app.include_router(incidentset.router)
    app.include_router(correlator.router)
    app.include_router(orchestrator.router)

    # ---- IncidentSet overrides ----
    class FakeMongo:
        def insert_one(self, *a, **kw):
            pass

        def find(self, *a, **kw):
            return []

        def find_one(self, *a, **kw):
            return {"_id": ObjectId(), "title": "t"}

        def find_sorted(self, *a, **kw):
            # Correlator expects this
            return []

        def open_mongo_connection(self):
            class DB(dict):
                def __getitem__(self, k):
                    class C:
                        def update_one(self, *a, **kw):
                            class R:
                                raw_result = {"ok": 1}
                            return R()
                    return C()
            return object(), DB()

        def close_mongo_connection(self):
            pass

    app.dependency_overrides[incidentset.get_mongo] = lambda: FakeMongo()
    app.dependency_overrides[incidentset.incident_writer] = lambda: {"scope": "incidents:write"}
    app.dependency_overrides[incidentset.incident_reader] = lambda: {"scope": "incidents:read"}

    # ---- Correlator overrides ----
    app.dependency_overrides[correlator.get_mongo] = lambda: FakeMongo()
    app.dependency_overrides[correlator.correlate_required] = lambda: {"scope": "incidents:correlate"}

    # ---- Orchestrator overrides ----
    app.dependency_overrides[orchestrator.orchestrator_run] = (
        lambda: {"scope": "incidents:orchestrate"}
    )

    # Prevent filesystem token access
    orchestrator._service_token_cache = "test-token"

    # Stub downstream HTTP calls
    def fake_post(url, json=None, headers=None, timeout=None):
        class Resp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                if "correlator" in url:
                    return {"action": "create"}
                return {"inserted": True}
        return Resp()

    orchestrator.requests.post = fake_post
    correlator.requests.get = lambda *a, **kw: type("R", (), {"status_code": 200, "json": lambda: {}})()

    return app


def test_incidents_unit_smoke():
    """
    Smoke test for the entire Incidents unit:
    - incidentset
    - correlator
    - orchestrator
    """

    app = build_test_app()
    client = TestClient(app)

    # ---- IncidentSet ----
    r = client.post(
        "/incidents/incidentset/insert_incident",
        json={"title": "Smoke", "priority": "low"},
    )
    assert r.status_code == 200

    # ---- Correlator ----
    r = client.post(
        "/incidents/correlator/correlate",
        json={"rule_id": "r1"},
    )
    assert r.status_code == 200
    assert r.json()["action"] == "create"

    # ---- Orchestrator ----
    r = client.post(
        "/incidents/orchestrator/process_detection",
        json={
            "rule_id": "r1",
            "detection_id": "d1",
            "event_ids": ["e1"],
        },
    )
    assert r.status_code == 200
    assert r.json()["result"] == "created"
