"""TomTom Traffic API ingestors.

Two ingestors:
  TomTomIncidentsIngestor — national Spain incidents (1 API call per poll)
  TomTomFlowIngestor      — flow data for key highway coordinate points

Free tier budget: 2,500 requests/day.
  Flow (40 pts) every 30 min → 40 × 48 = 1,920 calls/day  (77% of free tier)

  Points cover Spain-wide intercity corridors (groups A–E) for MITMA crosscheck.
  30-min resolution is sufficient — MITMA publishes hourly aggregates.

Incident magnitude: 1=minor, 2=moderate, 3=major, 4=undefined/road_closed
Incident types (subset): 1=accident, 6=jam, 7=lane_closed, 8=road_closed,
    9=road_works, 14=broken_down_vehicle

Spain bounding box: minLon=-9.3, minLat=36.0, maxLon=3.3, maxLat=43.8

Docs: https://developer.tomtom.com/traffic-api/documentation/traffic-flow/flow-segment-data
      https://developer.tomtom.com/traffic-api/documentation/traffic-incidents/incident-details
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from traffic_ai.config import settings
from traffic_ai.db.influx import write_points
from traffic_ai.ingestors.base import BaseIngestor

logger = logging.getLogger(__name__)

# Spain bounding box (minLon, minLat, maxLon, maxLat)
# TomTom incidents API max bbox is 10,000 km² — Spain (~505,000 km²) doesn't fit.
# Use per-city bboxes instead (each well under the limit).
_CITY_BBOXES: list[tuple[str, str]] = [
    ("-4.0,40.2,-3.3,40.7", "madrid"),    # ~3,000 km²
    ("-0.6,39.3,0.0,39.7",  "valencia"),  # ~2,500 km²
    ("1.8,41.2,2.5,41.6",   "barcelona"), # ~2,700 km²
]

# Approximate city centres used as fallback when geometry is absent
_CITY_CENTRES: dict[str, tuple[float, float]] = {
    "madrid":    (40.4168, -3.7038),
    "valencia":  (39.4699, -0.3763),
    "barcelona": (41.3851,  2.1734),
}

# Intercity corridor points for MITMA crosscheck validation.
# 40 points × 48 polls/day (every 30 min) = 1,920 calls/day < 2,500 free-tier limit.
# All points are on intercity highways where MITMA OD assignment is meaningful
# and where Madrid/Barcelona/Valencia sensor networks have zero coverage.
# Tagged by corridor group (A–E) for query filtering.
DEFAULT_FLOW_POINTS: list[tuple[str, float, float]] = [
    # Group A — Madrid radial exits
    ("madrid_a1_somosierra",  41.1500, -3.5800),   # A-1 km 80  → Burgos/Bilbao
    ("madrid_a2_guadalajara", 40.6200, -3.1600),   # A-2 km 55  → Zaragoza/Barcelona
    ("madrid_a3_tarancon",    39.9900, -2.9900),   # A-3 km 90  → Valencia
    ("madrid_a4_ocana",       39.9500, -3.5000),   # A-4 km 80  → Córdoba/Sevilla
    ("madrid_a5_mostoles",    40.3200, -3.9500),   # A-5 km 25  → Badajoz
    ("madrid_a6_guadarrama",  40.7300, -4.0700),   # A-6 km 55  → Valladolid/Galicia
    ("madrid_r2_corredor",    40.5000, -3.3500),   # R-2 km 30  → Alcalá bypass
    ("madrid_m50_sw",         40.3000, -3.8500),   # M-50       → Madrid outer ring SW
    # Group B — Northeast corridor
    ("zaragoza_a2_west",      41.4000, -1.3000),   # A-2 km 280 → Madrid→Zaragoza mid
    ("zaragoza_a2_east",      41.5500, -0.7000),   # A-2 km 330 → Zaragoza→Barcelona
    ("lleida_ap2",            41.6200,  0.6200),   # AP-2 km 460 → Lleida bypass
    ("barcelona_ap7_tarragona", 41.1500, 1.2500),  # AP-7 km 250 → Barcelona→Tarragona
    ("tarragona_ap7_south",   40.8000,  0.5000),   # AP-7 km 210 → Tarragona→Valencia
    ("barcelona_b23",         41.3400,  2.0700),   # B-23 km 10  → Barcelona SW exit
    ("girona_ap7_north",      42.0000,  2.8200),   # AP-7 km 710 → Barcelona→France
    ("vic_c17",               41.9300,  2.2500),   # C-17 km 65  → Barcelona→Pyrenees
    # Group C — Southeast / Mediterranean
    ("valencia_a3_mid",       39.8500, -1.8500),   # A-3 km 330 → Valencia approach
    ("valencia_ap7_north",    39.8000, -0.1500),   # AP-7 km 480 → Valencia→Barcelona
    ("valencia_ap7_south",    39.3000, -0.4000),   # AP-7 km 420 → Valencia→Alicante
    ("alicante_ap7",          38.3500, -0.4800),   # AP-7 km 550 → Alicante bypass
    ("murcia_a30",            38.0000, -1.1300),   # A-30 km 380 → Murcia→Madrid
    ("cartagena_a30",         37.6000, -1.0000),   # A-30 km 50  → Cartagena exit
    ("almeria_a7",            37.1500, -2.0000),   # A-7 km 450  → Almería→Murcia
    ("granada_a44",           37.5500, -3.6000),   # A-44 km 120 → Granada→Jaén
    # Group D — South / Andalucía
    ("sevilla_a4_north",      37.7000, -5.9500),   # A-4 km 530  → Sevilla→Madrid
    ("sevilla_a49_west",      37.3800, -6.5000),   # A-49 km 20  → Sevilla→Huelva
    ("cadiz_a4",              36.6000, -6.2000),   # A-4 km 650  → Cádiz→Sevilla
    ("malaga_a7",             36.7200, -4.4000),   # A-7 km 230  → Málaga→Almería
    ("malaga_a45",            37.1000, -4.5500),   # A-45 km 170 → Málaga→Córdoba
    ("cordoba_a4",            37.8800, -4.7800),   # A-4 km 400  → Córdoba midpoint
    ("jaen_a4",               38.0000, -3.7900),   # A-4 km 300  → Jaén stretch
    ("huelva_a49",            37.2600, -7.0000),   # A-49 km 80  → Huelva→Portugal
    # Group E — North / Atlantic
    ("bilbao_ap8",            43.2630, -2.9350),   # AP-8 km 20  → Bilbao→San Sebastián
    ("sansebastian_ap8",      43.3000, -1.9800),   # AP-8 km 80  → San Sebastián→France
    ("burgos_a1",             42.3500, -3.7000),   # A-1 km 240  → Burgos→Madrid
    ("valladolid_a62",        41.5000, -4.8000),   # A-62 km 120 → Valladolid→Salamanca
    ("salamanca_a62",         40.9600, -5.6700),   # A-62 km 60  → Salamanca→Portugal
    ("vigo_ap9",              42.2000, -8.7000),   # AP-9 km 20  → Vigo→Porto
    ("coruna_ap9_north",      43.3700, -8.4000),   # AP-9 km 580 → A Coruña→Santiago
    ("oviedo_a66",            43.0000, -5.9000),   # A-66 km 430 → Oviedo→Benavente
]

_INCIDENT_TYPE_NAMES: dict[int, str] = {
    0: "unknown", 1: "accident", 2: "fog", 3: "dangerous_conditions",
    4: "rain", 5: "ice", 6: "jam", 7: "lane_closed", 8: "road_closed",
    9: "road_works", 10: "wind", 11: "flooding", 14: "broken_down_vehicle",
}

_MAGNITUDE_NAMES: dict[int, str] = {
    0: "unknown", 1: "minor", 2: "moderate", 3: "major", 4: "road_closed",
}

_BASE = "https://api.tomtom.com/traffic/services"


class TomTomIncidentsIngestor(BaseIngestor):
    """Polls TomTom for national Spain traffic incidents."""

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(name="tomtom_incidents")
        self._key = api_key or settings.tomtom_api_key

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def poll(self) -> list[dict[str, Any]]:
        if not self._key:
            self.logger.warning("TOMTOM_API_KEY not set — skipping incidents poll")
            return []

        all_records: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        try:
            async with aiohttp.ClientSession() as session:
                for bbox, city in _CITY_BBOXES:
                    # fields includes geometry{type,coordinates} for real GPS coords
                    # and the key properties we need for enrichment
                    url = (
                        f"{_BASE}/5/incidentDetails"
                        f"?bbox={bbox}"
                        "&language=es-ES"
                        "&timeValidityFilter=present"
                        f"&key={self._key}"
                    )
                    try:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                            if resp.status == 401:
                                self.logger.error("TomTom: invalid API key (401)")
                                return []
                            if resp.status == 429:
                                self.logger.warning("TomTom: rate limit hit (429)")
                                break
                            if resp.status != 200:
                                self.logger.warning("TomTom incidents bbox %s returned HTTP %d", bbox, resp.status)
                                continue
                            data = await resp.json(content_type=None)
                    except Exception:
                        self.logger.exception("Failed to fetch TomTom incidents for bbox %s", bbox)
                        continue

                    for r in _parse_incidents(data, city):
                        if r["id"] not in seen_ids:
                            seen_ids.add(r["id"])
                            all_records.append(r)
        except Exception:
            self.logger.exception("Failed to fetch TomTom incidents")
            return []

        if not all_records:
            return []

        lines = [_incident_to_line(r) for r in all_records]
        try:
            await write_points(lines)
            self.logger.info("TomTom incidents: wrote %d points", len(lines))
        except Exception:
            self.logger.exception("Failed to write TomTom incidents to InfluxDB")

        return all_records


class TomTomFlowIngestor(BaseIngestor):
    """Polls TomTom Flow Segment Data for key highway coordinate points."""

    def __init__(
        self,
        api_key: str | None = None,
        points: list[tuple[str, float, float]] | None = None,
    ) -> None:
        super().__init__(name="tomtom_flow")
        self._key = api_key or settings.tomtom_api_key
        self._points = points or DEFAULT_FLOW_POINTS

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def poll(self) -> list[dict[str, Any]]:
        if not self._key:
            self.logger.warning("TOMTOM_API_KEY not set — skipping flow poll")
            return []

        records: list[dict[str, Any]] = []
        async with aiohttp.ClientSession() as session:
            for name, lat, lon in self._points:
                try:
                    record = await _fetch_flow_point(session, self._key, name, lat, lon)
                    if record:
                        records.append(record)
                except Exception:
                    self.logger.debug("TomTom flow failed for %s", name)

        if not records:
            return []

        lines = [_flow_to_line(r) for r in records]
        try:
            await write_points(lines)
            self.logger.info("TomTom flow: wrote %d points", len(lines))
        except Exception:
            self.logger.exception("Failed to write TomTom flow data to InfluxDB")

        return records


async def _fetch_flow_point(
    session: aiohttp.ClientSession,
    key: str,
    name: str,
    lat: float,
    lon: float,
) -> dict[str, Any] | None:
    url = (
        f"{_BASE}/4/flowSegmentData/absolute/10/json"
        f"?point={lat},{lon}&unit=KMPH&key={key}"
    )
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
        if resp.status != 200:
            return None
        data = await resp.json(content_type=None)

    fd = data.get("flowSegmentData", {})
    current_speed = fd.get("currentSpeed", 0.0)
    free_flow_speed = fd.get("freeFlowSpeed", 0.0)
    confidence = fd.get("confidence", 0.0)
    road_closure = bool(fd.get("roadClosure", False))

    # Derive a density score: 0 = free_flow, 100 = standstill
    if road_closure:
        density_score = 100.0
    elif free_flow_speed and free_flow_speed > 0:
        density_score = max(0.0, min(100.0, (1 - current_speed / free_flow_speed) * 100))
    else:
        density_score = 0.0

    return {
        "point_id": name,
        "lat": lat,
        "lon": lon,
        "current_speed": float(current_speed),
        "free_flow_speed": float(free_flow_speed),
        "confidence": float(confidence),
        "road_closure": road_closure,
        "density_score": density_score,
        "source": "tomtom_flow",
        "ts": datetime.now(timezone.utc),
    }


def _parse_incidents(data: dict[str, Any], city: str = "") -> list[dict[str, Any]]:
    """Parse TomTom v5 incidentDetails response.

    The API returns incidents as GeoJSON features; properties include:
      id, iconCategory, magnitudeOfDelay, from, to, length, delay, roadNumbers
    Geometry (LineString or Point) is extracted for map positioning.
    """
    records: list[dict[str, Any]] = []
    ts = datetime.now(timezone.utc)
    fallback_lat, fallback_lon = _CITY_CENTRES.get(city, (40.4168, -3.7038))

    incidents = data.get("incidents") or data.get("features", [])
    for inc in incidents:
        try:
            props = inc.get("properties") or {}
            inc_type = int(props.get("iconCategory") or props.get("type") or 0)
            magnitude = int(props.get("magnitudeOfDelay") or props.get("magnitude") or 0)
            delay = float(props.get("delay") or 0)
            length = float(props.get("length") or 0)
            road_numbers = props.get("roadNumbers") or []
            road = road_numbers[0] if road_numbers else ""

            # Extract coordinates from GeoJSON geometry
            lat, lon = fallback_lat, fallback_lon
            geom = inc.get("geometry", {})
            coords = geom.get("coordinates")
            if coords:
                first = coords[0] if isinstance(coords[0], list) else coords
                if len(first) >= 2:
                    lon, lat = float(first[0]), float(first[1])

            # id may be absent in v5 minimal responses — synthesise from position+type
            inc_id = str(inc.get("id") or props.get("id") or f"{city}_{lon:.5f}_{lat:.5f}_{inc_type}").strip()
            if not inc_id:
                continue

            records.append({
                "id": inc_id,
                "type": inc_type,
                "type_name": _INCIDENT_TYPE_NAMES.get(inc_type, "unknown"),
                "magnitude": magnitude,
                "magnitude_name": _MAGNITUDE_NAMES.get(magnitude, "unknown"),
                "delay_s": delay,
                "length_m": length,
                "road": road,
                "city": city,
                "lat": lat,
                "lon": lon,
                "source": "tomtom",
                "ts": ts,
            })
        except Exception:
            logger.debug("Skipping malformed TomTom incident")

    return records


def _incident_to_line(r: dict[str, Any]) -> str:
    inc_id = r["id"].replace(" ", r"\ ").replace(",", r"\,")
    type_name = r["type_name"].replace(" ", r"\ ")
    road = (r["road"] or "unknown").replace(" ", r"\ ").replace(",", r"\,")
    city = (r.get("city") or "unknown").replace(" ", r"\ ")
    return (
        f"tomtom_incidents,id={inc_id},type={type_name},"
        f"magnitude={r['magnitude_name']},road={road},city={city},source=tomtom "
        f"delay_s={r['delay_s']},length_m={r['length_m']},"
        f"magnitude_i={r['magnitude']}i,type_i={r['type']}i,"
        f"lat={r['lat']},lon={r['lon']}"
    )


def _flow_to_line(r: dict[str, Any]) -> str:
    point_id = r["point_id"].replace(" ", r"\ ").replace(",", r"\,")
    return (
        f"tomtom_flow,point_id={point_id},source=tomtom "
        f"current_speed={r['current_speed']},"
        f"free_flow_speed={r['free_flow_speed']},"
        f"density_score={r['density_score']},"
        f"confidence={r['confidence']},"
        f"road_closure={'true' if r['road_closure'] else 'false'}"
    )
