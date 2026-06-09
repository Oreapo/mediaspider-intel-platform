from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_auth_service, require_user
from ..schemas.auth import AuthUserResponse, LoginRequest, LoginResponse
from ...application.auth_service import AuthService, AuthUser


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, service: AuthService = Depends(get_auth_service)):
    try:
        token, user = service.login(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return LoginResponse(
        token=token,
        user=AuthUserResponse(username=user.username, role=user.role, display_name=user.display_name),
    )


@router.get("/me", response_model=AuthUserResponse)
def me(user: AuthUser = Depends(require_user)):
    return AuthUserResponse(username=user.username, role=user.role, display_name=user.display_name)


@router.post("/logout")
def logout():
    return {"message": "Logged out"}
