import os
from datetime import datetime, UTC
from typing import Optional
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import (
    require_scopes,
    get_identity,
    get_context
)

from app.security import (
    generate_ingestion_key,
    hash_ingestion_key,
)

from modules.audit import AuditLogger

router = APIRouter(prefix="/herringbone/auth", tags=["ingestion"])

identity = Depends(get_identity)
admin = Depends(require_scopes("platform:admin"))


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


@router.get("/ingestion-keys")
async def list_ingestion_keys(
    request: Request,
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    require_scopes("orgs:keys:read")(context)
    mongo = get_mongo()

    if identity.get("type") != "user":
        audit.log(
            event="ingestion_key_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "non_user_identity"},
            request=request,
        )
        raise HTTPException(403, "user identity required")

    context_id = context.get("context_id")

    if not context_id or context_id == "default":
        audit.log(
            event="ingestion_key_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "org_context_required"},
            request=request,
        )
        raise HTTPException(403, "organization context required")

    keys = mongo.find(
        "ingestion_keys",
        {"context_id": context_id},
    )

    return {
        "count": len(keys),
        "keys": [
            {
                "id": str(k["_id"]),
                "enabled": k.get("enabled", True),
                "created_at": k.get("created_at").isoformat()
                if k.get("created_at")
                else None,
                "created_by": k.get("created_by"),
            }
            for k in keys
        ],
    }


@router.post("/ingestion-keys")
async def create_ingestion_key_api(
    request: Request,
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    require_scopes("orgs:keys:write")(context)
    mongo = get_mongo()

    if identity.get("type") != "user":
        audit.log(
            event="ingestion_key_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "non_user_identity"},
            request=request,
        )
        raise HTTPException(403, "user identity required")

    context_id = context.get("context_id")

    if not context_id or context_id == "default":
        audit.log(
            event="ingestion_key_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "org_context_required"},
            request=request,
        )
        raise HTTPException(403, "organization context required")

    raw_key = generate_ingestion_key()

    doc = {
        "key_hash": hash_ingestion_key(raw_key),
        "context_id": context_id,
        "enabled": True,
        "created_at": datetime.now(UTC),
        "created_by": identity.get("email"),
    }

    mongo.insert_one("ingestion_keys", doc, context_id=context_id)

    audit.log(
        event="ingestion_key_created",
        identity=identity,
        metadata={"context_id": context_id},
        request=request,
    )

    return {"ok": True, "key": raw_key}


@router.delete("/ingestion-keys/{key_id}")
async def revoke_ingestion_key(
    key_id: str,
    request: Request,
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    require_scopes("orgs:keys:write")(context)
    mongo = get_mongo()

    if identity.get("type") != "user":
        audit.log(
            event="ingestion_key_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "non_user_identity"},
            request=request,
        )
        raise HTTPException(403, "user identity required")

    context_id = context.get("context_id")

    if not context_id or context_id == "default":
        audit.log(
            event="ingestion_key_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "org_context_required"},
            request=request,
        )
        raise HTTPException(403, "organization context required")

    try:
        oid = ObjectId(key_id)
    except Exception:
        raise HTTPException(400, "invalid key id")

    result = mongo.update_one(
        "ingestion_keys",
        {
            "_id": oid,
            "context_id": context_id,
        },
        {"$set": {"enabled": False}},
    )

    if result.matched_count == 0:
        raise HTTPException(404, "key not found")

    audit.log(
        event="ingestion_key_revoked",
        identity=identity,
        metadata={"key_id": key_id, "context_id": context_id},
        request=request,
    )

    return {"ok": True}


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
