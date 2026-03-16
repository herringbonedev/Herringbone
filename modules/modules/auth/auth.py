from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jose import jwt
import uuid

from modules.audit.logger import AuditLogger


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

    context_id = payload.get("context_id") or DEFAULT_CONTEXT

    identity = {
        "type": identity_type,
        "scopes": payload.get("scope", []),
        "context_id": context_id,
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


def require_scopes(scope_sets):

    if isinstance(scope_sets, str):
        scope_sets = [(scope_sets,)]

    def checker(identity: dict = Depends(get_identity)):

        audit = AuditLogger()

        scopes = set(identity.get("scopes", []))

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
            metadata={"required_scopes": scope_sets},
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return checker


def resolve_context(request: Request, identity):

    header_context = request.headers.get("X-Herringbone-Org")

    if header_context:
        return header_context

    if identity and identity.get("context_id"):
        return identity["context_id"]

    return DEFAULT_CONTEXT


def get_context(
    request: Request,
    identity=Depends(get_identity),
):

    context_id = resolve_context(request, identity)

    return {
        "context_id": context_id,
        "identity": identity,
        "trace_id": str(uuid.uuid4()),
    }
