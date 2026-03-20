from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jose import jwt
from bson import ObjectId
import uuid
import os

from modules.audit.logger import AuditLogger
from modules.database.mongo_db import HerringboneMongoDatabase


JWT_ALG_USER = "HS256"
JWT_ALG_SERVICE = "RS256"

USER_SECRET_PATH = "/run/secrets/jwt_secret"
SERVICE_PUBLIC_KEY_PATH = "/run/secrets/service_jwt_public_key"
SERVICE_TOKEN_PATH = "/run/secrets/service_token"

SERVICE_AUD = "herringbone-services"

DEFAULT_CONTEXT = "default"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/login")

_user_secret = None
_service_public_key = None
_service_token = None


def _load_file(path):
    try:
        with open(path, "r") as f:
            value = f.read().strip()
    except FileNotFoundError:
        raise RuntimeError(f"Secret file not found: {path}")

    if not value:
        raise RuntimeError(f"Secret file empty: {path}")

    return value


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
    )


def is_enterprise_enabled() -> bool:
    return os.environ.get("HB_ENTERPRISE", "false").lower() == "true"


def get_user_secret():
    global _user_secret
    if _user_secret is None:
        _user_secret = _load_file(USER_SECRET_PATH)
    return _user_secret


def get_service_public_key():
    global _service_public_key
    if _service_public_key is None:
        _service_public_key = _load_file(SERVICE_PUBLIC_KEY_PATH)
    return _service_public_key


def get_service_token():
    global _service_token
    if _service_token is None:
        _service_token = _load_file(SERVICE_TOKEN_PATH)
    return _service_token


def service_auth_headers():
    return {"Authorization": f"Bearer {get_service_token()}"}


def _normalize_identity(payload, identity_type):
    scopes = payload.get("scope", [])
    if isinstance(scopes, str):
        scopes = scopes.split()

    identity = {
        "type": identity_type,
        "scopes": scopes,
        "token_id": payload.get("jti"),
    }

    if identity_type == "user":
        identity["id"] = payload.get("sub")
        identity["email"] = payload.get("email")

    if identity_type == "service":
        identity["service"] = payload.get("service")
        identity["service_id"] = payload.get("sub")

    return identity


def decode_token(token):
    audit = AuditLogger()

    try:
        payload = jwt.decode(
            token,
            get_user_secret(),
            algorithms=[JWT_ALG_USER],
        )

        if payload.get("typ") == "user":
            identity = _normalize_identity(payload, "user")

            audit.log(
                event="auth_user_token_valid",
                identity=identity,
                metadata={"token_type": "user"},
            )
            return identity

    except Exception as e:
        audit.log(
            event="auth_user_token_invalid",
            result="failure",
            severity="WARNING",
            metadata={"error": str(e)},
        )

    try:
        payload = jwt.decode(
            token,
            get_service_public_key(),
            algorithms=[JWT_ALG_SERVICE],
            audience=SERVICE_AUD,
        )

        if payload.get("typ") == "service":
            identity = _normalize_identity(payload, "service")

            audit.log(
                event="auth_service_token_valid",
                identity=identity,
                metadata={"token_type": "service"},
            )
            return identity

    except Exception as e:
        audit.log(
            event="auth_service_token_invalid",
            result="failure",
            severity="WARNING",
            metadata={"error": str(e)},
        )

    audit.log(
        event="auth_token_rejected",
        result="failure",
        severity="WARNING",
    )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )


def get_identity(token: str = Depends(oauth2_scheme)):
    return decode_token(token)


async def get_identity_optional(request: Request):
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return None

    scheme, token = get_authorization_scheme_param(auth_header)

    if scheme.lower() != "bearer" or not token:
        return None

    try:
        return decode_token(token)
    except HTTPException:
        return None


def resolve_context_id(request: Request, context: dict) -> str:
    audit = AuditLogger()

    enterprise_enabled = is_enterprise_enabled()

    if not enterprise_enabled:
        return DEFAULT_CONTEXT

    context_id = context.get("context_id")
    identity = context.get("identity")

    if not context_id:
        audit.log(
            event="context_missing",
            identity=identity,
            result="failure",
            severity="WARNING",
        )
        raise HTTPException(400, "context header required")

    if identity and identity.get("type") == "service":
        audit.log(
            event="context_service_forbidden",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={"context_id": context_id},
        )
        raise HTTPException(403, "service identity cannot use org context")

    return str(context_id)


def _dedupe_scopes(scopes: list[str]) -> list[str]:
    seen = set()
    result = []
    for scope in scopes:
        if scope and scope not in seen:
            seen.add(scope)
            result.append(scope)
    return result


def get_context(
    request: Request,
    identity=Depends(get_identity),
):
    audit = AuditLogger()

    enterprise_enabled = is_enterprise_enabled()
    header_context = request.headers.get("X-Herringbone-Org")

    if enterprise_enabled and not header_context:
        audit.log(
            event="context_missing_header_fallback",
            identity=identity,
            metadata={
                "fallback": "default_context"
            },
        )
        raw_context_id = DEFAULT_CONTEXT
    else:
        raw_context_id = header_context

    raw_context_id = header_context if enterprise_enabled else DEFAULT_CONTEXT

    ctx = {
        "context_id": raw_context_id,
        "identity": identity,
        "trace_id": str(uuid.uuid4()),
        "global_scopes": list(identity.get("scopes", [])),
        "org_scopes": [],
        "role": None,
    }

    ctx["context_id"] = resolve_context_id(request, ctx)

    if identity.get("type") == "service":
        effective_scopes = _dedupe_scopes(list(identity.get("scopes", [])))
        effective_identity = dict(identity)
        effective_identity["scopes"] = effective_scopes

        ctx["scopes"] = effective_scopes
        ctx["identity"] = effective_identity

        request.state.context_id = ctx["context_id"]
        request.state.scopes = effective_scopes
        request.state.identity = effective_identity

        audit.log(
            event="context_resolved",
            identity=effective_identity,
            metadata={
                "context_id": ctx["context_id"],
                "enterprise_enabled": enterprise_enabled,
                "header_present": bool(header_context),
                "scope_count": len(effective_scopes),
                "role": None,
            },
        )

        return ctx

    if not enterprise_enabled or ctx["context_id"] == DEFAULT_CONTEXT:
        effective_scopes = _dedupe_scopes(list(identity.get("scopes", [])))
        effective_identity = dict(identity)
        effective_identity["scopes"] = effective_scopes

        ctx["scopes"] = effective_scopes
        ctx["identity"] = effective_identity

        request.state.context_id = ctx["context_id"]
        request.state.scopes = effective_scopes
        request.state.identity = effective_identity

        audit.log(
            event="context_resolved",
            identity=effective_identity,
            metadata={
                "context_id": ctx["context_id"],
                "enterprise_enabled": enterprise_enabled,
                "header_present": bool(header_context),
                "scope_count": len(effective_scopes),
                "role": None,
            },
        )

        return ctx

    try:
        from app.enterprise.orgs.orgs_context import resolve_org_context
    except ImportError:
        audit.log(
            event="enterprise_module_missing",
            identity=identity,
            result="failure",
            severity="ERROR",
        )
        raise HTTPException(500, "enterprise module not available")

    org_ctx = resolve_org_context(request=request, context=ctx)

    ctx["context_id"] = org_ctx["context_id"]
    ctx["role"] = org_ctx.get("role")
    ctx["org_scopes"] = list(org_ctx.get("org_scopes", []))
    ctx["slug"] = org_ctx.get("slug")

    effective_scopes = _dedupe_scopes(
        list(ctx["global_scopes"]) + list(ctx["org_scopes"])
    )

    effective_identity = dict(identity)
    effective_identity["scopes"] = effective_scopes
    effective_identity["global_scopes"] = list(ctx["global_scopes"])
    effective_identity["org_scopes"] = list(ctx["org_scopes"])
    effective_identity["context_id"] = ctx["context_id"]
    effective_identity["org_role"] = ctx["role"]

    ctx["scopes"] = effective_scopes
    ctx["identity"] = effective_identity

    request.state.context_id = ctx["context_id"]
    request.state.scopes = effective_scopes
    request.state.identity = effective_identity
    request.state.org_role = ctx["role"]

    audit.log(
        event="context_resolved",
        identity=effective_identity,
        metadata={
            "context_id": ctx["context_id"],
            "enterprise_enabled": enterprise_enabled,
            "header_present": bool(header_context),
            "scope_count": len(effective_scopes),
            "role": ctx["role"],
        },
    )

    return ctx


def require_scopes(scope_sets):
    if isinstance(scope_sets, str):
        scope_sets = [(scope_sets,)]

    def checker(context: dict = Depends(get_context)):
        audit = AuditLogger()

        identity = context.get("identity", {})
        scopes = set(context.get("scopes", []))

        if "*" in scopes:
            return identity

        for scope_set in scope_sets:
            if all(scope in scopes for scope in scope_set):
                return identity

        audit.log(
            event="auth_scope_denied",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={
                "required_scopes": scope_sets,
                "granted_scopes": list(scopes),
                "context_id": context.get("context_id"),
                "role": context.get("role"),
            },
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return checker


def require_user_identity(identity: dict = Depends(get_identity)):
    audit = AuditLogger()

    if not identity:
        audit.log(
            event="auth_user_missing",
            result="failure",
            severity="WARNING",
        )
        raise HTTPException(401, "authentication required")

    if identity.get("type") != "user":
        audit.log(
            event="auth_user_required",
            identity=identity,
            result="failure",
            severity="WARNING",
        )
        raise HTTPException(403, "user identity required")

    if not identity.get("id"):
        audit.log(
            event="auth_user_invalid",
            identity=identity,
            result="failure",
            severity="WARNING",
        )
        raise HTTPException(400, "invalid user identity")

    return identity