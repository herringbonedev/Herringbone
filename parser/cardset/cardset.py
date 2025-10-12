from datetime import datetime
import os
from bson import json_util
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from schema import CardSchema
from modules.database.mongo_db import HerringboneMongoDatabase

app = FastAPI(title="CardSet Service (FastAPI)")
validator = CardSchema()

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


@app.post("/parser/cardset/insert_card")
async def insert_card(request: Request):

    print("Attempting to insert a new card...")

    if getattr(app.state, "mongo", None) is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        payload = await request.json()
        print(f"New card payload: {str(payload)}")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

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


@app.post("/parser/cardset/pull_cards")
async def pull_cards(request: Request):
    if getattr(app.state, "mongo", None) is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(payload, dict) or len(payload) != 1:
        raise HTTPException(status_code=400, detail='Body must be like {"domain":"google.com"}')

    (sel_type, sel_value) = next(iter(payload.items()))
    if not isinstance(sel_type, str) or not isinstance(sel_value, str):
        raise HTTPException(status_code=400, detail="Type and value must be strings")

    query = {"selector.type": sel_type, "selector.value": sel_value}

    try:
        mongo = app.state.mongo
        collection = mongo.client_connection[mongo.database][mongo.collection]
        docs = list(collection.find(query))

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

