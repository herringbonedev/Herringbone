from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jose import jwt
import uuid

JWT_ALG_USER = "HS256"
JWT_ALG_SERVICE = "RS256"

USER_SECRET_PATH = "/run/secrets/jwt_secret"
SERVICE_PUBLIC_KEY_PATH = "/run/secrets/service_jwt_public_key"
SERVICE_TOKEN_PATH = "/run/secrets/service_token"

SERVICE_AUD = "herringbone-services"

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


def decode_token(token):

    try:
        payload = jwt.decode(
            token,
            get_user_secret(),
            algorithms=[JWT_ALG_USER],
        )

        if payload.get("typ") == "user":
            return {
                "type": "user",
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "scopes": payload.get("scope", []),
                "context_id": payload.get("context_id", "default"),
            }

    except Exception:
        pass

    try:
        payload = jwt.decode(
            token,
            get_service_public_key(),
            algorithms=[JWT_ALG_SERVICE],
            audience=SERVICE_AUD,
        )

        if payload.get("typ") == "service":
            return {
                "type": "service",
                "service": payload.get("service"),
                "service_id": payload.get("sub"),
                "scopes": payload.get("scope", []),
                "context_id": payload.get("context_id", "default"),
            }

    except Exception:
        pass

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

        scopes = set(identity.get("scopes", []))

        if "*" in scopes:
            return identity

        for scope_set in scope_sets:
            if all(scope in scopes for scope in scope_set):
                return identity

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return checker


def get_context(identity=Depends(get_identity)):

    context_id = "default"

    if identity:
        context_id = identity.get("context_id", "default")

    return {
        "context_id": context_id,
        "identity": identity,
        "trace_id": str(uuid.uuid4()),
    }