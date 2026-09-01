from __future__ import annotations
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_user, require_admin_kepala, get_current_user
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.auth_service import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == body.username, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Username atau password salah.")

    token = create_access_token({"sub": user.username, "role": user.role})
    return TokenResponse(
        access_token=token,
        username=user.username,
        name=user.name,
        role=user.role,
        role_label=user.role_label,
        expedition=user.expedition,
        dealer_code=user.dealer_code,
    )


@router.get("/me")
async def me(user: User = Depends(require_user)):
    return UserResponse(
        username=user.username,
        name=user.name,
        role=user.role,
        role_label=user.role_label,
        expedition=user.expedition,
        dealer_code=user.dealer_code,
    )
