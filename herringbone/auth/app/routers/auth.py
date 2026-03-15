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


@router.get("/users")
async def list_users(
    request: Request,
    identity=Depends(get_identity),
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()
    users = mongo.find("users", {})

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
    identity=Depends(get_identity),
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    target = mongo.find_one("users", {"email": payload.email})

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    caller_scopes = identity.get("scopes", [])

    validate_admin_scope_assignment(payload.scopes, caller_scopes)

    mongo.update_one(
        "users",
        {"_id": target["_id"]},
        {"$set": {"scopes": payload.scopes}},
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
        raise HTTPException(status_code=404, detail="Service not found")

    caller_scopes = identity.get("scopes", [])

    validate_admin_scope_assignment(payload.scopes, caller_scopes)

    mongo.update_one(
        "service_accounts",
        {"_id": svc["_id"]},
        {"$set": {"scopes": payload.scopes}},
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
        raise HTTPException(status_code=404, detail="Service not found or disabled")

    token = create_service_token(
        service_id=str(svc["_id"]),
        service_name=svc["service_name"],
        scopes=payload.scopes,
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
        raise HTTPException(status_code=404, detail="Service not found")

    mongo.delete_one("service_accounts", {"_id": svc["_id"]})

    return {
        "ok": True,
        "deleted": service_name,
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