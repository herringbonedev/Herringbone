import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

JWT_ALG = os.environ.get("JWT_ALG", "HS256")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/login")


def is_auth_enabled() -> bool:
    return os.environ.get("AUTH_ENABLED", "false").lower() == "true"


def load_user_jwt_secret() -> str:
    env = os.environ.get("JWT_SECRET") or os.environ.get("USER_JWT_SECRET")
    if env:
        return env
    raise RuntimeError("User JWT secret not configured (JWT_SECRET)")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    # Bootstrap mode → fake admin user
    if not is_auth_enabled():
        return {
            "id": "bootstrap",
            "email": "bootstrap@local",
            "role": "admin",
            "bootstrap": True,
        }

    try:
        secret = load_user_jwt_secret()
        payload = jwt.decode(token, secret, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("typ") != "user":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
    }


def require_role(required_role: str):
    def checker(user: dict = Depends(get_current_user)):
        if user.get("bootstrap"):
            return user

        if user.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return checker


def require_admin(user: dict = Depends(get_current_user)):
    if user.get("bootstrap"):
        return user

    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user
