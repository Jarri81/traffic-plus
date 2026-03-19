"""Incident CRUD endpoints."""
from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from traffic_ai.api.deps import get_current_user
from traffic_ai.db.database import get_db
from traffic_ai.models.orm import Incident, User
from traffic_ai.models.schemas import IncidentOut

router = APIRouter()


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
