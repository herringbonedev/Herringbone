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
    create_context_token,
)

from app.schemas import (
    RegisterRequest,
    LoginRequest,
    UserDeleteRequest,
    UserScopesUpdateRequest,
)

router = APIRouter(prefix="/herringbone/auth", tags=["users"])

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

    if mongo.find_one_with_context("users", {"email": payload.email}, context_id="default"):
        audit.log(
            event="user_register_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "user_exists", "email": payload.email},
            request=request,
        )
        raise HTTPException(400, "User already exists")

    user_count = len(mongo.find_with_context("users", {}, context_id="default"))

    if user_count == 0:
        scopes = ["*"]
    else:
        requested_scopes = payload.scopes or [
            "detections:rules:read",
            "parser:cards:read",
            "dashboard:read",
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

    user_id = mongo.insert_one("users", user_doc, context_id="default")

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


@router.get("/users")
async def list_users(
    request: Request,
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    mongo = get_mongo()

    context_id = context.get("context_id")
    enterprise_enabled = context.get("enterprise_enabled", False)

    users = []
    members_by_user = {}

    if not enterprise_enabled or context_id == "default":
        users = mongo.find_with_context("users", {}, context_id="default")

    else:
        try:
            org_oid = ObjectId(context_id)
        except Exception:
            raise HTTPException(400, "invalid context_id")

        members = mongo.find_with_context(
            "organization_members",
            {
                "org_id": org_oid,
                "status": "active",
            },
            context_id=context_id,
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
            users = mongo.find_with_context(
                "users",
                {"_id": {"$in": object_ids}},
                context_id="default",
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
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    mongo = get_mongo()

    target = mongo.find_one_with_context("users", {"email": payload.email}, context_id="default")

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
            context_id="default",
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

    member = mongo.find_one_with_context(
        "organization_members",
        {
            "user_id": target["_id"],
            "org_id": org_oid,
            "status": "active",
        },
        context_id=context_id,
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
        context_id=context_id,
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

    target = mongo.find_one_with_context("users", {"email": payload.email}, context_id="default")

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    mongo.delete_one("users", {"_id": target["_id"]}, context_id="default")

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
    scopes = mongo.find_one("scopes", {})

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