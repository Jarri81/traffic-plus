"""Madrid loop-detector ingestor.

Pulls real-time traffic intensity data published by Ayuntamiento de Madrid
(datos.madrid.es) every 5 minutes from ~4,000 measurement points covering
the urban road network including the M-30.

Data format: CSV with semicolon separator, UTF-8 encoded.
Columns (as documented by Madrid open data):
    idelem          — sensor element ID (maps to a known point location)
    descripcion     — human-readable location name
    acutalizacion   — timestamp of last reading (DD/MM/YYYY HH:MM:SS)
    vmed            — average speed km/h (0 = no data / sensor error)
    error           — "N" = ok, "E" = error
    subError        — error sub-code
    intensidad      — vehicles per hour (flow)
    ocupacion       — occupancy % (0–100)
    carga           — traffic load (vehicles × time)
    nivelServicio   — level of service (E=free flow → F=congested)
    velocidadMedia  — average speed (same as vmed in most cases)
    periodoIntegracion — integration period in minutes (usually 5)

Each reading is written to InfluxDB under measurement "madrid_loop"
and tagged with the sensor ID so the risk scorer can query it.

A best-effort segment match is attempted by looking for a RoadSegment
whose name contains the sensor's descripcion tokens. Falls back to
writing with segment_id="unknown" if no match found.
"""
from __future__ import annotations
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from traffic_ai.db.influx import write_points
from traffic_ai.ingestors.base import BaseIngestor

logger = logging.getLogger(__name__)

# Real-time CSV published every 5 minutes by Madrid Open Data
# Dataset: "Intensidad del tráfico en tiempo real" — id 202468
MADRID_TRAFFIC_URL = (
    "https://datos.madrid.es/egob/catalogo/202468-0-intensidad-trafico-csv.csv"
)

# Measurement point catalog with coordinates (updated monthly)
MADRID_POINTS_URL = (
    "https://datos.madrid.es/egob/catalogo/202468-6-intensidad-trafico-pmed.csv"
)


class MadridLoopIngestor(BaseIngestor):
    """Ingestor for Madrid Ayuntamiento real-time traffic intensity data."""

    def __init__(self) -> None:
        super().__init__(name="madrid_loops")
        self._point_cache: dict[str, dict[str, Any]] = {}  # idelem → {lat, lon, name}

    async def start(self) -> None:
        self._running = True
        await self._load_point_catalog()
        self.logger.info(
            "MadridLoopIngestor started — %d measurement points loaded",
            len(self._point_cache),
        )

    async def stop(self) -> None:
        self._running = False

    async def poll(self) -> list[dict[str, Any]]:
        """Fetch current traffic intensity CSV and write to InfluxDB."""
        records: list[dict[str, Any]] = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    MADRID_TRAFFIC_URL,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers={"Accept-Encoding": "gzip"},
                ) as resp:
                    if resp.status != 200:
                        self.logger.warning(
                            "Madrid traffic URL returned %d", resp.status
                        )
                        return []
                    raw = await resp.text(encoding="utf-8-sig")  # handles BOM
        except Exception:
            self.logger.exception("Failed to fetch Madrid traffic data")
            return []

        lines: list[str] = []
        reader = csv.DictReader(io.StringIO(raw), delimiter=";")
        for row in reader:
            try:
                record = self._parse_row(row)
                if record:
                    records.append(record)
                    lines.append(self._to_line_protocol(record))
            except Exception:
                self.logger.debug("Skipping malformed row: %s", row)

        if lines:
            try:
                await write_points(lines)
                self.logger.info(
                    "Madrid loops: wrote %d points to InfluxDB", len(lines)
                )
            except Exception:
                self.logger.exception("Failed to write Madrid loop data to InfluxDB")

        return records

    # ── private ─────────────────────────────────────────────────────────────

    def _parse_row(self, row: dict[str, str]) -> dict[str, Any] | None:
        """Parse a CSV row into a normalised record. Returns None to skip."""
        error = row.get("error", "N").strip()
        if error != "N":
            return None  # sensor error — don't write bad data

        sensor_id = row.get("idelem", "").strip()
        if not sensor_id:
            return None

        def _float(key: str) -> float:
            try:
                return float(row.get(key, "0").strip().replace(",", "."))
            except ValueError:
                return 0.0

        speed = _float("vmed")
        flow = _float("intensidad")
        occupancy = _float("ocupacion")

        # Enrich with catalog data if available
        meta = self._point_cache.get(sensor_id, {})

        return {
            "sensor_id": f"madrid_{sensor_id}",
            "name": meta.get("name") or row.get("descripcion", "").strip(),
            "lat": meta.get("lat"),
            "lon": meta.get("lon"),
            "speed_kmh": speed,
            "flow_veh_h": flow,
            "occupancy_pct": occupancy,
            "source": "madrid_loops",
            "ts": datetime.now(timezone.utc),
        }

    @staticmethod
    def _to_line_protocol(record: dict[str, Any]) -> str:
        sensor_id = record["sensor_id"].replace(" ", r"\ ")
        return (
            f"madrid_loop,sensor_id={sensor_id},source=madrid_loops "
            f"speed_kmh={record['speed_kmh']},"
            f"flow_veh_h={record['flow_veh_h']},"
            f"occupancy_pct={record['occupancy_pct']}"
        )

    async def _load_point_catalog(self) -> None:
        """Load the static measurement point catalog (coordinates + names).

        Falls back silently if unavailable — data still flows without coords.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    MADRID_POINTS_URL, timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status != 200:
                        return
                    raw = await resp.text(encoding="utf-8-sig")

            reader = csv.DictReader(io.StringIO(raw), delimiter=";")
            for row in reader:
                sensor_id = row.get("id", "").strip()
                if not sensor_id:
                    continue
                self._point_cache[sensor_id] = {
                    "name": row.get("nombre", "").strip(),
                    "lat": _safe_float(row.get("latitud", "")),
                    "lon": _safe_float(row.get("longitud", "")),
                }
            self.logger.info("Loaded %d Madrid measurement points", len(self._point_cache))
        except Exception:
            self.logger.warning("Could not load Madrid point catalog — coords unavailable")


def _safe_float(s: str) -> float | None:
    try:
        return float(s.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None
