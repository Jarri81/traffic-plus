"""FastAPI dependencies for authentication, RBAC, and database access."""
from __future__ import annotations
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from traffic_ai.api.auth import verify_token
from traffic_ai.db.database import get_db
from traffic_ai.models.orm import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Role hierarchy — higher index = more permissions
_ROLE_RANK: dict[str, int] = {"viewer": 0, "operator": 1, "admin": 2}


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Decode JWT token and return the authenticated user."""
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_role(min_role: str):
    """Return a dependency that enforces a minimum role level.

    Role hierarchy: viewer < operator < admin
    Passing min_role="operator" means both operators and admins are allowed.
    """
    required_rank = _ROLE_RANK.get(min_role, 99)

    async def _check(user: Annotated[User, Depends(get_current_user)]) -> User:
        user_rank = _ROLE_RANK.get(user.role, -1)
        if user_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{min_role}' or higher required (you have '{user.role}')",
            )
        return user
    return _check


# Convenience shortcuts
require_operator = require_role("operator")
require_admin = require_role("admin")


def scoped_pilot(user: User, requested_pilot: str | None) -> str | None:
    """Resolve the effective pilot filter for a user.

    - Admin: can see any pilot, uses requested_pilot as-is (or None = all)
    - Scoped user: always locked to their pilot_scope, ignores requested_pilot
    - Unscoped non-admin: uses requested_pilot as-is (or None = all)
    """
    if user.role == "admin":
        return requested_pilot
    if user.pilot_scope:
        return user.pilot_scope  # Always lock scoped users to their pilot
    return requested_pilot
