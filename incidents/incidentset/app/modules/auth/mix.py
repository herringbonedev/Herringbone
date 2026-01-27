from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/login")


def service_or_user(required_service_scope: str | None = None):
    """
    Allow:
      - service token WITH scope
      - OR any valid user token
    """
    async def checker(token: str = Depends(oauth2_scheme)):
        service = _try_service(token)
        if service:
            _enforce_scope(service, required_service_scope)
            return {"type": "service", "identity": service}

        user = _try_user(token)
        if user:
            return {"type": "user", "identity": user}

        raise _unauthorized()

    return checker


def service_or_role(required_service_scope: str, allowed_roles: list[str]):
    """
    Allow:
      - service token WITH scope
      - OR user token WITH role in allowed_roles
    """
    async def checker(token: str = Depends(oauth2_scheme)):
        service = _try_service(token)
        if service:
            _enforce_scope(service, required_service_scope)
            return {"type": "service", "identity": service}

        user = _try_user(token)
        if user:
            if user.get("role") not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User role not permitted",
                )
            return {"type": "user", "identity": user}

        raise _unauthorized()

    return checker


def _enforce_scope(service: dict, scope: str | None):
    if scope and scope not in service.get("scopes", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service missing required scope",
        )


def _unauthorized():
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


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

        payload = jwt.decode(
            token,
            get_user_jwt_secret(),
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
