from datetime import datetime
import os
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

@app.get("/healthz")
def healthz():
    if getattr(app.state, "mongo", None) is None:
        return JSONResponse({"ok": False, "error": "mongo not ready"}, status_code=503)
    return {"ok": True}

@app.post("/parser/cardset/insert_card")
async def insert_card(request: Request):
    if getattr(app.state, "mongo", None) is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    result = validator(payload)
    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {result.get('error')}")
    
    payload["last_updated"] = datetime.utcnow()

    try:
        app.state.mongo.insert_log(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insert failed: {e}")

    return {"ok": True, "message": "Valid card. Inserted into database."}
