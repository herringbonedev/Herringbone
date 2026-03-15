from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, UTC
import os
import json
from typing import Any, Dict, List, Optional
from bson import json_util
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.schema import CardSchema
from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import require_scopes
from modules.audit.logger import AuditLogger

cardset_write = require_scopes("parser:cards:write")
cardset_read = require_scopes("parser:cards:read")

router = APIRouter(
    prefix="/parser/cardset",
    tags=["cardset"],
)

validator = CardSchema()
audit = AuditLogger()


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
    request: Request,
    identity=Depends(cardset_write),
    mongo: HerringboneMongoDatabase = Depends(get_mongo),
):

    payload = card.model_dump()

    payload["selector_type"] = payload["selector"]["type"]
    payload["selector_value"] = payload["selector"]["value"]

    result = validator(payload)

    if not result.get("valid"):
        audit.log(
            event="card_insert_failed",
            severity="WARNING",
            identity=identity,
            request=request,
            target=payload.get("name"),
            result="failure",
            metadata={"error": result.get("error")},
        )
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {result.get('error')}")

    existing = mongo.find_one(cards_collection(), {"selector": payload.get("selector")})
    if existing:
        audit.log(
            event="card_insert_duplicate",
            severity="WARNING",
            identity=identity,
            request=request,
            target=payload.get("name"),
            result="failure",
        )
        return {"ok": False, "message": "Card with this selector already exists."}

    payload["last_updated"] = datetime.now(UTC)

    try:
        mongo.insert_one(cards_collection(), payload)
    except Exception as e:
        audit.log(
            event="card_insert_failed",
            severity="ERROR",
            identity=identity,
            request=request,
            target=payload.get("name"),
            result="failure",
            metadata={"error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Insert failed: {e}")

    audit.log(
        event="card_inserted",
        severity="INFO",
        identity=identity,
        request=request,
        target=payload.get("name"),
        metadata={"selector": payload.get("selector")},
    )

    return {"ok": True, "message": "Valid card. Inserted into database."}


@router.post("/pull_cards", response_model=PullCardsResponse)
async def pull_cards(
    body: PullCardsRequest,
    request: Request,
    identity=Depends(cardset_read),
    mongo: HerringboneMongoDatabase = Depends(get_mongo),
):

    sel_type = body.selector_type
    sel_value = body.selector_value
    limit = body.limit

    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        audit.log(
            event="card_query_invalid_selector",
            severity="WARNING",
            identity=identity,
            request=request,
            result="failure",
        )
        raise HTTPException(status_code=400, detail="Type and value must be strings")

    query = {
        "selector.type": sel_type,
        "selector.value": sel_value,
        "deleted": {"$ne": True},
    }

    try:
        docs = mongo.find(cards_collection(), query, limit=limit)
    except Exception as e:
        audit.log(
            event="card_query_failed",
            severity="ERROR",
            identity=identity,
            request=request,
            result="failure",
            metadata={"error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    audit.log(
        event="card_query",
        severity="INFO",
        identity=identity,
        request=request,
        metadata={"selector_type": sel_type, "selector_value": sel_value, "count": len(docs)},
    )

    return JSONResponse(
        content={
            "ok": True,
            "count": len(docs),
            "cards": json.loads(json_util.dumps(docs)),
        }
    )


@router.get("/pull_all_cards")
async def pull_all_cards(
    request: Request,
    identity=Depends(cardset_read),
    mongo: HerringboneMongoDatabase = Depends(get_mongo),
):

    try:
        docs = mongo.find(cards_collection(), {"deleted": {"$ne": True}})
    except Exception as e:
        audit.log(
            event="card_query_all_failed",
            severity="ERROR",
            identity=identity,
            request=request,
            result="failure",
            metadata={"error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    audit.log(
        event="card_query_all",
        severity="INFO",
        identity=identity,
        request=request,
        metadata={"count": len(docs)},
    )

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
    request: Request,
    identity=Depends(cardset_write),
    mongo: HerringboneMongoDatabase = Depends(get_mongo),
):

    sel_type = body.selector_type
    sel_value = body.selector_value

    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        audit.log(
            event="card_delete_invalid_selector",
            severity="WARNING",
            identity=identity,
            request=request,
            result="failure",
        )
        raise HTTPException(status_code=400, detail="Type and value must be strings")

    try:
        res = mongo.upsert_one(
            cards_collection(),
            {"selector.type": sel_type, "selector.value": sel_value},
            {"deleted": True, "deleted_at": datetime.now(UTC)},
        )
    except Exception as e:
        audit.log(
            event="card_delete_failed",
            severity="ERROR",
            identity=identity,
            request=request,
            result="failure",
            metadata={"error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")

    audit.log(
        event="card_deleted",
        severity="INFO",
        identity=identity,
        request=request,
        metadata={"selector_type": sel_type, "selector_value": sel_value},
    )

    return {"ok": True, "deleted": 1 if res else 0}


@router.post("/update_card", response_model=UpdateCardResponse)
async def update_card(
    new_card: CardModel,
    request: Request,
    identity=Depends(cardset_write),
    mongo: HerringboneMongoDatabase = Depends(get_mongo),
):

    payload = new_card.model_dump()
    result = validator(payload)

    if not result.get("valid"):
        audit.log(
            event="card_update_failed",
            severity="WARNING",
            identity=identity,
            request=request,
            target=payload.get("name"),
            result="failure",
            metadata={"error": result.get("error")},
        )
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {result.get('error')}")

    sel = payload.get("selector") or {}
    sel_type, sel_value = sel.get("type"), sel.get("value")

    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        audit.log(
            event="card_update_invalid_selector",
            severity="WARNING",
            identity=identity,
            request=request,
            result="failure",
        )
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
        audit.log(
            event="card_update_failed",
            severity="ERROR",
            identity=identity,
            request=request,
            result="failure",
            metadata={"error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")

    audit.log(
        event="card_updated",
        severity="INFO",
        identity=identity,
        request=request,
        target=payload.get("name"),
        metadata={"selector": payload.get("selector")},
    )

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