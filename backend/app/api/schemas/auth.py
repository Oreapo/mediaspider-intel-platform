from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=160)


class AuthUserResponse(BaseModel):
    username: str
    role: str
    display_name: str


class LoginResponse(BaseModel):
    token: str
    user: AuthUserResponse
    token_type: str = "bearer"
