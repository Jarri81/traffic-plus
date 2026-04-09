"""Alerts endpoint — recent high-severity incidents and TomTom events.

GET /api/v1/alerts
  Returns active alerts from two sources:
    1. PostgreSQL Incident table (severity >= 3, active status)
    2. InfluxDB tomtom_incidents (magnitude >= 2, last 30 minutes)

  Query params:
    limit   — max number of alerts (default 50)
    source  — filter by source: "postgres", "tomtom", or omit for all
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from traffic_ai.api.deps import get_current_user
from traffic_ai.db.database import get_db
from traffic_ai.db.influx import query_points
from traffic_ai.models.orm import Incident, User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/alerts")
async def get_alerts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    source: str | None = Query(None, description="postgres | tomtom"),
) -> list[dict]:
    """Return active high-severity alerts from Postgres + TomTom InfluxDB."""
    alerts: list[dict] = []

    if source in (None, "postgres"):
        alerts.extend(await _postgres_alerts(db, limit))

    if source in (None, "tomtom"):
        alerts.extend(await _tomtom_alerts())

    # Sort newest first, truncate to limit
    alerts.sort(key=lambda a: a.get("started_at") or "", reverse=True)
    return alerts[:limit]


async def _postgres_alerts(db: AsyncSession, limit: int) -> list[dict]:
    try:
        result = await db.execute(
            select(Incident)
            .where(Incident.status == "active", Incident.severity >= 3)
            .order_by(Incident.started_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
    except Exception:
        logger.exception("Failed to query PostgreSQL alerts")
        return []

    return [
        {
            "id": str(inc.id),
            "source": inc.source or "system",
            "incident_type": inc.incident_type,
            "severity": inc.severity,
            "severity_label": _severity_label(inc.severity),
            "description": inc.description or "",
            "segment_id": str(inc.segment_id) if inc.segment_id else None,
            "status": inc.status,
            "started_at": inc.started_at.isoformat() if inc.started_at else None,
        }
        for inc in rows
    ]


async def _tomtom_alerts() -> list[dict]:
    """Return TomTom incidents with magnitude >= 2 (moderate/major/road_closed)."""
    try:
        flux = """
        from(bucket: "traffic_metrics")
          |> range(start: -30m)
          |> filter(fn: (r) => r._measurement == "tomtom_incidents")
          |> last()
        """
        rows = await query_points(flux)
    except Exception:
        logger.exception("Failed to query TomTom alerts from InfluxDB")
        return []

    # Group raw field rows by incident id tag
    by_id: dict[str, dict] = {}
    for row in rows:
        inc_id = row.get("id", "")
        if not inc_id:
            continue
        if inc_id not in by_id:
            by_id[inc_id] = {
                "type": row.get("type", "unknown"),
                "magnitude_tag": row.get("magnitude", "unknown"),
                "road": row.get("road", ""),
                "city": row.get("city", ""),
            }
        field = row.get("_field", "")
        val = row.get("_value")
        if field and val is not None:
            by_id[inc_id][field] = val

    alerts = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for inc_id, vals in by_id.items():
        magnitude = int(vals.get("magnitude_i") or 0)
        if magnitude < 2:
            continue
        alerts.append({
            "id": inc_id,
            "source": "tomtom",
            "incident_type": vals.get("type", "unknown"),
            "severity": magnitude,
            "severity_label": _magnitude_label(magnitude),
            "description": _build_description(vals),
            "city": vals.get("city", ""),
            "road": vals.get("road", ""),
            "delay_s": vals.get("delay_s", 0),
            "length_m": vals.get("length_m", 0),
            "status": "active",
            "started_at": now_iso,
        })
    return alerts


def _severity_label(severity: int | None) -> str:
    if severity is None:
        return "unknown"
    if severity >= 5:
        return "critical"
    if severity >= 4:
        return "high"
    if severity >= 3:
        return "medium"
    return "low"


def _magnitude_label(magnitude: int) -> str:
    return {1: "minor", 2: "moderate", 3: "major", 4: "road_closed"}.get(magnitude, "unknown")


def _build_description(row: dict) -> str:
    type_name = row.get("type", "Incident")
    road = row.get("road", "")
    city = row.get("city", "")
    delay = row.get("delay_s", 0)
    parts = [type_name.replace("_", " ").capitalize()]
    if road:
        parts.append(f"on {road}")
    if city:
        parts.append(f"({city.capitalize()})")
    if delay and float(delay) > 0:
        parts.append(f"— {int(float(delay) // 60)} min delay")
    return " ".join(parts)
