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


from jose.exceptions import ExpiredSignatureError


def decode_token(token):
    audit = AuditLogger()

    try:
        payload = jwt.decode(
            token,
            get_user_secret(),
            algorithms=[JWT_ALG_USER],
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

    except ExpiredSignatureError:
        audit.log(
            event="auth_token_expired",
            result="failure",
            severity="WARNING",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )

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


def _dedupe_scopes(scopes):
    return list(dict.fromkeys(scopes))


def get_context(request: Request, identity=Depends(get_identity)):
    enterprise_enabled = is_enterprise_enabled()

    header_context = (
        request.headers.get("X-Context-Id")
        or request.headers.get("X-Herringbone-Org")
        or request.headers.get("X-Herringbone-Context")
    )

    token_context_id = str(identity.get("context_id") or DEFAULT_CONTEXT)

    if not enterprise_enabled:
        token_context_id = DEFAULT_CONTEXT

    if header_context and str(header_context) != token_context_id:
        raise HTTPException(400, "context mismatch")

    effective_scopes = _dedupe_scopes(
        list(identity.get("global_scopes", [])) +
        list(identity.get("org_scopes", [])) +
        list(identity.get("scopes", []))
    )

    ctx = {
        "context_id": token_context_id,
        "identity": identity,
        "scopes": effective_scopes,
        "enterprise_enabled": enterprise_enabled,
    }

    request.state.context_id = token_context_id
    request.state.scopes = effective_scopes
    request.state.identity = identity

    return ctx


def require_scopes(required):
    if isinstance(required, str):
        required = [required]

    def checker(ctx=Depends(get_context)):
        scopes = set(ctx.get("scopes", []))
        if "*" in scopes or all(r in scopes for r in required):
            return ctx["identity"]
        raise HTTPException(403, "Forbidden")

    return checker
