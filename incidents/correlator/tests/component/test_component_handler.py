import anyio
from fastapi import HTTPException
from starlette.requests import Request

from app.routers import correlator


def fake_request():
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/incidents/correlator/correlate",
        "headers": [],
        "client": ("testclient", 1234),
    }
    return Request(scope)


fake_identity = {
    "type": "service",
    "service": "test-correlator",
    "service_id": "svc-test",
    "scopes": ["incidents:correlate"],
    "context_id": "default",
}


def test_missing_rule_id_raises_400():
    async def run():
        await correlator.correlate(
            payload={},
            mongo=object(),
            request=fake_request(),
            identity=fake_identity,
        )

    try:
        anyio.run(run)
    except HTTPException as e:
        assert e.status_code == 400
    else:
        assert False, "Expected HTTPException"


def test_rule_only_create_when_no_candidates():
    class Mongo:
        def find_sorted(self, *args, **kwargs):
            return []

    async def run():
        return await correlator.correlate(
            payload={"rule_id": "rule-1"},
            mongo=Mongo(),
            request=fake_request(),
            identity=fake_identity,
        )

    result = anyio.run(run)

    assert result == {"action": "create"}