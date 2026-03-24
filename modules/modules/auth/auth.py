from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jose import jwt
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


def _normalize_scope_value(value):
    if isinstance(value, str):
        return value.split()
    if isinstance(value, list):
        return value
    return []


def _normalize_identity(payload, identity_type):
    scopes = _normalize_scope_value(payload.get("scope", []))

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


def _normalize_context_identity(payload):
    scopes = _normalize_scope_value(payload.get("scope", []))
    global_scopes = _normalize_scope_value(payload.get("global_scopes", []))
    org_scopes = _normalize_scope_value(payload.get("org_scopes", []))

    return {
        "type": "user",
        "scopes": scopes,
        "token_id": payload.get("jti"),
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "context_id": str(payload.get("context_id") or DEFAULT_CONTEXT),
        "role": payload.get("role"),
        "global_scopes": global_scopes,
        "org_scopes": org_scopes,
        "token_type": "context",
    }


def decode_token(token):
    audit = AuditLogger()

    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")

        if alg == "HS256":
            payload = jwt.decode(
                token,
                get_user_secret(),
                algorithms=["HS256"],
            )

            if payload.get("typ") == "context":
                identity = _normalize_context_identity(payload)

                audit.log(
                    event="auth_context_token_valid",
                    identity=identity,
                    metadata={
                        "token_type": "context",
                        "context_id": identity.get("context_id"),
                        "role": identity.get("role"),
                    },
                )
                return identity

            if payload.get("typ") == "user":
                identity = _normalize_identity(payload, "user")

                audit.log(
                    event="auth_user_token_valid",
                    identity=identity,
                    metadata={"token_type": "user"},
                )
                return identity

        elif alg == "RS256":
            payload = jwt.decode(
                token,
                get_service_public_key(),
                algorithms=["RS256"],
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

        else:
            raise Exception(f"Unsupported alg: {alg}")

    except Exception as e:
        audit.log(
            event="auth_token_rejected",
            result="failure",
            severity="WARNING",
            metadata={"error": str(e)},
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

    header_context = (
        request.headers.get("X-Herringbone-Org")
        or request.headers.get("X-Herringbone-Context")
    )
    
    if identity.get("token_type") == "context":
        token_context_id = str(identity.get("context_id") or DEFAULT_CONTEXT)

        if not enterprise_enabled:
            token_context_id = DEFAULT_CONTEXT

        if header_context and str(header_context) != token_context_id:
            audit.log(
                event="context_token_header_mismatch",
                identity=identity,
                request=request,
                result="failure",
                severity="WARNING",
                metadata={
                    "header_context": str(header_context),
                    "token_context": token_context_id,
                },
            )
            raise HTTPException(400, "context token does not match requested context")

        scopes = _dedupe_scopes(list(identity.get("scopes", [])))

        ctx = {
            "context_id": token_context_id,
            "identity": {
                **identity,
                "scopes": scopes,
                "context_id": token_context_id,
            },
            "trace_id": str(uuid.uuid4()),
            "global_scopes": list(identity.get("global_scopes", [])),
            "org_scopes": list(identity.get("org_scopes", [])),
            "role": identity.get("role"),
            "enterprise_enabled": enterprise_enabled,
            "scopes": scopes,
        }

        request.state.context_id = ctx["context_id"]
        request.state.scopes = scopes
        request.state.identity = ctx["identity"]
        request.state.org_role = ctx.get("role")

        audit.log(
            event="context_resolved",
            identity=ctx["identity"],
            request=request,
            metadata={
                "context_id": ctx["context_id"],
                "enterprise_enabled": enterprise_enabled,
                "header_present": bool(header_context),
                "scope_count": len(scopes),
                "role": ctx.get("role"),
                "token_type": "context",
            },
        )

        return ctx
    
    if not enterprise_enabled:
        context_id = DEFAULT_CONTEXT
    else:
        context_id = header_context or DEFAULT_CONTEXT

    ctx = {
        "context_id": context_id,
        "identity": identity,
        "trace_id": str(uuid.uuid4()),
        "global_scopes": list(identity.get("scopes", [])),
        "org_scopes": [],
        "role": None,
        "enterprise_enabled": enterprise_enabled,
    }

    ctx["context_id"] = resolve_context_id(request, ctx)

    scopes = _dedupe_scopes(list(identity.get("scopes", [])))

    ctx["identity"] = {
        **identity,
        "scopes": scopes,
        "context_id": ctx["context_id"],
    }
    ctx["scopes"] = scopes

    request.state.context_id = ctx["context_id"]
    request.state.scopes = scopes
    request.state.identity = ctx["identity"]

    audit.log(
        event="context_resolved",
        identity=ctx["identity"],
        request=request,
        metadata={
            "context_id": ctx["context_id"],
            "enterprise_enabled": enterprise_enabled,
            "header_present": bool(header_context),
            "scope_count": len(scopes),
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