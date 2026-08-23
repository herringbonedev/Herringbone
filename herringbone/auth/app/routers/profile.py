import os

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request

from modules.audit import AuditLogger
from modules.auth.auth import get_context
from modules.database.mongo_db import HerringboneMongoDatabase

from app.schemas import UserProfileUpdateRequest


router = APIRouter(prefix="/herringbone/auth/user_profile", tags=["profile"])


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


def get_user_id(identity):
    try:
        return ObjectId(identity["id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid user identity",
        )


def validate_org_membership(
    mongo,
    user_id,
    context_id,
):
    try:
        org_id = ObjectId(context_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid context_id",
        )

    member = mongo.find_one_with_context(
        "organization_members",
        {
            "user_id": user_id,
            "org_id": org_id,
            "status": "active",
        },
        context_id=context_id,
    )

    if not member:
        raise HTTPException(
            status_code=404,
            detail="User is not a member of this organization",
        )

    return member


@router.get("/get")
async def get_user_profile(
    request: Request,
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    mongo = get_mongo()
    context_id = context.get("context_id")
    enterprise_enabled = context.get("enterprise_enabled", False)

    try:
        user_id = get_user_id(identity)

        if enterprise_enabled and context_id and context_id != "default":
            validate_org_membership(
                mongo,
                user_id,
                context_id,
            )

        user = mongo.find_one_with_context(
            "users",
            {"_id": user_id},
            context_id="default",
        )

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        if "profile" not in user:
            audit.log(
                event="get_user_profile_failed",
                identity=identity,
                result="failure",
                severity="WARNING",
                metadata={
                    "email": identity.get("email"),
                    "reason": "profile_not_found",
                    "context_id": context_id,
                },
                request=request,
            )

            raise HTTPException(
                status_code=404,
                detail="User profile not found",
            )

        audit.log(
            event="get_user_profile_success",
            identity=identity,
            result="success",
            severity="INFO",
            metadata={
                "email": identity.get("email"),
                "context_id": context_id,
            },
            request=request,
        )

        return {
            "ok": True,
            "email": identity.get("email"),
            "profile": user["profile"],
        }

    except HTTPException:
        raise

    except Exception as e:
        audit.log(
            event="get_user_profile_failed",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={
                "email": identity.get("email"),
                "context_id": context_id,
                "error": str(e),
            },
            request=request,
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.post("/set")
async def set_user_profile(
    payload: UserProfileUpdateRequest,
    request: Request,
    context=Depends(get_context),
    audit: AuditLogger = Depends(get_audit_logger),
):
    identity = context["identity"]
    mongo = get_mongo()
    context_id = context.get("context_id")
    enterprise_enabled = context.get("enterprise_enabled", False)
    profile = payload.model_dump(exclude_unset=True)

    try:
        user_id = get_user_id(identity)

        user = mongo.find_one_with_context(
            "users",
            {"_id": user_id},
            context_id="default",
        )

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        if enterprise_enabled and context_id and context_id != "default":
            try:
                validate_org_membership(
                    mongo,
                    user_id,
                    context_id,
                )
            except HTTPException as e:
                if e.status_code == 404:
                    audit.log(
                        event="user_profile_update_denied",
                        identity=identity,
                        result="failure",
                        severity="WARNING",
                        metadata={
                            "email": identity.get("email"),
                            "context_id": context_id,
                            "reason": "membership_not_found",
                        },
                        request=request,
                    )
                raise

        mongo.update_one(
            "users",
            {"_id": user_id},
            {
                "$set": {
                    "profile": profile,
                }
            },
            context_id="default",
        )

        audit.log(
            event="set_user_profile_success",
            identity=identity,
            result="success",
            severity="INFO",
            metadata={
                "email": identity.get("email"),
                "context_id": context_id,
                "mode": (
                    "org"
                    if enterprise_enabled
                    and context_id
                    and context_id != "default"
                    else "default"
                ),
            },
            request=request,
        )

        return {
            "ok": True,
            "email": identity.get("email"),
            "profile": profile,
        }

    except HTTPException:
        raise

    except Exception as e:
        audit.log(
            event="set_user_profile_failed",
            identity=identity,
            result="failure",
            severity="WARNING",
            metadata={
                "email": identity.get("email"),
                "context_id": context_id,
                "error": str(e),
            },
            request=request,
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )