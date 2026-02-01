from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, UTC
import os
import json
from typing import Any, Dict, List, Optional
from bson import json_util
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.schema import CardSchema
from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.mix import service_or_user
from modules.auth.user import require_role


cardset_write_user = require_role(["admin", "analyst"])
cardset_admin_user = require_role(["admin"])
cardset_read_any = service_or_user("parser:cards:read")


router = APIRouter(
    prefix="/parser/cardset",
    tags=["cardset"],
)

validator = CardSchema()


class SelectorModel(BaseModel):
    type: str
    value: str


class CardModel(BaseModel):
    name: str
    selector: SelectorModel
    regex: Optional[List[Dict[str, str]]] = []
    jsonp: Optional[List[Dict[str, str]]] = []


class InsertCardResponse(BaseModel):
    ok: bool
    message: str


class PullCardsRequest(BaseModel):
    selector_type: str
    selector_value: str
    limit: Optional[int] = None


class PullCardsResponse(BaseModel):
    ok: bool
    count: int
    cards: List[Dict[str, Any]]


class DeleteCardsRequest(BaseModel):
    selector_type: str
    selector_value: str


class DeleteCardsResponse(BaseModel):
    ok: bool
    deleted: int


class UpdateCardResponse(BaseModel):
    ok: bool
    matched: int
    modified: int
    upserted_id: Optional[str] = None


def get_mongo() -> HerringboneMongoDatabase:
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", ""),
        password=os.environ.get("MONGO_PASS", ""),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
    )


def cards_collection():
    return os.environ.get("COLLECTION_NAME", "cards")


@router.post("/insert_card", response_model=InsertCardResponse)
async def insert_card(
    card: CardModel,
    mongo: HerringboneMongoDatabase = Depends(get_mongo),
):

    payload = card.model_dump()
    result = validator(payload)

    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {result.get('error')}")

    existing = mongo.find_one(cards_collection(), {"selector": payload.get("selector")})
    if existing:
        return {"ok": False, "message": "Card with this selector already exists."}

    payload["last_updated"] = datetime.now(UTC)

    try:
        mongo.insert_one(cards_collection(), payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insert failed: {e}")

    return {"ok": True, "message": "Valid card. Inserted into database."}


@router.post("/pull_cards", response_model=PullCardsResponse)
async def pull_cards(
    body: PullCardsRequest,
    auth=Depends(cardset_read_any),
    mongo: HerringboneMongoDatabase = Depends(get_mongo),
):

    sel_type = body.selector_type
    sel_value = body.selector_value
    limit = body.limit

    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        raise HTTPException(status_code=400, detail="Type and value must be strings")

    query = {
        "selector.type": sel_type,
        "selector.value": sel_value,
        "deleted": {"$ne": True},
    }

    try:
        docs = mongo.find(cards_collection(), query, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    return JSONResponse(
        content={
            "ok": True,
            "count": len(docs),
            "cards": json.loads(json_util.dumps(docs)),
        }
    )


@router.get("/pull_all_cards")
async def pull_all_cards(
    auth=Depends(cardset_read_any),
    mongo: HerringboneMongoDatabase = Depends(get_mongo),
):

    try:
        docs = mongo.find(cards_collection(), {"deleted": {"$ne": True}})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    return JSONResponse(
        content={
            "ok": True,
            "count": len(docs),
            "cards": json.loads(json_util.dumps(docs)),
        }
    )


@router.post("/delete_cards", response_model=DeleteCardsResponse)
async def delete_cards(
    body: DeleteCardsRequest,
    mongo: HerringboneMongoDatabase = Depends(get_mongo),
):

    sel_type = body.selector_type
    sel_value = body.selector_value

    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        raise HTTPException(status_code=400, detail="Type and value must be strings")

    try:
        res = mongo.upsert_one(
            cards_collection(),
            {"selector.type": sel_type, "selector.value": sel_value},
            {"deleted": True, "deleted_at": datetime.now(UTC)},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")

    return {"ok": True, "deleted": 1 if res else 0}


@router.post("/update_card", response_model=UpdateCardResponse)
async def update_card(
    new_card: CardModel,
    user=Depends(cardset_admin_user),
    mongo: HerringboneMongoDatabase = Depends(get_mongo),
):

    payload = new_card.model_dump()
    result = validator(payload)

    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {result.get('error')}")

    sel = payload.get("selector") or {}
    sel_type, sel_value = sel.get("type"), sel.get("value")

    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        raise HTTPException(status_code=400, detail="selector.type and selector.value must be strings")

    filter_query = {"selector.type": sel_type, "selector.value": sel_value}

    payload["last_updated"] = datetime.now(UTC)
    payload["deleted"] = False
    payload.pop("deleted_at", None)

    try:
        upserted_id = mongo.upsert_one(
            cards_collection(),
            filter_query,
            payload,
            clean_codec=False,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")

    return {
        "ok": True,
        "matched": 1,
        "modified": 1,
        "upserted_id": str(upserted_id) if upserted_id else None,
    }


@router.get("/readyz")
async def readyz(
    mongo: HerringboneMongoDatabase = Depends(get_mongo),
):
    try:
        mongo.find_one(cards_collection(), {})
        return {"ok": True}
    except Exception:
        return JSONResponse({"ok": False, "error": "mongo not ready"}, status_code=503)


@router.get("/livez")
async def livez():
    return {"ok": True}
