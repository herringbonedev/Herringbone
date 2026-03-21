import os, secrets
from datetime import datetime, UTC
from typing import Optional
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import (
    require_scopes,
    get_identity,
    get_identity_optional,
    get_context
)

from modules.audit import AuditLogger

from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_service_token,
    generate_ingestion_key,
    hash_ingestion_key,
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


@router.post("/register")
async def register_user(
    payload: RegisterRequest,
    request: Request,
    identity: dict | None = Depends(get_identity_optional),
    audit: AuditLogger = Depends(get_audit_logger),
):
    import secrets

    mongo = get_mongo()

    bootstrap_required = is_bootstrap_required(mongo)

    if bootstrap_required:
        expected = load_bootstrap_token()
        provided = request.headers.get("x-bootstrap-token")

        if not expected or not provided or not secrets.compare_digest(provided, expected):
            audit.log(
                event="user_register_denied",
                identity=identity,
                result="failure",
                severity="WARNING",
                metadata={"reason": "invalid_bootstrap_token"},
                request=request,
            )
            raise HTTPException(403, "Bootstrap token required for first user")

    else:
        if identity is None:
            audit.log(
                event="user_register_denied",
                result="failure",
                severity="WARNING",
                metadata={"reason": "unauthenticated"},
                request=request,
            )
            raise HTTPException(401, "Authentication required")

        caller_scopes = identity.get("scopes", [])

        if "*" not in caller_scopes and "platform:admin" not in caller_scopes:
            audit.log(
                event="user_register_denied",
                identity=identity,
                result="failure",
                severity="WARNING",
                metadata={"reason": "insufficient_scope"},
                request=request,
            )
            raise HTTPException(403, "Only platform admins can create users")

    if mongo.find_one("users", {"email": payload.email}):
        audit.log(
            event="user_register_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "user_exists", "email": payload.email},
            request=request,
        )
        raise HTTPException(400, "User already exists")

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

    audit.log(
        event="user_register_success",
        identity=identity,
        metadata={"email": payload.email, "user_id": str(user_id)},
        request=request,
    )

    return {"ok": True, "user_id": str(user_id), "scopes": scopes}


@router.post("/login")
async def login_user(
    payload: LoginRequest,
    request: Request,
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    user = mongo.find_one("users", {"email": payload.email})

    if not user or not verify_password(payload.password, user["password_hash"]):
        audit.log(
            event="user_login_failed",
            result="failure",
            severity="WARNING",
            metadata={"email": payload.email},
            request=request,
        )
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token(
        user_id=str(user["_id"]),
        email=user["email"],
        scopes=user.get("scopes", []),
    )

    audit.log(
        event="user_login_success",
        identity={
            "id": str(user["_id"]),
            "email": user["email"],
            "scopes": user.get("scopes", []),
            "type": "user",
        },
        request=request,
    )

    return {"access_token": token, "token_type": "bearer"}


@router.get("/users")
async def list_users(
    request: Request,
    identity=Depends(get_identity),
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    context_id = context.get("context_id")
    enterprise_enabled = context.get("enterprise_enabled", False)

    users = []
    members_by_user = {}

    if not enterprise_enabled or context_id == "default":
        users = mongo.find("users", {})

    else:
        try:
            org_oid = ObjectId(context_id)
        except Exception:
            raise HTTPException(400, "invalid context_id")

        members = mongo.find(
            "organization_members",
            {
                "org_id": org_oid,
                "status": "active",
            },
        )

        if not members:
            audit.log(
                event="users_list",
                identity=identity,
                metadata={
                    "count": 0,
                    "context_id": context_id,
                    "enterprise_enabled": enterprise_enabled,
                },
                request=request,
            )
            return {"count": 0, "users": []}

        object_ids = []
        for m in members:
            uid = m.get("user_id")
            if not uid:
                continue

            try:
                oid = uid if isinstance(uid, ObjectId) else ObjectId(str(uid))
            except Exception:
                continue

            object_ids.append(oid)
            members_by_user[str(oid)] = m

        if object_ids:
            users = mongo.find(
                "users",
                {"_id": {"$in": object_ids}},
            )
        else:
            users = []

    result = []

    for u in users:
        user_id = str(u["_id"])

        global_scopes = u.get("scopes", [])
        org_scopes = None
        role = None

        if enterprise_enabled and context_id != "default":
            member = members_by_user.get(user_id)

            if member:
                org_scopes = member.get("scopes", [])
                role = member.get("role")

        effective_scopes = (
            org_scopes if org_scopes is not None else global_scopes
        )

        result.append(
            {
                "email": u.get("email"),
                "scopes": effective_scopes,
                "global_scopes": global_scopes,
                "org_scopes": org_scopes,
                "role": role,
            }
        )

    audit.log(
        event="users_list",
        identity=identity,
        metadata={
            "count": len(result),
            "context_id": context_id,
            "enterprise_enabled": enterprise_enabled,
        },
        request=request,
    )

    return {
        "count": len(result),
        "users": result,
    }


@router.post("/users/scopes")
async def update_user_scopes(
    payload: UserScopesUpdateRequest,
    request: Request,
    identity=Depends(get_identity),
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    target = mongo.find_one("users", {"email": payload.email})

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    caller_scopes = identity.get("scopes", [])
    validate_admin_scope_assignment(payload.scopes, caller_scopes)

    context_id = context.get("context_id")
    enterprise_enabled = context.get("enterprise_enabled", False)

    if not enterprise_enabled or not context_id or context_id == "default":
        mongo.update_one(
            "users",
            {"_id": target["_id"]},
            {"$set": {"scopes": payload.scopes}},
        )

        audit.log(
            event="user_scopes_updated",
            identity=identity,
            metadata={
                "email": payload.email,
                "scopes": payload.scopes,
                "mode": "global",
                "context_id": "default",
            },
            request=request,
        )

        return {
            "ok": True,
            "email": payload.email,
            "scopes": payload.scopes,
        }

    try:
        org_oid = ObjectId(context_id)
    except Exception:
        raise HTTPException(400, "invalid context_id")

    member = mongo.find_one(
        "organization_members",
        {
            "user_id": target["_id"],
            "org_id": org_oid,
            "status": "active",
        },
    )

    if not member:
        audit.log(
            event="user_scopes_update_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={
                "email": payload.email,
                "context_id": context_id,
                "reason": "membership_not_found",
            },
            request=request,
        )
        raise HTTPException(404, "user is not a member of this organization")

    mongo.update_one(
        "organization_members",
        {"_id": member["_id"]},
        {
            "$set": {
                "scopes": payload.scopes,
                "updated_at": datetime.now(UTC),
            }
        },
    )

    audit.log(
        event="user_scopes_updated",
        identity=identity,
        metadata={
            "email": payload.email,
            "scopes": payload.scopes,
            "mode": "org",
            "context_id": context_id,
        },
        request=request,
    )

    return {
        "ok": True,
        "email": payload.email,
        "scopes": payload.scopes,
    }


@router.delete("/users")
async def delete_user(
    payload: UserDeleteRequest,
    request: Request,
    identity=admin,
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    target = mongo.find_one("users", {"email": payload.email})

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    mongo.delete_one("users", {"_id": target["_id"]})

    audit.log(
        event="user_deleted",
        identity=identity,
        metadata={"email": payload.email},
        request=request,
    )

    return {
        "ok": True,
        "deleted": payload.email,
    }


@router.get("/scopes")
async def list_scopes(
    request: Request,
    identity=Depends(get_identity),
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()
    scopes = mongo.find("scopes", {})

    return {
        "count": len(scopes),
        "scopes": [
            {
                "scope": s.get("scope"),
                "category": s.get("category"),
                "action": s.get("action"),
                "description": s.get("description", ""),
                "tier": s.get("tier", "free"),
                "ui_group": s.get("ui_group", "General"),
                "order": s.get("order", 0),
            }
            for s in scopes
        ]
    }


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

    audit.log(
        event="service_registered",
        identity=identity,
        metadata={"service_name": payload.service_name},
        request=request,
    )

    return {
        "ok": True,
        "service_id": str(svc_id),
        "service_name": payload.service_name,
    }


@router.get("/services")
async def list_services(
    request: Request,
    identity=Depends(get_identity),
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()
    services = mongo.find("service_accounts", {})

    return {
        "count": len(services),
        "services": [
            {
                "id": str(s.get("_id")),
                "service_name": s.get("service_name"),
                "service_id": s.get("service_id"),
                "scopes": s.get("scopes", []),
                "enabled": s.get("enabled", True),
                "created_at": s.get("created_at"),
            }
            for s in services
        ],
    }


@router.post("/services/scopes/set")
async def set_service_scopes(
    payload: ServiceScopeUpdateRequest,
    request: Request,
    identity=Depends(get_identity),
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    svc = mongo.find_one("service_accounts", {"service_name": payload.service_name})

    if not svc:
        audit.log(
            event="service_lookup_failed",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"service_name": payload.service_name},
            request=request,
        )
        raise HTTPException(status_code=404, detail="Service not found")

    caller_scopes = identity.get("scopes", [])

    validate_admin_scope_assignment(payload.scopes, caller_scopes)

    mongo.update_one(
        "service_accounts",
        {"_id": svc["_id"]},
        {"$set": {"scopes": payload.scopes}},
    )

    audit.log(
        event="service_scopes_updated",
        identity=identity,
        metadata={"service": payload.service_name, "scopes": payload.scopes},
        request=request,
    )

    return {
        "ok": True,
        "service": payload.service_name,
        "scopes": payload.scopes,
    }


@router.post("/service-token")
async def create_service_token_api(
    payload: ServiceTokenRequest,
    request: Request,
    identity=admin,
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    svc = mongo.find_one(
        "service_accounts",
        {"service_name": payload.service, "enabled": True},
    )

    if not svc:
        audit.log(
            event="service_lookup_failed",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"service_name": payload.service},
            request=request,
        )
        raise HTTPException(status_code=404, detail="Service not found or disabled")

    token = create_service_token(
        service_id=str(svc["_id"]),
        service_name=svc["service_name"],
        scopes=payload.scopes,
    )

    audit.log(
        event="service_token_created",
        identity=identity,
        metadata={"service": payload.service, "scopes": payload.scopes},
        request=request,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.delete("/services/{service_name}")
async def delete_service(
    service_name: str,
    request: Request,
    identity=admin,
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    svc = mongo.find_one("service_accounts", {"service_name": service_name})

    if not svc:
        audit.log(
            event="service_lookup_failed",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"service_name": service_name},
            request=request,
        )
        raise HTTPException(status_code=404, detail="Service not found")

    mongo.delete_one("service_accounts", {"_id": svc["_id"]})

    audit.log(
        event="service_deleted",
        identity=identity,
        metadata={"service_name": service_name},
        request=request,
    )

    return {
        "ok": True,
        "deleted": service_name,
    }


@router.post("/ingestion-keys")
async def create_ingestion_key_api(
    request: Request,
    context=Depends(get_context),
    identity=Depends(require_scopes("ingestion:write")),
    audit: AuditLogger = Depends(get_audit_logger),
):
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

    context_id = context["context_id"]

    raw_key = generate_ingestion_key()

    doc = {
        "key_hash": hash_ingestion_key(raw_key),
        "context_id": context_id,
        "enabled": True,
        "created_at": datetime.now(UTC),
        "created_by": identity.get("email"),
    }

    mongo.insert_one("ingestion_keys", doc)

    audit.log(
        event="ingestion_key_created",
        identity=identity,
        metadata={"context_id": context_id},
        request=request,
    )

    return {"ok": True, "key": raw_key}


@router.get("/ingestion-keys")
async def list_ingestion_keys(
    request: Request,
    context=Depends(get_context),
    identity=Depends(require_scopes("ingestion:write")),
    audit: AuditLogger = Depends(get_audit_logger),
):
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

    context_id = context["context_id"]

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


@router.delete("/ingestion-keys/{key_id}")
async def revoke_ingestion_key(
    key_id: str,
    request: Request,
    context=Depends(get_context),
    identity=Depends(require_scopes("ingestion:write")),
    audit: AuditLogger = Depends(get_audit_logger),
):
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

    context_id = context["context_id"]

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