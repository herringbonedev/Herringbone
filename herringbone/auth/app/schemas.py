from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    scopes: Optional[list[str]] = None


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


class UserDeleteRequest(BaseModel):
    email: EmailStr


class UserScopesUpdateRequest(BaseModel):
    email: EmailStr
    scopes: list[str]


class OrgMemberUpsertRequest(BaseModel):
    email: EmailStr
    role: str = "member"
    scopes: Optional[list[str]] = None

class UserProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_name: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    team: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    timezone: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    website: Optional[str] = None
    bio: Optional[str] = None