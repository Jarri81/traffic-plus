"""Valencia city real-time traffic state ingestor.

Fetches real-time traffic state by road segment from the Valencia city
open government data API (RTOD — Real-Time Open Data).

Source:  http://apigobiernoabiertortod.valencia.es/rest/datasets/estado_trafico.json
Also:    https://valencia.opendatasoft.com/explore/dataset/estat-transit-temps-real-estado-trafico-tiempo-real/
License: Open data — Ajuntament de València
Auth:    None
Update:  Every 3 minutes

The JSON structure is flexible — Valencia has published several formats over
the years. We handle both the RTOD direct API and the OpenDataSoft export.

Possible field names across versions:
  id / idTram / tramo_id  — segment identifier
  descripcion / descripcio / nombre  — human-readable name
  estado / estatActual / state / nivel  — congestion state (integer)
  velocidad / velocitat / speed_kmh  — speed in km/h

Estado codes (Valencia uses same scale as Madrid):
  0 = no data, 1 = fluid, 2 = dense, 3 = slow, 4 = very slow, 5 = jam, 6 = closed
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from traffic_ai.db.influx import write_points
from traffic_ai.ingestors.base import BaseIngestor

logger = logging.getLogger(__name__)

# Primary RTOD endpoint
VALENCIA_RTOD_URL = (
    "http://apigobiernoabiertortod.valencia.es/rest/datasets/estado_trafico.json"
)
# Fallback via OpenDataSoft export
VALENCIA_ODS_URL = (
    "https://valencia.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    "estat-transit-temps-real-estado-trafico-tiempo-real/exports/json?limit=500"
)

_ESTADO_TO_SCORE: dict[int, float] = {
    0: 0.0, 1: 10.0, 2: 35.0, 3: 55.0, 4: 70.0, 5: 85.0, 6: 100.0,
}
_ESTADO_TO_LEVEL: dict[int, str] = {
    0: "unknown", 1: "free_flow", 2: "light", 3: "moderate",
    4: "heavy", 5: "congested", 6: "closed",
}


class ValenciaTrafficIngestor(BaseIngestor):
    """Fetches Valencia city real-time traffic state from open government API."""

    def __init__(self) -> None:
        super().__init__(name="valencia_traffic")

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def poll(self) -> list[dict[str, Any]]:
        data = await self._fetch()
        if data is None:
            return []

        records = _parse(data)
        if not records:
            self.logger.warning("Valencia: no records parsed from response")
            return []

        lines = [_to_line_protocol(r) for r in records]
        try:
            await write_points(lines)
            self.logger.info("Valencia traffic: wrote %d segment points", len(lines))
        except Exception:
            self.logger.exception("Failed to write Valencia traffic data to InfluxDB")

        return records

    async def _fetch(self) -> Any:
        urls = [VALENCIA_RTOD_URL, VALENCIA_ODS_URL]
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=20)
                    ) as resp:
                        if resp.status == 200:
                            return await resp.json(content_type=None)
                        self.logger.debug("Valencia URL %s returned %d", url, resp.status)
                except Exception as exc:
                    self.logger.debug("Valencia fetch failed for %s: %s", url, exc)
        self.logger.warning("All Valencia traffic URLs failed")
        return None


def _parse(data: Any) -> list[dict[str, Any]]:
    """Parse Valencia traffic JSON — handles multiple known response shapes."""
    records: list[dict[str, Any]] = []
    ts = datetime.now(timezone.utc)

    # Unwrap common envelope shapes
    if isinstance(data, dict):
        rows = (
            data.get("results") or
            data.get("records") or
            data.get("trafico") or
            data.get("data") or
            data.get("features") or
            []
        )
        # OpenDataSoft wraps in {"results": [...]}
        if not rows and "results" in data:
            rows = data["results"]
    elif isinstance(data, list):
        rows = data
    else:
        return records

    for row in rows:
        try:
            # Handle GeoJSON feature format
            if isinstance(row, dict) and "properties" in row:
                row = row["properties"]
            if not isinstance(row, dict):
                continue

            # Segment ID — try multiple field names
            seg_id = str(
                row.get("id") or row.get("idTram") or row.get("tramo_id") or
                row.get("id_tramo") or row.get("cod_tramo") or ""
            ).strip()
            if not seg_id:
                continue

            # Description
            description = str(
                row.get("descripcion") or row.get("descripcio") or
                row.get("nombre") or row.get("name") or ""
            ).strip()

            # Estado (congestion level)
            estado_raw = (
                row.get("estado") or row.get("estatActual") or
                row.get("state") or row.get("nivel") or row.get("congestion") or 0
            )
            try:
                estado = int(estado_raw)
            except (ValueError, TypeError):
                estado = 0

            # Speed
            speed_raw = (
                row.get("velocidad") or row.get("velocitat") or
                row.get("speed_kmh") or row.get("speed") or 0
            )
            try:
                speed = float(speed_raw)
            except (ValueError, TypeError):
                speed = 0.0

            records.append({
                "seg_id": f"vlc_{seg_id}",
                "description": description,
                "estado": estado,
                "speed_kmh": speed,
                "density_score": _ESTADO_TO_SCORE.get(estado, 0.0),
                "density_level": _ESTADO_TO_LEVEL.get(estado, "unknown"),
                "source": "valencia_rtod",
                "ts": ts,
            })
        except Exception:
            logger.debug("Skipping malformed Valencia row: %s", row)

    return records


def _to_line_protocol(record: dict[str, Any]) -> str:
    seg_id = record["seg_id"].replace(" ", r"\ ").replace(",", r"\,")
    return (
        f"valencia_traffic,seg_id={seg_id},source=valencia "
        f"speed_kmh={record['speed_kmh']},"
        f"density_score={record['density_score']},"
        f"estado={record['estado']}i"
    )
