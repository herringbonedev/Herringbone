from fastapi import Depends, HTTPException, status

from .user import get_current_user
from .service import get_current_service


def get_current_user_optional():
    try:
        return get_current_user()
    except Exception:
        return None


def get_current_service_optional():
    try:
        return get_current_service()
    except Exception:
        return None


def require_user_or_service_scope(required_scope: str | None = None):
    def checker(
        user=Depends(get_current_user_optional),
        service=Depends(get_current_service_optional),
    ):
        if user:
            return {
                "type": "user",
                "identity": user,
            }

        if service:
            if required_scope:
                scopes = service.get("scopes", [])
                if required_scope not in scopes:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Service missing required scope",
                    )

            return {
                "type": "service",
                "identity": service,
            }

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return checker
