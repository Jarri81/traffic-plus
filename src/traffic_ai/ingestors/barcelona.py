"""Barcelona traffic state ingestor.

Pulls real-time traffic state data from Open Data BCN (Ajuntament de Barcelona).
Data is published every 5 minutes from inductive loop sensors on the urban network.

API: Open Data BCN CKAN portal — dataset "Trams de vies amb estat del trànsit"
Resource URL:  https://opendata-ajuntament.barcelona.cat/data/api/action/datastore_search
Dataset ID:    trams (traffic sections with current state)

Each road section ("tram") has:
    idTram          — section ID
    descripcio      — human-readable location (e.g. "Gran Via - Balmes / Enric Granados")
    estatActual     — current state: 0=no data, 1=very fluid, 2=fluid, 3=dense, 4=very dense, 5=congested, 6=cut
    velocitat       — average speed km/h (may be absent for low-traffic sensors)

We map estat 0–6 to our density_score 0–100 and write to InfluxDB measurement
"barcelona_traffic" so the risk scorer can use it.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from traffic_ai.db.influx import write_points
from traffic_ai.ingestors.base import BaseIngestor

logger = logging.getLogger(__name__)

# Open Data BCN CKAN API — traffic state resource
BCN_TRAFFIC_URL = (
    "https://opendata-ajuntament.barcelona.cat/data/api/action/datastore_search"
    "?resource_id=trams&limit=500"
)

# Fallback: static GeoJSON / JSON published by the Ajuntament
BCN_TRAFFIC_FALLBACK_URL = (
    "https://opendata-ajuntament.barcelona.cat/resources/bcn/trams-estat.json"
)

# estat → density score (0-100)
_ESTAT_TO_SCORE: dict[int, float] = {
    0: 0.0,   # no data
    1: 10.0,  # very fluid
    2: 25.0,  # fluid
    3: 50.0,  # dense
    4: 65.0,  # very dense
    5: 80.0,  # congested
    6: 100.0, # cut / road closed
}

_ESTAT_TO_LEVEL: dict[int, str] = {
    0: "unknown",
    1: "free_flow",
    2: "light",
    3: "moderate",
    4: "heavy",
    5: "congested",
    6: "closed",
}


class BarcelonaIngestor(BaseIngestor):
    """Ingests Barcelona real-time traffic state from Open Data BCN."""

    def __init__(self) -> None:
        super().__init__(name="barcelona")

    async def start(self) -> None:
        self._running = True
        self.logger.info("BarcelonaIngestor started")

    async def stop(self) -> None:
        self._running = False

    async def poll(self) -> list[dict[str, Any]]:
        """Fetch current traffic state and write to InfluxDB."""
        data = await self._fetch()
        if not data:
            return []

        records = self._parse(data)
        if not records:
            return []

        lines = [self._to_line_protocol(r) for r in records]
        try:
            await write_points(lines)
            self.logger.info("Barcelona: wrote %d traffic state points", len(lines))
        except Exception:
            self.logger.exception("Failed to write Barcelona traffic data")

        return records

    # ── private ─────────────────────────────────────────────────────────────

    async def _fetch(self) -> dict | list | None:
        async with aiohttp.ClientSession() as session:
            # Try CKAN API first
            for url in (BCN_TRAFFIC_URL, BCN_TRAFFIC_FALLBACK_URL):
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        if resp.status == 200:
                            return await resp.json()
                except Exception:
                    self.logger.debug("Barcelona fetch failed for %s", url)
        self.logger.warning("All Barcelona traffic URLs failed")
        return None

    def _parse(self, data: dict | list) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        ts = datetime.now(timezone.utc)

        # Handle CKAN API response format: {"result": {"records": [...]}}
        if isinstance(data, dict):
            rows = (
                data.get("result", {}).get("records", [])
                or data.get("records", [])
                or data.get("features", [])  # GeoJSON fallback
                or (data.get("tramos") or [])
            )
        else:
            rows = data  # plain list

        for row in rows:
            try:
                # Handle GeoJSON feature format
                if "properties" in row:
                    row = row["properties"]

                tram_id = str(row.get("idTram") or row.get("id") or "").strip()
                if not tram_id:
                    continue

                estat_raw = row.get("estatActual") or row.get("estat") or 0
                estat = int(estat_raw) if str(estat_raw).isdigit() else 0

                speed_raw = row.get("velocitat") or row.get("speed") or 0
                try:
                    speed = float(speed_raw)
                except (ValueError, TypeError):
                    speed = 0.0

                density_score = _ESTAT_TO_SCORE.get(estat, 0.0)
                density_level = _ESTAT_TO_LEVEL.get(estat, "unknown")

                records.append({
                    "tram_id": f"bcn_{tram_id}",
                    "description": row.get("descripcio", "").strip(),
                    "estat": estat,
                    "speed_kmh": speed,
                    "density_score": density_score,
                    "density_level": density_level,
                    "source": "barcelona_open_data",
                    "ts": ts,
                })
            except Exception:
                self.logger.debug("Skipping malformed Barcelona row: %s", row)

        return records

    @staticmethod
    def _to_line_protocol(record: dict[str, Any]) -> str:
        tram_id = record["tram_id"].replace(" ", r"\ ")
        return (
            f"barcelona_traffic,tram_id={tram_id},source=barcelona "
            f"density_score={record['density_score']},"
            f"speed_kmh={record['speed_kmh']},"
            f"estat={record['estat']}i"
        )
