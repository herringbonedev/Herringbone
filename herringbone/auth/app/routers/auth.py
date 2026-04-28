import os, secrets
from datetime import datetime, UTC
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import (
    require_scopes,
    get_identity,
    get_identity_optional,
)

from modules.audit import AuditLogger

from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_context_token,
)

from app.schemas import (
    RegisterRequest,
    LoginRequest,
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
        return len(mongo.find_with_context("users", {}, context_id="default")) == 0
    except Exception:
        return True


@router.post("/login")
async def login_user(
    payload: LoginRequest,
    request: Request,
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    user = mongo.find_one_with_context("users", {"email": payload.email}, context_id="default")

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

    context_token = create_context_token(
        user_id=str(user["_id"]),
        email=user["email"],
        context_id="default",
        scopes=user.get("scopes", []),
        role=None,
        global_scopes=user.get("scopes", []),
        org_scopes=[],
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

    return {
        "token": token,
        "access_token": token,
        "context_token": context_token,
        "token_type": "bearer",
    }


@router.post("/context-token")
async def create_context_token_api(
    request: Request,
    identity=Depends(get_identity),
    audit: AuditLogger = Depends(get_audit_logger),
):
    if identity.get("type") != "user":
        audit.log(
            event="context_token_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "non_user_identity"},
            request=request,
        )
        raise HTTPException(403, "user identity required")

    body = {}
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
    except Exception:
        body = {}

    context_id = (
        body.get("context_id")
        or request.headers.get("X-Context-Id")
        or request.headers.get("X-Herringbone-Org")
        or request.headers.get("X-Herringbone-Context")
        or "default"
    )

    global_scopes = list(identity.get("scopes", []))
    org_scopes = []
    scopes = list(global_scopes)
    role = None

    if os.environ.get("HB_ENTERPRISE", "false").lower() == "true" and context_id != "default":
        try:
            from app.enterprise.orgs.orgs_context import resolve_org_context
        except ImportError:
            audit.log(
                event="enterprise_module_missing",
                identity=identity,
                request=request,
                result="failure",
                severity="ERROR",
            )
            raise HTTPException(500, "enterprise module not available")

        base_context = {
            "context_id": context_id,
            "identity": identity,
            "global_scopes": global_scopes,
            "org_scopes": [],
            "role": None,
            "enterprise_enabled": True,
        }

        org_ctx = resolve_org_context(request=request, context=base_context)
        context_id = org_ctx["context_id"]
        role = org_ctx.get("role")
        org_scopes = list(org_ctx.get("org_scopes", []))
        deduped = []
        seen = set()
        for scope in global_scopes + org_scopes:
            if scope and scope not in seen:
                seen.add(scope)
                deduped.append(scope)
        scopes = deduped

    token = create_context_token(
        user_id=identity.get("id"),
        email=identity.get("email"),
        context_id=context_id,
        scopes=scopes,
        role=role,
        global_scopes=global_scopes,
        org_scopes=org_scopes,
    )

    audit.log(
        event="context_token_created",
        identity={
            **identity,
            "scopes": scopes,
            "global_scopes": global_scopes,
            "org_scopes": org_scopes,
            "context_id": context_id,
            "role": role,
        },
        metadata={
            "context_id": context_id,
            "scope_count": len(scopes),
            "role": role,
        },
        request=request,
    )

    return {
        "token": token,
        "access_token": token,
        "token_type": "bearer",
        "context_id": context_id,
        "scopes": scopes,
        "role": role,
    }


@router.get("/scopes")
async def list_scopes(
    request: Request,
    identity=Depends(get_identity),
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()
    scopes = mongo.find_with_context("scopes", {}, context_id="default")

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