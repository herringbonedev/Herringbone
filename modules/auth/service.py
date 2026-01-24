import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

SERVICE_JWT_ALG = "RS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/service-token")


def load_service_public_key() -> str:
    env = os.environ.get("SERVICE_JWT_PUBLIC_KEY")
    if env:
        return env

    raise RuntimeError("Service JWT public key not configured (SERVICE_JWT_PUBLIC_KEY)")


def get_current_service(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        public_key = load_service_public_key()  # lazy load at runtime

        payload = jwt.decode(
            token,
            public_key,
            algorithms=[SERVICE_JWT_ALG],
            audience="herringbone-services",  # matches security.py
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired service token",
        )

    if payload.get("typ") != "service":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return {
        "service_id": payload.get("sub"),
        "service": payload.get("service"),
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
