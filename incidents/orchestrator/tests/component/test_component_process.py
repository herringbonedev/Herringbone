import anyio
from fastapi import HTTPException
from starlette.requests import Request

from app.routers import orchestrator


def fake_request():
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/incidents/orchestrator/process_detection",
        "headers": [],
        "client": ("testclient", 1234),
    }
    return Request(scope)


fake_identity = {
    "type": "service",
    "service": "test-orchestrator",
    "service_id": "svc-test",
    "scopes": ["incidents:orchestrate"],
    "context_id": "default",
}


def test_missing_rule_id_400():

    async def run():
        await orchestrator.process_detection(
            payload={},
            request=fake_request(),
            identity=fake_identity,
        )

    try:
        anyio.run(run)
    except HTTPException as e:
        assert e.status_code == 400
    else:
        assert False, "Expected HTTPException"