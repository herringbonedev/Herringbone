from fastapi import Depends, HTTPException, status

from modules.auth.user import get_current_user
from modules.auth.service import get_current_service, require_service_scope

from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/login")


def service_or_user(required_service_scope: str | None = None):
    async def checker(token: str = Depends(_raw_bearer_token)):
        # Try service auth first
        try:
            service = await _try_service(token)
            if required_service_scope:
                if required_service_scope not in service.get("scopes", []):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Service missing required scope",
                    )
            return {
                "type": "service",
                "identity": service,
            }
        except Exception:
            pass

        # Try user auth
        try:
            user = await _try_user(token)
            return {
                "type": "user",
                "identity": user,
            }
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return checker

async def _raw_bearer_token(token: str = Depends(oauth2_scheme)) -> str:
    return token


async def _try_service(token: str):
    from modules.auth.service import get_service_public_key, SERVICE_JWT_ALG, SERVICE_JWT_AUD
    from jose import jwt

    payload = jwt.decode(
        token,
        get_service_public_key(),
        algorithms=[SERVICE_JWT_ALG],
        audience=SERVICE_JWT_AUD,
    )

    if payload.get("typ") != "service":
        raise Exception()

    return {
        "service_id": payload.get("sub"),
        "service": payload.get("service"),
        "scopes": payload.get("scope", []),
    }


async def _try_user(token: str):
    from modules.auth.user import get_user_jwt_secret, JWT_ALG
    from jose import jwt

    payload = jwt.decode(
        token,
        get_user_jwt_secret(),
        algorithms=[JWT_ALG],
    )

    if payload.get("typ") != "user":
        raise Exception()

    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
    }
