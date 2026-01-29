import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr, Field

from modules.database.mongo_db import HerringboneMongoDatabase
from modules.auth.user import require_admin, get_current_user, get_current_user_optional
from security import (
	hash_password,
	verify_password,
	create_access_token,
	create_service_token,
)

router = APIRouter(prefix="/herringbone/auth", tags=["auth"])


def get_mongo():
	return HerringboneMongoDatabase(
		user=os.environ.get("MONGO_USER", "admin"),
		password=os.environ.get("MONGO_PASS", "secret"),
		database=os.environ.get("DB_NAME", "herringbone"),
		host=os.environ.get("MONGO_HOST", "localhost"),
		port=int(os.environ.get("MONGO_PORT", 27017)),
		auth_source=os.environ.get("AUTH_DB", "herringbone"),
	)


def load_bootstrap_token() -> Optional[str]:
	path = os.environ.get("BOOTSTRAP_TOKEN_FILE")
	if path and os.path.exists(path):
		with open(path, "r") as f:
			return f.read().strip()
	return os.environ.get("BOOTSTRAP_TOKEN")


def is_bootstrap_required(mongo: HerringboneMongoDatabase) -> bool:
	try:
		return len(mongo.find("users", {})) == 0
	except Exception:
		return True


class RegisterRequest(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
	email: EmailStr
	password: str


class ServiceTokenRequest(BaseModel):
	service: str
	scopes: list[str] = []


class ServiceRegisterRequest(BaseModel):
	service_name: str
	scopes: list[str] = []
	

class ServiceScopeUpdateRequest(BaseModel):
    service_name: str
    scopes: list[str]


class UserRoleUpdateRequest(BaseModel):
    email: EmailStr
    role: str


class UserDeleteRequest(BaseModel):
    email: EmailStr


@router.post("/register")
async def register_user(
    payload: RegisterRequest,
    request: Request,
    current_user: dict | None = Depends(get_current_user_optional),
):
    mongo = get_mongo()

    bootstrap_required = is_bootstrap_required(mongo)

    # Bootstrap path (first user)
    if bootstrap_required:
        expected = load_bootstrap_token()
        provided = request.headers.get("x-bootstrap-token")

        if not expected or not provided or provided != expected:
            raise HTTPException(
                status_code=403,
                detail="Bootstrap token required for first user",
            )
    
    # Normal path (admin only)
    else:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")

        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin privileges required")
    
    # Create user
    if mongo.find_one("users", {"email": payload.email}):
        raise HTTPException(status_code=400, detail="User already exists")

    user_count = len(mongo.find("users", {}))
    role = "admin" if user_count == 0 else "analyst"

    user_doc = {
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "role": role,
        "created_at": datetime.utcnow(),
    }

    user_id = mongo.insert_one("users", user_doc)

    if role == "admin":
        try:
            mongo.insert_one(
                "audit_log",
                {
                    "event": "bootstrap_admin_created",
                    "email": payload.email,
                    "ip": request.client.host if request.client else None,
                    "ts": datetime.utcnow(),
                },
            )
        except Exception:
            pass

    return {
        "ok": True,
        "user_id": str(user_id),
        "role": role,
    }


@router.post("/login")
async def login_user(payload: LoginRequest):
	mongo = get_mongo()

	user = mongo.find_one("users", {"email": payload.email})
	if not user:
		raise HTTPException(status_code=401, detail="Invalid credentials")

	if not verify_password(payload.password, user["password_hash"]):
		raise HTTPException(status_code=401, detail="Invalid credentials")

	token = create_access_token(
		user_id=str(user["_id"]),
		email=user["email"],
		role=user["role"],
	)

	return {
		"access_token": token,
		"token_type": "bearer",
	}


@router.get("/users")
async def list_users(user=Depends(get_current_user)):
	mongo = get_mongo()
	users = mongo.find("users", {})

	return {
		"count": len(users),
		"users": [
			{
				"email": u.get("email"),
				"role": u.get("role"),
			}
			for u in users
		],
	}


@router.get("/scopes")
async def list_scopes(user=Depends(get_current_user)):
	mongo = get_mongo()
	scopes = mongo.find("scopes", {})

	return {
		"scopes": [
			{
				"scope": s.get("scope"),
				"tier": s.get("tier", "free"),
			}
			for s in scopes
		]
	}


@router.post("/services/register")
async def register_service(
	payload: ServiceRegisterRequest,
	user=Depends(require_admin),
):
	mongo = get_mongo()

	if mongo.find_one("service_accounts", {"service_name": payload.service_name}):
		raise HTTPException(status_code=400, detail="Service already exists")

	svc_doc = {
		"service_name": payload.service_name,
		"service_id": payload.service_name,
		"scopes": payload.scopes,
		"enabled": True,
		"created_at": datetime.utcnow(),
	}

	svc_id = mongo.insert_one("service_accounts", svc_doc)

	return {
		"ok": True,
		"service_id": str(svc_id),
		"service_name": payload.service_name,
	}


@router.get("/services")
async def list_services(user=Depends(require_admin)):
	mongo = get_mongo()
	services = mongo.find("service_accounts", {})

	result = []
	for s in services:
		result.append(
			{
				"id": str(s.get("_id")),
				"service_name": s.get("service_name"),
				"service_id": s.get("service_id"),
				"scopes": s.get("scopes", []),
				"enabled": s.get("enabled", True),
				"created_at": s.get("created_at"),
			}
		)

	return {
		"count": len(result),
		"services": result,
	}


@router.post("/service-token")
async def create_service_token_api(
	payload: ServiceTokenRequest,
	user=Depends(require_admin),
):
	mongo = get_mongo()

	svc = mongo.find_one(
		"service_accounts",
		{
			"service_name": payload.service,
			"enabled": True,
		},
	)

	if not svc:
		raise HTTPException(
			status_code=404,
			detail="Service not found or disabled",
		)

	token = create_service_token(
		service_id=str(svc["_id"]),
		service_name=svc["service_name"],
		scopes=payload.scopes,
	)

	return {
		"access_token": token,
		"token_type": "bearer",
	}


@router.delete("/services/{service_name}")
async def delete_service(service_name: str, user=Depends(require_admin)):
    mongo = get_mongo()

    svc = mongo.find_one("service_accounts", {"service_name": service_name})
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    mongo.delete_one("service_accounts", {"_id": svc["_id"]})

    return {"ok": True, "deleted": service_name}


@router.post("/services/scopes/remove")
async def remove_service_scopes(
    payload: ServiceScopeUpdateRequest,
    user=Depends(require_admin),
):
    mongo = get_mongo()

    svc = mongo.find_one("service_accounts", {"service_name": payload.service_name})
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    mongo.update_one(
        "service_accounts",
        {"_id": svc["_id"]},
        {
            "$pull": {
                "scopes": {"$in": payload.scopes}
            }
        },
    )

    return {"ok": True, "service": payload.service_name, "removed": payload.scopes}


@router.post("/users/role")
async def change_user_role(
    payload: UserRoleUpdateRequest,
    user=Depends(require_admin),
):
    mongo = get_mongo()

    target = mongo.find_one("users", {"email": payload.email})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.get("role") == "admin" and payload.role != "admin":
        admins = mongo.find("users", {"role": "admin"})
        if len(admins) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove role from last admin user",
            )

    mongo.update_one(
        "users",
        {"_id": target["_id"]},
        {"$set": {"role": payload.role}},
    )

    return {"ok": True, "email": payload.email, "role": payload.role}


@router.delete("/users")
async def delete_user(
    payload: UserDeleteRequest,
    user=Depends(require_admin),
):
    mongo = get_mongo()

    target = mongo.find_one("users", {"email": payload.email})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.get("role") == "admin":
        raise HTTPException(
            status_code=400,
            detail="Admin users cannot be deleted",
        )

    mongo.delete_one("users", {"_id": target["_id"]})

    return {"ok": True, "deleted": payload.email}


@router.get("/healthz")
async def healthz():
	return {"ok": True, "service": "herringbone-auth"}


@router.get("/readyz")
async def db_check():
	db = get_mongo()
	client, mongo_db = db.open_mongo_connection()
	cols = mongo_db.list_collection_names()
	db.close_mongo_connection()
	return {"ok": True, "collections": cols}
