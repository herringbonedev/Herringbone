from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

SERVICE_JWT_ALG = "RS256"
SERVICE_JWT_AUD = "herringbone-services"

SERVICE_JWT_PUBLIC_KEY_PATH = "/run/secrets/service_jwt_public_key"
SERVICE_TOKEN_PATH = "/run/secrets/service_token"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/herringbone/auth/service-token")

_service_public_key: str | None = None
_service_token: str | None = None


def _load_public_key() -> str:
    try:
        with open(SERVICE_JWT_PUBLIC_KEY_PATH, "r") as f:
            key = f.read().strip()
    except FileNotFoundError:
        raise RuntimeError(f"Service JWT public key file not found: {SERVICE_JWT_PUBLIC_KEY_PATH}")

    if not key:
        raise RuntimeError(f"Service JWT public key file empty: {SERVICE_JWT_PUBLIC_KEY_PATH}")

    return key


def get_service_public_key() -> str:
    global _service_public_key
    if _service_public_key is None:
        _service_public_key = _load_public_key()
    return _service_public_key


def get_current_service(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(
            token,
            get_service_public_key(),
            algorithms=[SERVICE_JWT_ALG],
            audience=SERVICE_JWT_AUD,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired service token",
        )

    if payload.get("typ") != "service":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return {
        "service_id": payload.get("sub"),
        "service": payload.get("service"),
        "scopes": payload.get("scope", []),
    }


def require_service_scope(required_scope: str):
    def checker(service: dict = Depends(get_current_service)):
        if required_scope not in service.get("scopes", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Service does not have required scope",
            )
        return service

    return checker


def _load_service_token() -> str:
    try:
        with open(SERVICE_TOKEN_PATH, "r") as f:
            token = f.read().strip()
    except FileNotFoundError:
        raise RuntimeError(f"Service token file not found: {SERVICE_TOKEN_PATH}")

    if not token:
        raise RuntimeError(f"Service token file empty: {SERVICE_TOKEN_PATH}")

    return token


def get_service_token() -> str:
    global _service_token
    if _service_token is None:
        _service_token = _load_service_token()
    return _service_token


def service_auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {get_service_token()}",
    }
