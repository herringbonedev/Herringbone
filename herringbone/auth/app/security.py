from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import jwt
import os

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_ALG = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24

def load_jwt_secret() -> str:
    secret_path = "/run/secrets/jwt_secret"

    if os.path.exists(secret_path):
        with open(secret_path, "r") as f:
            return f.read().strip()
    
    env_secret = os.environ.get("JWT_SECRET")
    if env_secret:
        return env_secret

    raise RuntimeError("JWT secret not configured")

JWT_SECRET = load_jwt_secret()

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
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def create_service_token(service_name: str, scopes: list[str] | None = None) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "svc": service_name,
        "scope": scopes or [],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MINUTES)).timestamp()),
        "type": "service",
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def verify_service_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])

        if payload.get("type") != "service":
            return None

        if "svc" not in payload:
            return None

        return payload
    except Exception:
        return None
