from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import jwt
import os

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================
# User JWT (HS256)
# ============================

USER_JWT_ALG = "HS256"
USER_JWT_EXPIRE_MINUTES = 60 * 24


def load_user_jwt_secret() -> str:
    env = os.environ.get("JWT_SECRET") or os.environ.get("USER_JWT_SECRET")
    if env:
        return env

    raise RuntimeError("USER_JWT_SECRET not configured (JWT_SECRET or USER_JWT_SECRET)")


def get_user_jwt_secret() -> str:
    # Lazy load to avoid startup crash if env not ready yet
    return load_user_jwt_secret()


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(password, password_hash)


def create_access_token(user_id: str, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "typ": "user",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=USER_JWT_EXPIRE_MINUTES)).timestamp()),
    }

    return jwt.encode(payload, get_user_jwt_secret(), algorithm=USER_JWT_ALG)


# ============================
# Service JWT (RS256)
# ============================

SERVICE_JWT_ALG = "RS256"
SERVICE_JWT_EXPIRE_MINUTES = 60


def load_service_private_key() -> str:
    env = os.environ.get("SERVICE_JWT_PRIVATE_KEY")
    if env:
        return env

    raise RuntimeError("SERVICE_JWT_PRIVATE_KEY not configured")


def get_service_private_key() -> str:
    # Lazy load for same reason as user secret
    return load_service_private_key()


def create_service_token(
    service_id: str,
    service_name: str,
    scopes: list[str],
) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "iss": "herringbone-auth",
        "sub": service_id,
        "service": service_name,
        "scope": scopes,
        "typ": "service",
        "aud": "herringbone-services",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=SERVICE_JWT_EXPIRE_MINUTES)).timestamp()),
    }

    return jwt.encode(payload, get_service_private_key(), algorithm=SERVICE_JWT_ALG)
