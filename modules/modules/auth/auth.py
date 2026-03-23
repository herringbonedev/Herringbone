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
    with open(path, "r") as f:
        return f.read().strip()

def is_enterprise_enabled():
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

def _normalize_scope_value(v):
    if isinstance(v, str):
        return v.split()
    if isinstance(v, list):
        return v
    return []

def decode_token(token):
    return jwt.decode(token, get_user_secret(), algorithms=[JWT_ALG_USER])

def get_identity(token: str = Depends(oauth2_scheme)):
    return decode_token(token)

def _dedupe(scopes):
    return list(dict.fromkeys(scopes))

def get_context(request: Request, identity=Depends(get_identity)):
    enterprise = is_enterprise_enabled()

    header_context = (
        request.headers.get("X-Context-Id")
        or request.headers.get("X-Herringbone-Org")
        or request.headers.get("X-Herringbone-Context")
    )

    token_context = str(identity.get("context_id") or DEFAULT_CONTEXT)

    if not enterprise:
        token_context = DEFAULT_CONTEXT

    if header_context and str(header_context) != token_context:
        raise HTTPException(400, "context mismatch")

    scopes = _dedupe(identity.get("scope", []))

    ctx = {
        "context_id": token_context,
        "identity": identity,
        "scopes": scopes,
        "enterprise_enabled": enterprise,
    }

    request.state.context_id = token_context
    request.state.scopes = scopes
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
