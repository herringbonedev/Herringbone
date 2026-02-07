import anyio
from fastapi import HTTPException
from app.routers import orchestrator


def test_missing_rule_id_400():
    async def run():
        await orchestrator.process_detection(payload={}, service={})

    try:
        anyio.run(run)
        assert False
    except HTTPException as e:
        assert e.status_code == 400
