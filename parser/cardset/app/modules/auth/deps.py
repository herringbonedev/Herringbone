import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() == "true"

JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALG = os.environ.get("JWT_ALG", "HS256")

if AUTH_ENABLED and not JWT_SECRET:
    raise RuntimeError("JWT_SECRET not set")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/herringbone/auth/login",
    auto_error=AUTH_ENABLED,
)


def _no_auth_user():
    return {
        "id": "local-dev",
        "email": "no-auth@local",
        "role": "admin",
    }


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    if not AUTH_ENABLED:
        return _no_auth_user()

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
    }


def require_role(required_role: str):
    def checker(user: dict = Depends(get_current_user)):
        if not AUTH_ENABLED:
            return user

        if user.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return checker


def require_admin(user: dict = Depends(get_current_user)):
    if not AUTH_ENABLED:
        return user

    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user
