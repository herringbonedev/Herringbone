from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/login")


def service_or_user(required_service_scope: str | None = None):
    async def checker(token: str = Depends(oauth2_scheme)):
        # Try service token first
        service = _try_service(token)
        if service:
            if required_service_scope and required_service_scope not in service.get("scopes", []):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Service missing required scope",
                )
            return {"type": "service", "identity": service}

        # Try user token
        user = _try_user(token)
        if user:
            return {"type": "user", "identity": user}

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return checker


def _try_service(token: str):
    try:
        from modules.auth.service import (
            get_service_public_key,
            SERVICE_JWT_ALG,
            SERVICE_JWT_AUD,
        )

        payload = jwt.decode(
            token,
            get_service_public_key(),
            algorithms=[SERVICE_JWT_ALG],
            audience=SERVICE_JWT_AUD,
        )

        if payload.get("typ") != "service":
            return None

        return {
            "service_id": payload.get("sub"),
            "service": payload.get("service"),
            "scopes": payload.get("scope", []),
        }

    except Exception:
        return None


def _try_user(token: str):
    try:
        from modules.auth.user import get_user_jwt_secret, JWT_ALG

        secret = get_user_jwt_secret()

        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALG],
        )

        if payload.get("typ") != "user":
            return None

        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role"),
        }

    except Exception:
        return None
