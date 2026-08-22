import os, secrets
from datetime import datetime, UTC
from typing import Optional
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.auth import (
    require_scopes,
    get_identity,
    get_identity_optional,
    get_context
)

from modules.audit import AuditLogger

from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_context_token,
)

from app.schemas import (
    UserProfileUpdateRequest
)

router = APIRouter(prefix="/herringbone/auth/user_profile", tags=["profile"])

identity = Depends(get_identity)
admin = Depends(require_scopes("platform:admin"))


def get_mongo():
    return HerringboneMongoDatabase(
        user=os.environ.get("MONGO_USER", "admin"),
        password=os.environ.get("MONGO_PASS", "secret"),
        database=os.environ.get("DB_NAME", "herringbone"),
        host=os.environ.get("MONGO_HOST", "localhost"),
        port=int(os.environ.get("MONGO_PORT", 27017)),
        auth_source=os.environ.get("AUTH_DB", "herringbone"),
    )


def get_audit_logger():
    return AuditLogger(get_mongo())


@router.get("/get")
async def list_users(
    request: Request,
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    print(identity)
    print(context)


@router.get("/set")
async def list_users(
    request: Request,
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    print(identity)
    print(context)