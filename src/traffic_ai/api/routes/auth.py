"""Authentication routes -- token issuance, refresh, and registration."""
from __future__ import annotations
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from traffic_ai.api.auth import create_access_token, verify_token
from traffic_ai.config import settings
from traffic_ai.db.database import get_db
from traffic_ai.api.limiter import limiter
from traffic_ai.models.orm import User
from traffic_ai.models.schemas import TokenResponse, UserOut, UserRegister

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/token", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Issue an access token for valid credentials."""
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    if user is None or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not pwd_context.verify(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token, expires_in=settings.access_token_expire_minutes * 60)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh_token(
    request: Request,
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Refresh an existing (still valid) access token."""
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    new_token = create_access_token(data={"sub": payload["sub"], "role": payload.get("role", "viewer")})
    return TokenResponse(access_token=new_token, expires_in=settings.access_token_expire_minutes * 60)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: UserRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    """Register a new user account (default role: viewer)."""
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        id=uuid.uuid4(),
        email=body.email,
        name=body.name,
        role="viewer",
        password_hash=pwd_context.hash(body.password),
    )
    db.add(user)
    await db.flush()
    return UserOut.model_validate(user)
