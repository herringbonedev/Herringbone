import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALG = os.environ.get("JWT_ALG", "HS256")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET not set")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/herringbone/auth/login"
)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
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
