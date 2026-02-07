from typing import List, Dict, Any
from pydantic import BaseModel, ConfigDict, RootModel


class InsertResp(BaseModel):
    inserted: bool


class UpdateResp(BaseModel):
    updated: bool


class IncidentDoc(BaseModel):
    model_config = ConfigDict(extra="allow")


class IncidentListResp(RootModel[List[Dict[str, Any]]]):
    pass


def test_contract_insert_update_shapes():
    InsertResp.model_validate({"inserted": True})
    UpdateResp.model_validate({"updated": True})


def test_contract_incident_doc_allows_extra():
    IncidentDoc.model_validate(
        {
            "_id": {"$oid": "abc"},
            "title": "t",
            "priority": "low",
            "status": "open",
        }
    )


def test_contract_incident_list_shape():
    IncidentListResp.model_validate(
        [
            {"_id": {"$oid": "1"}, "title": "a"},
            {"_id": {"$oid": "2"}, "title": "b"},
        ]
    )
