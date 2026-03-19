"""Alert engine — auto-creates incidents when risk scores cross thresholds.

Called by the risk computation Celery task after each scoring cycle.
Uses hysteresis to avoid alert storms: an incident is only created when
the score crosses UP through the threshold, and is auto-resolved when
it drops back below the clear threshold.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Score must exceed TRIGGER to create an alert for that level
ALERT_THRESHOLDS = {
    "critical": 75.0,
    "high":     50.0,
}

# Score must drop below CLEAR to auto-resolve the alert (hysteresis gap = 5)
CLEAR_THRESHOLDS = {
    "critical": 70.0,
    "high":     45.0,
}


async def evaluate_and_alert(
    db: AsyncSession,
    segment_id: str,
    score: float,
    pilot: str = "default",
) -> list[str]:
    """Check score against thresholds and create/resolve incidents as needed.

    Returns a list of action strings for logging (e.g. ["created:critical"]).
    """
    from traffic_ai.models.orm import Incident

    actions: list[str] = []

    for level, trigger in ALERT_THRESHOLDS.items():
        clear = CLEAR_THRESHOLDS[level]

        # Find any active incident of this level for this segment
        result = await db.execute(
            select(Incident).where(
                Incident.segment_id == segment_id,
                Incident.status == "active",
                Incident.incident_type == f"risk_threshold_{level}",
            ).limit(1)
        )
        existing = result.scalar_one_or_none()

        if score >= trigger and existing is None:
            # Score crossed UP — create incident
            incident = Incident(
                pilot=pilot,
                incident_type=f"risk_threshold_{level}",
                severity=_level_to_severity(level),
                status="active",
                segment_id=segment_id,
                description=(
                    f"Risk score {score:.1f} exceeded {level} threshold ({trigger}). "
                    f"Automated alert from risk scoring engine."
                ),
                source="risk_engine",
                started_at=datetime.now(timezone.utc),
            )
            db.add(incident)
            await db.flush()
            actions.append(f"created:{level}:{score:.1f}")
            logger.warning(
                "Alert created: segment=%s level=%s score=%.1f",
                segment_id, level, score,
            )

        elif score < clear and existing is not None:
            # Score dropped below clear threshold — auto-resolve
            existing.status = "resolved"
            existing.ended_at = datetime.now(timezone.utc)
            await db.flush()
            actions.append(f"resolved:{level}:{score:.1f}")
            logger.info(
                "Alert auto-resolved: segment=%s level=%s score=%.1f",
                segment_id, level, score,
            )

    return actions


def _level_to_severity(level: str) -> int:
    return {"critical": 5, "high": 4, "medium": 3, "low": 2}.get(level, 3)
