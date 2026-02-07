import anyio
from fastapi import HTTPException
from app.routers import correlator


def test_missing_rule_id_raises_400():
    async def run():
        await correlator.correlate(payload={}, mongo=object(), service={})

    try:
        anyio.run(run)
        assert False, "Expected HTTPException"
    except HTTPException as e:
        assert e.status_code == 400


def test_rule_only_create_when_no_candidates():
    class Mongo:
        def find_sorted(self, *args, **kwargs):
            return []

    async def run():
        return await correlator.correlate(
            payload={"rule_id": "rule-1"},
            mongo=Mongo(),
            service={},
        )

    result = anyio.run(run)
    assert result == {"action": "create"}
