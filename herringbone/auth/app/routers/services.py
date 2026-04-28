import os, secrets
from datetime import datetime, UTC
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import (
    require_scopes,
    get_identity,
    get_context
)

from modules.audit import AuditLogger

from app.security import (
    create_service_token,
)

from app.schemas import (
    ServiceTokenRequest,
    ServiceRegisterRequest,
    ServiceScopeUpdateRequest,
)

router = APIRouter(prefix="/herringbone/auth", tags=["services"])

identity = Depends(get_identity)
admin = Depends(require_scopes("platform:admin"))
root_admin = Depends(require_scopes("*"))


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


@router.post("/services/internal/register")
async def register_internal_service(
    payload: ServiceRegisterRequest,
    request: Request,
    identity=root_admin,
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    service_id = getattr(payload, "service_id", None) or payload.service_name

    if mongo.find_one(
        "service_accounts",
        {
            "service_name": payload.service_name,
            "owner_type": "platform",
        },
    ):
        raise HTTPException(status_code=400, detail="Service already exists")

    svc_doc = {
        "service_name": payload.service_name,
        "service_id": service_id,
        "owner_type": "platform",
        "internal": True,
        "context_id": None,
        "scopes": payload.scopes,
        "enabled": True,
        "created_at": datetime.now(UTC),
    }

    svc_id = mongo.insert_one("service_accounts", svc_doc)

    audit.log(
        event="internal_service_registered",
        identity=identity,
        metadata={
            "service_name": payload.service_name,
            "service_id": service_id,
        },
        request=request,
    )

    return {
        "ok": True,
        "service_id": str(svc_id),
        "service_account_id": service_id,
        "service_name": payload.service_name,
    }


@router.post("/services/register")
async def register_customer_service(
    payload: ServiceRegisterRequest,
    request: Request,
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    mongo = get_mongo()

    require_scopes("orgs:keys:write")(context)

    if identity.get("type") != "user":
        audit.log(
            event="customer_service_register_denied",
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
            event="customer_service_register_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "org_context_required"},
            request=request,
        )
        raise HTTPException(403, "organization context required")

    if mongo.find_one(
        "service_accounts",
        {
            "service_name": payload.service_name,
            "owner_type": "customer",
            "context_id": context_id,
        },
    ):
        raise HTTPException(status_code=400, detail="Service already exists")

    svc_doc = {
        "service_name": payload.service_name,
        "service_id": payload.service_name,
        "owner_type": "customer",
        "internal": False,
        "context_id": context_id,
        "scopes": payload.scopes,
        "enabled": True,
        "created_at": datetime.now(UTC),
        "created_by": identity.get("email"),
    }

    svc_id = mongo.insert_one("service_accounts", svc_doc)

    audit.log(
        event="customer_service_registered",
        identity=identity,
        metadata={
            "service_name": payload.service_name,
            "context_id": context_id,
        },
        request=request,
    )

    return {
        "ok": True,
        "service_id": str(svc_id),
        "service_name": payload.service_name,
        "context_id": context_id,
    }


@router.get("/services")
async def list_services(
    request: Request,
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    mongo = get_mongo()

    require_scopes("orgs:keys:read")(context)

    if identity.get("type") != "user":
        audit.log(
            event="services_list_denied",
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
            event="services_list_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "org_context_required"},
            request=request,
        )
        raise HTTPException(403, "organization context required")

    services = mongo.find(
        "service_accounts",
        {
            "owner_type": "customer",
            "internal": {"$ne": True},
            "context_id": context_id,
        },
    )

    audit.log(
        event="customer_services_listed",
        identity=identity,
        metadata={
            "count": len(services),
            "context_id": context_id,
        },
        request=request,
    )

    return {
        "count": len(services),
        "services": [
            {
                "id": str(s.get("_id")),
                "service_name": s.get("service_name"),
                "service_id": s.get("service_id"),
                "owner_type": s.get("owner_type", "customer"),
                "scopes": s.get("scopes", []),
                "enabled": s.get("enabled", True),
                "created_at": s.get("created_at"),
                "created_by": s.get("created_by"),
            }
            for s in services
        ],
    }


@router.post("/services/scopes/set")
async def set_service_scopes(
    payload: ServiceScopeUpdateRequest,
    request: Request,
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    mongo = get_mongo()

    require_scopes("orgs:keys:write")(context)

    if identity.get("type") != "user":
        audit.log(
            event="service_scope_update_denied",
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
            event="service_scope_update_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "org_context_required"},
            request=request,
        )
        raise HTTPException(403, "organization context required")

    svc = mongo.find_one(
        "service_accounts",
        {
            "service_name": payload.service_name,
            "owner_type": "customer",
            "internal": {"$ne": True},
            "context_id": context_id,
        },
    )

    if not svc:
        audit.log(
            event="service_lookup_failed",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={
                "service_name": payload.service_name,
                "context_id": context_id,
            },
            request=request,
        )
        raise HTTPException(status_code=404, detail="Service not found")

    caller_scopes = identity.get("scopes", [])
    validate_admin_scope_assignment(payload.scopes, caller_scopes)

    mongo.update_one(
        "service_accounts",
        {"_id": svc["_id"]},
        {
            "$set": {
                "scopes": payload.scopes,
                "updated_at": datetime.now(UTC),
            }
        },
    )

    audit.log(
        event="customer_service_scopes_updated",
        identity=identity,
        metadata={
            "service": payload.service_name,
            "scopes": payload.scopes,
            "context_id": context_id,
        },
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
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    mongo = get_mongo()

    require_scopes("orgs:keys:write")(context)

    if identity.get("type") != "user":
        audit.log(
            event="service_token_denied",
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
            event="service_token_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "org_context_required"},
            request=request,
        )
        raise HTTPException(403, "organization context required")

    svc = mongo.find_one(
        "service_accounts",
        {
            "service_name": payload.service,
            "owner_type": "customer",
            "internal": {"$ne": True},
            "context_id": context_id,
            "enabled": True,
        },
    )

    if not svc:
        audit.log(
            event="service_lookup_failed",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={
                "service_name": payload.service,
                "context_id": context_id,
            },
            request=request,
        )
        raise HTTPException(status_code=404, detail="Service not found or disabled")

    requested_scopes = payload.scopes or []
    allowed_scopes = set(svc.get("scopes", []))

    if "*" not in allowed_scopes:
        invalid_scopes = [
            scope for scope in requested_scopes
            if scope not in allowed_scopes
        ]

        if invalid_scopes:
            audit.log(
                event="service_token_scope_denied",
                identity=identity,
                result="failure",
                severity="WARNING",
                metadata={
                    "service": payload.service,
                    "context_id": context_id,
                    "invalid_scopes": invalid_scopes,
                },
                request=request,
            )
            raise HTTPException(403, "requested scopes exceed service account grants")

    token = create_service_token(
        service_id=str(svc["_id"]),
        service_name=svc["service_name"],
        scopes=requested_scopes,
    )

    audit.log(
        event="customer_service_token_created",
        identity=identity,
        metadata={
            "service": payload.service,
            "scopes": requested_scopes,
            "context_id": context_id,
        },
        request=request,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/services/internal/token")
async def create_internal_service_token_api(
    payload: ServiceTokenRequest,
    request: Request,
    identity=root_admin,
    audit: AuditLogger = Depends(get_audit_logger),
):
    mongo = get_mongo()

    svc = mongo.find_one(
        "service_accounts",
        {
            "service_name": payload.service,
            "owner_type": "platform",
            "internal": True,
            "enabled": True,
        },
    )

    if not svc:
        audit.log(
            event="internal_service_lookup_failed",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"service_name": payload.service},
            request=request,
        )
        raise HTTPException(status_code=404, detail="Internal service not found or disabled")

    requested_scopes = payload.scopes or []
    allowed_scopes = set(svc.get("scopes", []))

    if "*" not in allowed_scopes:
        invalid_scopes = [
            scope for scope in requested_scopes
            if scope not in allowed_scopes
        ]

        if invalid_scopes:
            audit.log(
                event="internal_service_token_scope_denied",
                identity=identity,
                result="failure",
                severity="WARNING",
                metadata={
                    "service": payload.service,
                    "invalid_scopes": invalid_scopes,
                },
                request=request,
            )
            raise HTTPException(403, "requested scopes exceed service account grants")

    token = create_service_token(
        service_id=str(svc["_id"]),
        service_name=svc["service_name"],
        scopes=requested_scopes,
    )

    audit.log(
        event="internal_service_token_created",
        identity=identity,
        metadata={
            "service": payload.service,
            "scopes": requested_scopes,
        },
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
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    mongo = get_mongo()

    require_scopes("orgs:keys:write")(context)

    if identity.get("type") != "user":
        audit.log(
            event="service_delete_denied",
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
            event="service_delete_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"reason": "org_context_required"},
            request=request,
        )
        raise HTTPException(403, "organization context required")

    svc = mongo.find_one(
        "service_accounts",
        {
            "service_name": service_name,
            "owner_type": "customer",
            "internal": {"$ne": True},
            "context_id": context_id,
        },
    )

    if not svc:
        audit.log(
            event="service_lookup_failed",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={
                "service_name": service_name,
                "context_id": context_id,
            },
            request=request,
        )
        raise HTTPException(status_code=404, detail="Service not found")

    mongo.delete_one(
        "service_accounts",
        {"_id": svc["_id"]},
    )

    audit.log(
        event="customer_service_deleted",
        identity=identity,
        metadata={
            "service_name": service_name,
            "context_id": context_id,
        },
        request=request,
    )

    return {
        "ok": True,
        "deleted": service_name,
    }