from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

JWT_ALG = "HS256"
USER_JWT_SECRET_PATH = "/run/secrets/jwt_secret"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/login", auto_error=False)

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


def decode_user_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        get_user_jwt_secret(),
        algorithms=[JWT_ALG],
    )

    if payload.get("typ") != "user":
        raise JWTError("Invalid token type")

    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
    }


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        return decode_user_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def get_current_user_optional(token: str | None = Depends(oauth2_scheme_optional)) -> dict | None:
    if not token:
        return None

    try:
        return decode_user_token(token)
    except JWTError:
        return None


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
