import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field

from modules.database.mongo_db import HerringboneMongoDatabase
from security import hash_password, verify_password, create_access_token, create_service_token
from bson import ObjectId


router = APIRouter(prefix="/herringbone/auth", tags=["auth"])


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
    )


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class ServiceTokenRequest(BaseModel):
    service: str
    scopes: list[str] = []


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register_user(payload: RegisterRequest):
    mongo = get_mongo()

    existing = mongo.find_one(
        collection="users",
        filter_query={"email": payload.email},
    )

    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user_count = len(
        mongo.find(collection="users", filter_query={})
    )

    role = "admin" if user_count == 0 else "analyst"

    user_doc = {
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "role": role,
        "created_at": datetime.utcnow(),
    }

    user_id = mongo.insert_one("users", user_doc)

    return {
        "ok": True,
        "user_id": str(user_id),
        "role": role,
    }


@router.post("/service-token")
async def create_service_token_api(
    payload: ServiceTokenRequest,
    user=Depends(require_admin),
):
    token = create_service_token(
        service_name=payload.service,
        scopes=payload.scopes,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/login")
async def login_user(payload: LoginRequest):
    mongo = get_mongo()

    user = mongo.find_one(
        collection="users",
        filter_query={"email": payload.email},
    )

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        user_id=str(user["_id"]),
        email=user["email"],
        role=user["role"],
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/users")
async def list_users():
    mongo = get_mongo()

    users = mongo.find(collection="users", filter_query={})

    result = []
    for u in users:
        result.append({
            "email": u.get("email"),
            "role": u.get("role"),
        })

    return {
        "count": len(result),
        "users": result,
    }
    

@router.get("/services")
async def list_services():
    mongo = get_mongo()

    services = mongo.find(collection="service_accounts", filter_query={})

    result = []
    for s in services:
        result.append({
            "id": str(s.get("_id")),
            "service_name": s.get("service_name"),
            "service_id": s.get("service_id"),
            "scopes": s.get("scopes", []),
            "enabled": s.get("enabled", True),
            "created_at": s.get("created_at"),
        })

    return {
        "count": len(result),
        "services": result,
    }


@router.get("/healthz")
async def healthz():
    return {"ok": True, "service": "herringbone-auth"}


@router.get("/readyz")
async def db_check():
    db = get_mongo()
    client, mongo_db = db.open_mongo_connection()
    cols = mongo_db.list_collection_names()
    db.close_mongo_connection()
    return {"ok": True, "collections": cols}

