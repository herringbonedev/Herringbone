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