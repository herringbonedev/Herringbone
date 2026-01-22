from fastapi import APIRouter, Depends, HTTPException, Request, Query
from datetime import datetime
import os
import json
from typing import Any, Dict, List, Optional
from bson import json_util
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from schema import CardSchema
from modules.database.mongo_db import HerringboneMongoDatabase

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


def get_mongo_handler() -> HerringboneMongoDatabase:
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "hbadmin"),
        password=os.environ.get("MONGO_PASS", "hbdevpw123"),
        database=os.environ.get("DB_NAME", "herringbone"),
        collection=os.environ.get("COLLECTION_NAME", "cards"),
        host=os.environ.get("MONGO_HOST", "127.0.0.1"),
        port=int(os.environ.get("MONGO_PORT", 27017))
    )


@router.post("/insert_card", response_model=InsertCardResponse)
async def insert_card(card: CardModel):
    print("]*] Attempting to insert a new card...")

    try:
        mongo = get_mongo_handler()
        mongo.open_mongo_connection()
    except Exception:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    payload = card.model_dump()
    print(f"[*] New card payload: {payload}")
    print("[*] Validating payload...")
    result = validator(payload)
    print(result)

    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {result.get('error')}")

    existing_card = mongo.find_one({"selector": payload.get("selector")})
    if existing_card:
        print(f"Card with selector {payload.get('selector')} already exists. Skipping insert.")
        return {"ok": False, "message": "Card with this selector already exists."}

    payload["last_updated"] = datetime.utcnow()

    try:
        print("Inserting into MongoDB...")
        mongo.insert_log(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insert failed: {e}")
    finally:
        try:
            mongo.close_mongo_connection()
        except Exception:
            pass

    return {"ok": True, "message": "Valid card. Inserted into database."}


@router.post("/pull_cards", response_model=PullCardsResponse)
async def pull_cards(body: PullCardsRequest):
    print(f"[*] Incoming pull card request: {str(body)}")
    try:
        mongo = get_mongo_handler()
        mongo.open_mongo_connection()
    except Exception:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    sel_type = body.selector_type
    sel_value = body.selector_value
    limit = body.limit

    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        raise HTTPException(status_code=400, detail="Type and value must be strings")

    try:
        docs = mongo.find_cards_by_selector(sel_type, sel_value, limit=int(limit or 0) or None)
        print(f"[*] Loaded docs: {str(docs)}")
        return JSONResponse(
            content={"ok": True, "count": len(docs), "cards": json.loads(json_util.dumps(docs))},
            status_code=200
        )
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")
    finally:
        try:
            mongo.close_mongo_connection()
        except Exception:
            pass
    

@router.get("/pull_all_cards")
async def pull_all_cards():
    try:
        mongo = get_mongo_handler()
        mongo.open_mongo_connection()
    except Exception:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        docs = mongo.find_all_cards()
        return JSONResponse(
            content={
                "ok": True,
                "count": len(docs),
                "cards": json.loads(json_util.dumps(docs))
            },
            status_code=200
        )
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")
    finally:
        try:
            mongo.close_mongo_connection()
        except Exception:
            pass


@router.post("/delete_cards", response_model=DeleteCardsResponse)
async def delete_cards(body: DeleteCardsRequest):
    try:
        mongo = get_mongo_handler()
        mongo.open_mongo_connection()
    except Exception:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    print(body)

    sel_type = body.selector_type
    sel_value = body.selector_value

    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        raise HTTPException(status_code=400, detail="Type and value must be strings")

    try:
        res = mongo.delete_cards_by_selector(sel_type, sel_value)
        return {"ok": True, "deleted": res.get("deleted", 0)}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")
    finally:
        try:
            mongo.close_mongo_connection()
        except Exception:
            pass


@router.post("/update_card", response_model=UpdateCardResponse)
async def update_card(new_card: CardModel):
    try:
        mongo = get_mongo_handler()
        mongo.open_mongo_connection()
    except Exception:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    payload = new_card.model_dump()
    result = validator(payload)

    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {result.get('error')}")

    sel = payload.get("selector") or {}
    sel_type, sel_value = sel.get("type"), sel.get("value")

    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        raise HTTPException(status_code=400, detail="selector.type and selector.value must be strings")

    filter_query = {"selector.type": sel_type, "selector.value": sel_value}
    payload["last_updated"] = datetime.utcnow()
    payload["deleted"] = False
    payload.pop("deleted_at", None)

    try:
        res = mongo.update_log(filter_query, payload, clean_codec=False)
        return JSONResponse(
            content={
                "ok": True,
                "matched": (res or {}).get("matched", 0),
                "modified": (res or {}).get("modified", 0),
                "upserted_id": str((res or {}).get("upserted_id")) if (res or {}).get("upserted_id") else None
            },
            status_code=200
        )
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    finally:
        try:
            mongo.close_mongo_connection()
        except Exception:
            pass


@router.get("/readyz")
async def readyz():
    try:
        mongo = get_mongo_handler()
        mongo.open_mongo_connection()
        return {"ok": True}
    except Exception:
        return JSONResponse({"ok": False, "error": "mongo not ready"}, status_code=503)
    finally:
        try:
            mongo.close_mongo_connection()
        except Exception:
            pass


@router.get("/livez")
async def livez():
    return {"ok": True}
