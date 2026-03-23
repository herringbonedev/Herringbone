from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
import os

DEFAULT_CONTEXT = "default"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/login")

def is_enterprise_enabled():
    return os.environ.get("HB_ENTERPRISE", "false").lower() == "true"

def decode_token(token):
    payload = jwt.decode(token, os.environ.get("JWT_SECRET"), algorithms=["HS256"])
    return payload

def get_identity(token: str = Depends(oauth2_scheme)):
    return decode_token(token)

def get_context(request: Request, identity=Depends(get_identity)):
    context_id = identity.get("context_id", DEFAULT_CONTEXT)
    enterprise = is_enterprise_enabled()

    if not enterprise:
        context_id = DEFAULT_CONTEXT

    return {
        "context_id": context_id,
        "identity": identity,
        "scopes": identity.get("scope", []),
        "enterprise_enabled": enterprise,
    }

def require_scopes(required):
    if isinstance(required, str):
        required = [required]

    def checker(ctx=Depends(get_context)):
        scopes = set(ctx.get("scopes", []))
        if "*" in scopes or all(r in scopes for r in required):
            return ctx["identity"]
        raise HTTPException(403, "Forbidden")

    return checker
