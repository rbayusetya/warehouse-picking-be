from __future__ import annotations
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    name: str
    role: str
    role_label: str
    expedition: str | None = None
    dealer_code: str | None = None


class UserResponse(BaseModel):
    username: str
    name: str
    role: str
    role_label: str
    expedition: str | None = None
    dealer_code: str | None = None
