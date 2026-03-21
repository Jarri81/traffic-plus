"""Application runtime settings endpoint.

Allows admins to read and update runtime configuration (webhook URL, etc.)
without restarting the server. Values are stored in Redis and take effect
immediately. Env vars serve as read-only defaults when Redis has no override.
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from traffic_ai.api.deps import get_current_user, require_admin
from traffic_ai.models.orm import User
from traffic_ai.utils.webhook import get_webhook_url, set_webhook_url

router = APIRouter()


class AppSettingsOut(BaseModel):
    webhook_url: str


class AppSettingsUpdate(BaseModel):
    webhook_url: Optional[str] = None


@router.get("/settings", response_model=AppSettingsOut)
async def get_settings(
    current_user: User = Depends(get_current_user),
) -> AppSettingsOut:
    """Return current runtime settings (readable by any authenticated user)."""
    return AppSettingsOut(webhook_url=await get_webhook_url())


@router.patch("/settings", response_model=AppSettingsOut)
async def update_settings(
    body: AppSettingsUpdate,
    current_user: User = Depends(require_admin),
) -> AppSettingsOut:
    """Update runtime settings. Persisted to Redis, effective immediately."""
    if body.webhook_url is not None:
        await set_webhook_url(body.webhook_url)
    return AppSettingsOut(webhook_url=await get_webhook_url())
