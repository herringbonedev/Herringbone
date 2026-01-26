from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

JWT_ALG = "HS256"

USER_JWT_SECRET_PATH = "/run/secrets/jwt_secret"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/login")

_user_jwt_secret: str | None = None


def _load_user_jwt_secret() -> str:
    try:
        with open(USER_JWT_SECRET_PATH, "r") as f:
            secret = f.read().strip()
    except FileNotFoundError:
        raise RuntimeError(f"User JWT secret file not found: {USER_JWT_SECRET_PATH}")

    if not secret:
        raise RuntimeError(f"User JWT secret file empty: {USER_JWT_SECRET_PATH}")

    return secret


def get_user_jwt_secret() -> str:
    global _user_jwt_secret
    if _user_jwt_secret is None:
        _user_jwt_secret = _load_user_jwt_secret()
    return _user_jwt_secret


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(
            token,
            get_user_jwt_secret(),
            algorithms=[JWT_ALG],
        )
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


def require_role(required_roles: str | list[str]):
    if isinstance(required_roles, str):
        required_roles = [required_roles]

    def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions (requires one of: {required_roles})",
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
