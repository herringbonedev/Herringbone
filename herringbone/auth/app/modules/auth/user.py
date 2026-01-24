import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

JWT_SECRET_PATH = "/run/secrets/jwt_secret"
JWT_ALG = os.environ.get("JWT_ALG", "HS256")


def load_user_jwt_secret():
    if os.path.exists(JWT_SECRET_PATH):
        with open(JWT_SECRET_PATH, "r") as f:
            return f.read().strip()

    env = os.environ.get("JWT_SECRET") or os.environ.get("USER_JWT_SECRET")
    if env:
        return env

    raise RuntimeError("User JWT secret not configured")


USER_JWT_SECRET = load_user_jwt_secret()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, USER_JWT_SECRET, algorithms=[JWT_ALG])
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
        if user.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return checker


def require_admin(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
