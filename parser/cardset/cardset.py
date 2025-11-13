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

app = FastAPI(title="CardSet Service (FastAPI)")
validator = CardSchema()

# ---------- Pydantic models ----------

class SelectorModel(BaseModel):
    type: str = Field(..., example="domain")
    value: str = Field(..., example="google.com")

class CardModel(BaseModel):
    selector: SelectorModel
    regex: Optional[List[Dict[str, str]]] = Field(None, example=[{"domain": "(?:[a-z0-9-]+\\.)*google\\.com"}])
    jsonp: Optional[List[Dict[str, str]]] = Field(None, example=[{"ip": "$.network.source.ip"}])

class InsertCardResponse(BaseModel):
    ok: bool
    message: str

class PullCardsRequest(BaseModel):
    selector_type: str = Field(..., example="domain", description="Key you previously used as the single body key, e.g. 'domain'")
    selector_value: str = Field(..., example="google.com", description="Value associated with that key")
    limit: Optional[int] = Field(None, ge=1, example=100)

class PullCardsResponse(BaseModel):
    ok: bool
    count: int
    cards: List[Dict[str, Any]]

class DeleteCardsRequest(BaseModel):
    selector_type: str = Field(..., example="domain")
    selector_value: str = Field(..., example="google.com")

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


@app.on_event("startup")
def on_startup():
    try:
        mongo = get_mongo_handler()
        mongo.open_mongo_connection()
        app.state.mongo = mongo
        print("[✓] Mongo handler initialized (FastAPI)")
    except Exception as e:
        print(f"[✗] Mongo connection init failed: {e}")
        app.state.mongo = None


@app.on_event("shutdown")
def on_shutdown():
    mongo = getattr(app.state, "mongo", None)
    if mongo and getattr(mongo, "client_connection", None):
        try:
            mongo.close_mongo_connection()
        except Exception:
            pass


@app.post("/parser/cardset/insert_card", response_model=InsertCardResponse)
async def insert_card(card: CardModel):
    print("Attempting to insert a new card...")

    if getattr(app.state, "mongo", None) is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    payload = card.model_dump()
    print(f"New card payload: {payload}")

    print("Validating payload...")
    result = validator(payload)
    print(result)
    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {result.get('error')}")

    payload["last_updated"] = datetime.utcnow()

    try:
        print("Inserting into MongoDB...")
        app.state.mongo.insert_log(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insert failed: {e}")

    return {"ok": True, "message": "Valid card. Inserted into database."}


@app.post("/parser/cardset/pull_cards", response_model=PullCardsResponse)
async def pull_cards(body: PullCardsRequest):
    if getattr(app.state, "mongo", None) is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    sel_type = body.selector_type
    sel_value = body.selector_value
    limit = body.limit

    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        raise HTTPException(status_code=400, detail="Type and value must be strings")

    try:
        docs = app.state.mongo.find_cards_by_selector(sel_type, sel_value, limit=int(limit or 0) or None)
        return JSONResponse(
            content={"ok": True, "count": len(docs), "cards": json.loads(json_util.dumps(docs))},
            status_code=200
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")
    

@app.get("/parser/cardset/pull_all_cards")
async def pull_all_cards():
    if getattr(app.state, "mongo", None) is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        # ✅ just call find_all_cards() — no ._db or .cards
        docs = app.state.mongo.find_all_cards()
        return JSONResponse(
            content={
                "ok": True,
                "count": len(docs),
                "cards": json.loads(json_util.dumps(docs))
            },
            status_code=200
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")



@app.post("/parser/cardset/delete_cards", response_model=DeleteCardsResponse)
async def delete_cards(body: DeleteCardsRequest):
    if getattr(app.state, "mongo", None) is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    sel_type = body.selector_type
    sel_value = body.selector_value

    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        raise HTTPException(status_code=400, detail="Type and value must be strings")

    try:
        res = app.state.mongo.delete_cards_by_selector(sel_type, sel_value)
        return {"ok": True, "deleted": res.get("deleted", 0)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")


@app.post("/parser/cardset/update_card", response_model=UpdateCardResponse)
async def update_card(new_card: CardModel):
    if getattr(app.state, "mongo", None) is None:
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
        res = app.state.mongo.update_log(filter_query, payload, clean_codec=False)
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
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


#
# Herringbone requires Liveness and Readiness probes for all services.
#
# The routes below contain the logic for livez and readyz
#


@app.get("/parser/cardset/readyz")
def readyz():
    if getattr(app.state, "mongo", None) is None:
        return JSONResponse({"ok": False, "error": "mongo not ready"}, status_code=503)
    return {"ok": True}


@app.get("/parser/cardset/livez")
def livez():
    return {"ok": True}
