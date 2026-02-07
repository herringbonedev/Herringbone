from pydantic import BaseModel


class AttachResp(BaseModel):
    result: str
    incident_id: str


class CreateResp(BaseModel):
    result: str


def test_contract_shapes():
    AttachResp.model_validate({"result": "attached", "incident_id": "abc"})
    CreateResp.model_validate({"result": "created"})
