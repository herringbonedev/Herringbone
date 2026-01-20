import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() == "true"

JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALG = os.environ.get("JWT_ALG", "HS256")

print("[*] auth deps loaded")

if AUTH_ENABLED:
    print("[*] AUTH_ENABLED = true")
else:
    print("[*] AUTH_ENABLED = false")

if AUTH_ENABLED and not JWT_SECRET:
    print("[✗] JWT_SECRET missing")
    raise RuntimeError("JWT_SECRET not set")

if JWT_SECRET:
    print("[✓] JWT_SECRET = set")

print(f"[*] JWT_ALG = {JWT_ALG}")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/herringbone/auth/login",
    auto_error=AUTH_ENABLED,
)


def _no_auth_user():
    return {
        "id": "local-dev",
        "email": "no-auth@local",
        "role": "admin",
        "typ": "no-auth",
    }


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError as e:
        print("[✗] JWT decode failed:", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    if not AUTH_ENABLED:
        print("[*] auth disabled → allowing request")
        return _no_auth_user()

    payload = _decode_token(token)

    typ = payload.get("typ", "user")

    user = {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
        "typ": typ,
        "service": payload.get("service"),
        "instance_id": payload.get("instance_id"),
        "version": payload.get("version"),
    }

    if typ == "service":
        print(f"[✓] service auth: {payload.get('service')} ({payload.get('instance_id')})")
    else:
        print(f"[✓] user auth: {payload.get('email')} ({payload.get('role')})")

    return user


def require_role(required_role: str):
    def checker(user: dict = Depends(get_current_user)):
        if not AUTH_ENABLED:
            return user

        # allow services through
        if user.get("typ") == "service":
            return user

        if user.get("role") != required_role:
            print("[✗] role check failed:", user.get("role"), "required:", required_role)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return user

    return checker


def require_admin(user: dict = Depends(get_current_user)):
    if not AUTH_ENABLED:
        return user

    # allow services
    if user.get("typ") == "service":
        return user

    if user.get("role") != "admin":
        print("[✗] admin required, got:", user.get("role"))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user
