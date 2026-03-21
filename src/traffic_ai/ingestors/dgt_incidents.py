"""DGT incidents ingestor.

Parses the DGT National Access Point DATEX II v3.6 incident feed and
writes new incidents to the PostgreSQL incidents table.

Feed URL (no auth, CC BY):
  https://nap.dgt.es/datex2/v3/dgt/SituationPublication/incidencias_datex2_v36.xml

Updated: near real-time as incidents are reported to DGT.

Coverage: Spanish national road network excluding Basque Country and Catalonia
(which have separate regional systems).

Deduplication: incidents are matched by external_id (DGT situation record ID).
Existing active incidents are updated; resolved ones are auto-closed.
"""
from __future__ import annotations
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from traffic_ai.ingestors.base import BaseIngestor
from traffic_ai.models.orm import Incident

logger = logging.getLogger(__name__)

DGT_INCIDENTS_URL = (
    "https://nap.dgt.es/datex2/v3/dgt/SituationPublication/incidencias_datex2_v36.xml"
)


class DGTIncidentsIngestor(BaseIngestor):
    """Ingests DGT national road incidents from DATEX II feed."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        super().__init__(name="dgt_incidents")
        self.db = db

    async def start(self) -> None:
        self._running = True
        self.logger.info("DGTIncidentsIngestor started")

    async def stop(self) -> None:
        self._running = False

    async def poll(self) -> list[dict[str, Any]]:
        """Fetch DATEX II XML and upsert incidents into PostgreSQL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    DGT_INCIDENTS_URL,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        self.logger.warning("DGT incidents feed returned %d", resp.status)
                        return []
                    xml_bytes = await resp.read()
        except Exception:
            self.logger.exception("Failed to fetch DGT incidents feed")
            return []

        parsed = _parse_incidents_datex2(xml_bytes)
        self.logger.info("DGT incidents: parsed %d situations", len(parsed))

        if self.db is None:
            return parsed  # unit test / no-DB mode

        created = updated = resolved = 0
        active_ids: set[str] = set()

        for situation in parsed:
            ext_id = situation["external_id"]
            active_ids.add(ext_id)
            result = await self.db.execute(
                select(Incident).where(Incident.external_id == ext_id).limit(1)
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                # New incident
                incident = Incident(
                    pilot="dgt",
                    incident_type=situation["incident_type"],
                    severity=situation["severity"],
                    status="active",
                    description=situation["description"],
                    source="dgt_datex2",
                    external_id=ext_id,
                    started_at=situation.get("started_at") or datetime.now(timezone.utc),
                )
                self.db.add(incident)
                created += 1
            elif existing.status == "resolved":
                # DGT is re-reporting a resolved incident — reopen it
                existing.status = "active"
                existing.ended_at = None
                updated += 1
            # else: already active, no change needed

        # Auto-resolve incidents no longer in the feed
        result = await self.db.execute(
            select(Incident).where(
                Incident.source == "dgt_datex2",
                Incident.status == "active",
            )
        )
        for incident in result.scalars().all():
            if incident.external_id not in active_ids:
                incident.status = "resolved"
                incident.ended_at = datetime.now(timezone.utc)
                resolved += 1

        await self.db.flush()
        self.logger.info(
            "DGT incidents: created=%d updated=%d resolved=%d",
            created, updated, resolved,
        )
        return parsed


# ── DATEX II parser ──────────────────────────────────────────────────────────

def _parse_incidents_datex2(xml_bytes: bytes) -> list[dict[str, Any]]:
    """Parse DGT DATEX II v3.6 situation publication."""
    incidents: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        logger.warning("Failed to parse DGT incidents XML")
        return incidents

    for situation in _iter_tag(root, "situation"):
        ext_id = _text(situation, ("id", "situationId"))
        if not ext_id:
            continue

        incident_type = _infer_type(situation)
        severity = _parse_severity(situation)
        description = _build_description(situation)
        started_at = _parse_datetime(situation, ("situationRecordCreationTime", "startTime"))

        incidents.append({
            "external_id": ext_id,
            "incident_type": incident_type,
            "severity": severity,
            "description": description,
            "started_at": started_at,
        })

    return incidents


def _iter_tag(root: ET.Element, tag_suffix: str):
    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == tag_suffix:
            yield elem


def _text(elem: ET.Element, tags: tuple[str, ...]) -> str | None:
    for child in elem.iter():
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag in tags and child.text:
            return child.text.strip()
    return None


def _infer_type(situation: ET.Element) -> str:
    """Infer incident type from the DATEX II situation record content."""
    xml_str = ET.tostring(situation, encoding="unicode").lower()
    if "roadwork" in xml_str or "obra" in xml_str:
        return "roadwork"
    if "accident" in xml_str or "accidente" in xml_str:
        return "accident"
    if "closure" in xml_str or "corte" in xml_str:
        return "road_closure"
    if "restriction" in xml_str or "restriccion" in xml_str:
        return "restriction"
    if "weather" in xml_str or "meteorolog" in xml_str:
        return "weather_hazard"
    return "general"


def _parse_severity(situation: ET.Element) -> int:
    raw = _text(situation, ("severity", "probabilityOfOccurrence")) or ""
    mapping = {
        "highest": 5, "high": 4, "medium": 3, "low": 2, "lowest": 1,
        "certain": 5, "probable": 3, "risk": 2,
    }
    for key, val in mapping.items():
        if key in raw.lower():
            return val
    return 3  # default medium


def _build_description(situation: ET.Element) -> str:
    parts: list[str] = []
    for tag in ("generalPublicComment", "comment", "description", "roadNumber"):
        val = _text(situation, (tag,))
        if val:
            parts.append(val)
    return " | ".join(parts[:3]) if parts else "DGT traffic incident"


def _parse_datetime(situation: ET.Element, tags: tuple[str, ...]) -> datetime | None:
    raw = _text(situation, tags)
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw[:19], fmt[:len(fmt)])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None
