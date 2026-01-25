from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import jwt

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

USER_JWT_SECRET_PATH = "/run/secrets/jwt_secret"
SERVICE_JWT_PRIVATE_KEY_PATH = "/run/secrets/service_jwt_private_key"

_user_jwt_secret: str | None = None
_service_private_key: str | None = None


def _load_secret_file(path: str) -> str:
    try:
        with open(path, "r") as f:
            value = f.read().strip()
    except FileNotFoundError:
        raise RuntimeError(f"Secret file not found: {path}")

    if not value:
        raise RuntimeError(f"Secret file empty: {path}")

    return value


# ============================
# User JWT (HS256)
# ============================

USER_JWT_ALG = "HS256"
USER_JWT_EXPIRE_MINUTES = 60 * 24


def get_user_jwt_secret() -> str:
    global _user_jwt_secret
    if _user_jwt_secret is None:
        _user_jwt_secret = _load_secret_file(USER_JWT_SECRET_PATH)
    return _user_jwt_secret


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


def get_service_private_key() -> str:
    global _service_private_key
    if _service_private_key is None:
        _service_private_key = _load_secret_file(SERVICE_JWT_PRIVATE_KEY_PATH)
    return _service_private_key


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
