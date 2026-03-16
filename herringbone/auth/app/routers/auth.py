import os
import secrets
from datetime import datetime, UTC
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request
from bson import ObjectId

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import (
    require_scopes,
    get_identity,
    get_identity_optional,
    get_context,
)
from modules.audit import AuditLogger

from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_service_token,
)

from app.schemas import (
    RegisterRequest,
    LoginRequest,
    ServiceTokenRequest,
    ServiceRegisterRequest,
    ServiceScopeUpdateRequest,
    UserDeleteRequest,
    UserScopesUpdateRequest,
)

router = APIRouter(prefix="/herringbone/auth", tags=["auth"])

identity = Depends(get_identity)
admin = Depends(require_scopes("platform:admin"))


# -----------------------------
# Helpers
# -----------------------------

def generate_ingestion_key():
    return "hb_ingest_" + secrets.token_hex(16)


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
    )


def get_audit_logger():
    return AuditLogger(get_mongo())


def validate_admin_scope_assignment(requested_scopes, caller_scopes):
    if "*" in requested_scopes or "platform:admin" in requested_scopes:
        if "*" not in caller_scopes and "platform:admin" not in caller_scopes:
            raise HTTPException(
                status_code=403,
                detail="Only platform admins can assign platform admin scopes",
            )

    if "org:admin" in requested_scopes:
        if (
            "*" not in caller_scopes
            and "platform:admin" not in caller_scopes
            and "org:admin" not in caller_scopes
        ):
            raise HTTPException(
                status_code=403,
                detail="Only org admins or platform admins can assign org admin",
            )


def load_bootstrap_token() -> Optional[str]:
    path = os.environ.get("BOOTSTRAP_TOKEN_FILE")

    if path and os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()

    return os.environ.get("BOOTSTRAP_TOKEN")


def is_bootstrap_required(mongo: HerringboneMongoDatabase) -> bool:
    try:
        return len(mongo.find("users", {})) == 0
    except Exception:
        return True


# -----------------------------
# User APIs
# -----------------------------

@router.post("/register")
async def register_user(
    payload: RegisterRequest,
    request: Request,
    identity: dict | None = Depends(get_identity_optional),
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    bootstrap_required = is_bootstrap_required(mongo)

    if bootstrap_required:
        expected = load_bootstrap_token()
        provided = request.headers.get("x-bootstrap-token")

        if not expected or not provided or provided != expected:
            raise HTTPException(
                status_code=403,
                detail="Bootstrap token required for first user",
            )

    else:
        if identity is None:
            raise HTTPException(status_code=401, detail="Authentication required")

        caller_scopes = identity.get("scopes", [])

        if "*" not in caller_scopes and "platform:admin" not in caller_scopes:
            raise HTTPException(
                status_code=403,
                detail="Only platform admins can create users",
            )

    if mongo.find_one("users", {"email": payload.email}):
        raise HTTPException(status_code=400, detail="User already exists")

    user_count = len(mongo.find("users", {}))

    if user_count == 0:
        scopes = ["*"]
    else:
        requested_scopes = payload.scopes or [
            "logs:read",
            "search:query",
            "incidents:read",
        ]

        caller_scopes = identity.get("scopes", []) if identity else []

        validate_admin_scope_assignment(requested_scopes, caller_scopes)

        scopes = requested_scopes

    user_doc = {
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "scopes": scopes,
        "created_at": datetime.now(UTC),
    }

    user_id = mongo.insert_one("users", user_doc)

    return {
        "ok": True,
        "user_id": str(user_id),
        "scopes": scopes,
    }


@router.post("/login")
async def login_user(
    payload: LoginRequest,
    request: Request,
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    user = mongo.find_one("users", {"email": payload.email})

    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        user_id=str(user["_id"]),
        email=user["email"],
        scopes=user.get("scopes", []),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


# -----------------------------
# Ingestion Keys (Context Scoped)
# -----------------------------

@router.post("/ingestion-keys")
async def create_ingestion_key_api(
    context=Depends(get_context),
    identity=Depends(require_scopes("org:admin")),
):
    mongo = get_mongo()

    key = generate_ingestion_key()

    doc = {
        "key": key,
        "context_id": context["context_id"],
        "enabled": True,
        "created_at": datetime.now(UTC),
        "created_by": identity.get("email") or identity.get("service"),
    }

    mongo.insert_one("ingestion_keys", doc)

    return {"ok": True, "key": key}


@router.get("/ingestion-keys")
async def list_ingestion_keys(
    context=Depends(get_context),
    identity=Depends(require_scopes("org:admin")),
):
    mongo = get_mongo()

    keys = mongo.find(
        "ingestion_keys",
        {"context_id": context["context_id"]},
    )

    return {
        "count": len(keys),
        "keys": [
            {
                "id": str(k["_id"]),
                "enabled": k.get("enabled", True),
                "created_at": k.get("created_at"),
                "created_by": k.get("created_by"),
            }
            for k in keys
        ],
    }


@router.delete("/ingestion-keys/{key_id}")
async def revoke_ingestion_key(
    key_id: str,
    context=Depends(get_context),
    identity=Depends(require_scopes("org:admin")),
):
    mongo = get_mongo()

    mongo.update_one(
        "ingestion_keys",
        {
            "_id": ObjectId(key_id),
            "context_id": context["context_id"],
        },
        {"$set": {"enabled": False}},
    )

    return {"ok": True}


# -----------------------------
# Service APIs
# -----------------------------

@router.post("/services/register")
async def register_service(
    payload: ServiceRegisterRequest,
    request: Request,
    identity=admin,
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    if mongo.find_one("service_accounts", {"service_name": payload.service_name}):
        raise HTTPException(status_code=400, detail="Service already exists")

    svc_doc = {
        "service_name": payload.service_name,
        "service_id": payload.service_name,
        "scopes": payload.scopes,
        "enabled": True,
        "created_at": datetime.now(UTC),
    }

    svc_id = mongo.insert_one("service_accounts", svc_doc)

    return {
        "ok": True,
        "service_id": str(svc_id),
        "service_name": payload.service_name,
    }


# -----------------------------
# Health
# -----------------------------

@router.get("/healthz")
async def healthz():
    return {"ok": True, "service": "herringbone-auth"}


@router.get("/readyz")
async def db_check():
    db = get_mongo()
    client, mongo_db = db.open_mongo_connection()
    cols = mongo_db.list_collection_names()
    db.close_mongo_connection()

    return {
        "ok": True,
        "collections": cols,
    }