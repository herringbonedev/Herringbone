from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, ValidationError


class Attach(BaseModel):
    action: Literal["attach"]
    incident_id: str


class Create(BaseModel):
    action: Literal["create"]
    correlation_identity: Optional[Dict[str, Any]] = None


def test_valid_responses():
    Create.model_validate({"action": "create"})
    Create.model_validate({"action": "create", "correlation_identity": {}})
    Attach.model_validate({"action": "attach", "incident_id": "abc123"})


def test_invalid_action_rejected():
    try:
        Attach.model_validate({"action": "nope"})
        assert False, "Expected ValidationError"
    except ValidationError:
        pass
