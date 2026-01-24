# modules/auth/service.py

import os
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

SERVICE_JWT_PRIVATE_KEY = os.environ.get("SERVICE_JWT_PRIVATE_KEY")
SERVICE_JWT_PUBLIC_KEY = os.environ.get("SERVICE_JWT_PUBLIC_KEY")
SERVICE_JWT_ALG = os.environ.get("SERVICE_JWT_ALG", "RS256")

if not SERVICE_JWT_PUBLIC_KEY:
    raise RuntimeError("SERVICE_JWT_PUBLIC_KEY not set")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/herringbone/auth/service-token"
)

def create_service_token(
    service_id: str,
    service_name: str,
    scopes: list[str],
    expires_minutes: int = 60,
):
    now = datetime.utcnow()
    payload = {
        "iss": "herringbone-auth",
        "sub": service_id,
        "service": service_name,
        "scope": scopes,
        "typ": "service",
        "aud": "herringbone-services",
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }

    return jwt.encode(payload, SERVICE_JWT_PRIVATE_KEY, algorithm=SERVICE_JWT_ALG)

def get_current_service(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(
            token,
            SERVICE_JWT_PUBLIC_KEY,
            algorithms=[SERVICE_JWT_ALG],
            audience="herringbone-services",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired service token",
        )

    if payload.get("typ") != "service":
        raise HTTPException(401, "Invalid token type")

    return {
        "service_id": payload.get("sub"),
        "service_name": payload.get("service"),
        "scopes": payload.get("scope", []),
    }

def require_service_scope(required_scope: str):
    def checker(service: dict = Depends(get_current_service)):
        if required_scope not in service.get("scopes", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Service does not have required scope",
            )
        return service
    return checker
