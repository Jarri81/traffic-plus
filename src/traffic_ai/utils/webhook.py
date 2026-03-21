"""Webhook notification utility.

Fires HTTP POST payloads to a configured URL when high-severity events occur.
The webhook URL can be configured at runtime via the /api/v1/settings endpoint
(stored in Redis) or set permanently via the WEBHOOK_URL environment variable.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

import aiohttp

from traffic_ai.config import settings

logger = logging.getLogger(__name__)

_REDIS_KEY = "config:webhook_url"


async def get_webhook_url() -> str:
    """Return the active webhook URL (Redis runtime config → env var → empty)."""
    try:
        from traffic_ai.db.redis_client import get_redis
        redis = await get_redis()
        stored = await redis.get(_REDIS_KEY)
        if stored:
            return stored
    except Exception:
        pass
    return getattr(settings, "webhook_url", "")


async def set_webhook_url(url: str) -> None:
    """Persist webhook URL to Redis (survives API restarts until Redis flushes)."""
    from traffic_ai.db.redis_client import get_redis
    redis = await get_redis()
    if url:
        await redis.set(_REDIS_KEY, url)
    else:
        await redis.delete(_REDIS_KEY)


async def fire_webhook(event_type: str, payload: dict) -> bool:
    """POST a JSON payload to the configured webhook URL.

    Returns True if delivered successfully, False otherwise.
    Never raises — webhook failures must not break the main flow.
    """
    url = await get_webhook_url()
    if not url:
        return False

    body = {
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "traffic-ai",
        **payload,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status < 300:
                    logger.debug("Webhook delivered: %s → %s", event_type, url)
                    return True
                logger.warning("Webhook returned %d for event %s", resp.status, event_type)
                return False
    except Exception as exc:
        logger.warning("Webhook delivery failed (%s): %s", event_type, exc)
        return False
