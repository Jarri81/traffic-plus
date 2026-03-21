"""Incident CRUD endpoints."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from traffic_ai.api.deps import get_current_user, require_operator
from traffic_ai.db.database import get_db
from traffic_ai.models.orm import Incident, User
from traffic_ai.models.schemas import IncidentOut

router = APIRouter()


class IncidentCreate(BaseModel):
    incident_type: str
    severity: Optional[int] = None
    segment_id: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = "manual"
    pilot: str = "default"


@router.post("/incidents", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
async def create_incident(
    body: IncidentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(require_operator),
) -> IncidentOut:
    """Manually create an incident. Fires webhook for severity >= 4."""
    incident = Incident(
        incident_type=body.incident_type,
        severity=body.severity,
        segment_id=body.segment_id,
        description=body.description,
        source=body.source,
        pilot=body.pilot,
        status="active",
        started_at=datetime.now(timezone.utc),
    )
    db.add(incident)
    await db.flush()
    out = IncidentOut.model_validate(incident)

    if body.severity and body.severity >= 4:
        from traffic_ai.utils.webhook import fire_webhook  # noqa: PLC0415
        import asyncio  # noqa: PLC0415
        asyncio.create_task(fire_webhook("incident.high_severity", {
            "incident_id": out.id,
            "incident_type": body.incident_type,
            "severity": body.severity,
            "segment_id": body.segment_id,
            "description": body.description,
        }))

    return out


@router.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user),
    status: str | None = Query(None, description="Filter by status: active, resolved"),
    segment_id: str | None = Query(None),
    limit: int = Query(50, le=500),
) -> list[IncidentOut]:
    """List incidents with optional filters."""
    stmt = select(Incident).order_by(Incident.started_at.desc())
    if status:
        stmt = stmt.where(Incident.status == status)
    if segment_id:
        stmt = stmt.where(Incident.segment_id == segment_id)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return [IncidentOut.model_validate(i) for i in result.scalars().all()]


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
async def get_incident(
    incident_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user),
) -> IncidentOut:
    """Get a single incident."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentOut.model_validate(incident)


@router.patch("/incidents/{incident_id}/resolve", response_model=IncidentOut)
async def resolve_incident(
    incident_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user),
) -> IncidentOut:
    """Mark an incident as resolved."""
    from datetime import datetime, timezone
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident.status = "resolved"
    incident.ended_at = datetime.now(timezone.utc)
    await db.flush()
    return IncidentOut.model_validate(incident)
