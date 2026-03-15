import os
from datetime import datetime, UTC
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import require_scopes, get_identity, get_identity_optional
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
    mongo = get_mongo()

    bootstrap_required = is_bootstrap_required(mongo)

    if bootstrap_required:
        expected = load_bootstrap_token()
        provided = request.headers.get("x-bootstrap-token")

        if not expected or not provided or provided != expected:
            audit.log(
                event="user_register_denied",
                request=request,
                identity=identity,
                target=payload.email,
                result="failure",
                metadata={"reason": "invalid_bootstrap_token"},
            )
            raise HTTPException(
                status_code=403,
                detail="Bootstrap token required for first user",
            )

    else:
        if identity is None:
            audit.log(
                event="user_register_denied",
                request=request,
                identity=identity,
                target=payload.email,
                result="failure",
                metadata={"reason": "authentication_required"},
            )
            raise HTTPException(status_code=401, detail="Authentication required")

        caller_scopes = identity.get("scopes", [])

        if "*" not in caller_scopes and "platform:admin" not in caller_scopes:
            audit.log(
                event="user_register_denied",
                request=request,
                identity=identity,
                target=payload.email,
                result="failure",
                metadata={"reason": "admin_required"},
            )
            raise HTTPException(
                status_code=403,
                detail="Only platform admins can create users",
            )

    if mongo.find_one("users", {"email": payload.email}):
        audit.log(
            event="user_register_denied",
            request=request,
            identity=identity,
            target=payload.email,
            result="failure",
            metadata={"reason": "user_already_exists"},
        )
        raise HTTPException(status_code=400, detail="User already exists")

    user_count = len(mongo.find("users", {}))

    if user_count == 0:
        scopes = ["*"]
        event_name = "bootstrap_admin_created"
    else:
        requested_scopes = payload.scopes or [
            "logs:read",
            "search:query",
            "incidents:read",
        ]

        caller_scopes = identity.get("scopes", []) if identity else []

        if "platform:admin" in requested_scopes or "*" in requested_scopes:
            if "*" not in caller_scopes and "platform:admin" not in caller_scopes:
                audit.log(
                    event="user_register_denied",
                    request=request,
                    identity=identity,
                    target=payload.email,
                    result="failure",
                    metadata={"reason": "admin_escalation_denied"},
                )
                raise HTTPException(
                    status_code=403,
                    detail="Only platform admins can create another platform admin",
                )

        scopes = requested_scopes
        event_name = "user_created"

    user_doc = {
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "scopes": scopes,
        "created_at": datetime.now(UTC),
    }

    user_id = mongo.insert_one("users", user_doc)

    audit.log(
        event=event_name,
        request=request,
        identity=identity,
        target=payload.email,
        metadata={
            "user_id": str(user_id),
            "assigned_scopes": scopes,
        },
    )

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

    if not user:
        audit.log(
            event="user_login_denied",
            request=request,
            target=payload.email,
            result="failure",
            severity="ERROR",
            metadata={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user["password_hash"]):
        audit.log(
            event="user_login_denied",
            request=request,
            target=payload.email,
            result="failure",
            severity="ERROR",
            metadata={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        user_id=str(user["_id"]),
        email=user["email"],
        scopes=user.get("scopes", []),
    )

    audit.log(
        event="user_login",
        request=request,
        identity={
            "sub": str(user["_id"]),
            "email": user["email"],
            "scopes": user.get("scopes", []),
        },
        target=user["email"],
        metadata={"token_type": "user"},
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/users")
async def list_users(
    request: Request,
    identity=Depends(get_identity),
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()
    users = mongo.find("users", {})

    audit.log(
        event="users_listed",
        request=request,
        identity=identity,
        metadata={"count": len(users)},
    )

    return {
        "count": len(users),
        "users": [
            {
                "email": u.get("email"),
                "scopes": u.get("scopes", []),
            }
            for u in users
        ],
    }


@router.post("/users/scopes")
async def update_user_scopes(
    payload: UserScopesUpdateRequest,
    request: Request,
    identity=admin,
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    target = mongo.find_one("users", {"email": payload.email})

    if not target:
        audit.log(
            event="user_scope_update_denied",
            request=request,
            identity=identity,
            target=payload.email,
            result="failure",
            severity="WARNING",
            metadata={"reason": "user_not_found"},
        )
        raise HTTPException(status_code=404, detail="User not found")

    caller_scopes = identity.get("scopes", [])

    if "platform:admin" in payload.scopes or "*" in payload.scopes:
        if "*" not in caller_scopes and "platform:admin" not in caller_scopes:
            audit.log(
                event="user_scope_update_denied",
                request=request,
                identity=identity,
                target=payload.email,
                result="failure",
                severity="CRITICAL",
                metadata={"reason": "admin_escalation_denied"},
            )
            raise HTTPException(
                status_code=403,
                detail="Only platform admins can grant platform admin",
            )

    mongo.update_one(
        "users",
        {"_id": target["_id"]},
        {"$set": {"scopes": payload.scopes}},
    )

    audit.log(
        event="user_scopes_updated",
        request=request,
        identity=identity,
        target=payload.email,
        metadata={"assigned_scopes": payload.scopes},
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
        audit.log(
            event="user_delete_denied",
            request=request,
            identity=identity,
            target=payload.email,
            result="failure",
            severity="WARNING",
            metadata={"reason": "user_not_found"},
        )
        raise HTTPException(status_code=404, detail="User not found")

    mongo.delete_one("users", {"_id": target["_id"]})

    audit.log(
        event="user_deleted",
        request=request,
        identity=identity,
        target=payload.email,
        metadata={"user_id": str(target["_id"])},
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

    audit.log(
        event="scopes_listed",
        request=request,
        identity=identity,
        metadata={"count": len(scopes)},
    )

    return {
        "scopes": [
            {"scope": s.get("scope"), "tier": s.get("tier", "free")}
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
        audit.log(
            event="service_register_denied",
            request=request,
            identity=identity,
            target=payload.service_name,
            result="failure",
            severity="WARNING",
            metadata={"reason": "service_already_exists"},
        )
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
        request=request,
        identity=identity,
        target=payload.service_name,
        metadata={
            "service_id": str(svc_id),
            "assigned_scopes": payload.scopes,
        },
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

    audit.log(
        event="services_listed",
        request=request,
        identity=identity,
        metadata={"count": len(services)},
    )

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
            event="service_token_create_denied",
            request=request,
            identity=identity,
            target=payload.service,
            result="failure",
            severity="WARNING",
            metadata={"reason": "service_not_found_or_disabled"},
        )
        raise HTTPException(status_code=404, detail="Service not found or disabled")

    token = create_service_token(
        service_id=str(svc["_id"]),
        service_name=svc["service_name"],
        scopes=payload.scopes,
    )

    audit.log(
        event="service_token_created",
        request=request,
        identity=identity,
        target=payload.service,
        metadata={"assigned_scopes": payload.scopes},
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
            event="service_delete_denied",
            request=request,
            identity=identity,
            target=service_name,
            result="failure",
            severity="WARNING",
            metadata={"reason": "service_not_found"},
        )
        raise HTTPException(status_code=404, detail="Service not found")

    mongo.delete_one("service_accounts", {"_id": svc["_id"]})

    audit.log(
        event="service_deleted",
        request=request,
        identity=identity,
        target=service_name,
        metadata={"service_id": str(svc["_id"])},
    )

    return {
        "ok": True,
        "deleted": service_name,
    }


@router.post("/services/scopes/remove")
async def remove_service_scopes(
    payload: ServiceScopeUpdateRequest,
    request: Request,
    identity=admin,
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    svc = mongo.find_one("service_accounts", {"service_name": payload.service_name})

    if not svc:
        audit.log(
            event="service_scope_remove_denied",
            request=request,
            identity=identity,
            target=payload.service_name,
            result="failure",
            metadata={"reason": "service_not_found"},
        )
        raise HTTPException(status_code=404, detail="Service not found")

    mongo.update_one(
        "service_accounts",
        {"_id": svc["_id"]},
        {"$pull": {"scopes": {"$in": payload.scopes}}},
    )

    audit.log(
        event="service_scopes_removed",
        request=request,
        identity=identity,
        target=payload.service_name,
        metadata={"removed_scopes": payload.scopes},
    )

    return {
        "ok": True,
        "service": payload.service_name,
        "removed": payload.scopes,
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

    return {
        "ok": True,
        "collections": cols,
    }