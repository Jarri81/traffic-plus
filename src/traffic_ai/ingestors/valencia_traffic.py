"""Valencia city real-time traffic state ingestor.

Source:  https://geoportal.valencia.es/server/rest/services/OPENDATA/Trafico/MapServer/192/query
Dataset: https://opendata.vlci.valencia.es/dataset/estat-transit-temps-real-estado-trafico-tiempo-real
License: CC BY 4.0 — Ajuntament de València
Update:  Every 3 minutes

Fields returned by the ArcGIS REST endpoint:
  gid           — unique feature id
  idtramo       — segment identifier
  denominacion  — human-readable name
  estado        — congestion state (integer, see below)

Estado codes:
  0 = Fluid / Fluido
  1 = Dens / Denso
  2 = Congestionat / Congestionado
  3 = Tallat / Cortado (closed)
  4 = Sense dades / Sin datos
  5 = Pas inferior fluid
  6 = Pas inferior dens
  7 = Pas inferior congestionat
  8 = Pas inferior tallat
  9 = Sense dades (pas inferior)
  null = no data
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from traffic_ai.db.influx import write_points
from traffic_ai.ingestors.base import BaseIngestor

logger = logging.getLogger(__name__)

VALENCIA_URL = (
    "https://geoportal.valencia.es/server/rest/services/OPENDATA/Trafico"
    "/MapServer/192/query?where=1%3D1&outFields=gid%2Cdenominacion%2Cestado%2Cidtramo"
    "&f=json"
)

_ESTADO_TO_SCORE: dict[int, float] = {
    0: 10.0,   # fluid
    1: 35.0,   # dense
    2: 70.0,   # congested
    3: 100.0,  # closed
    4: 0.0,    # no data
    5: 10.0,   # underpass fluid
    6: 35.0,   # underpass dense
    7: 70.0,   # underpass congested
    8: 100.0,  # underpass closed
    9: 0.0,    # underpass no data
}
_ESTADO_TO_LEVEL: dict[int, str] = {
    0: "free_flow", 1: "light", 2: "congested", 3: "closed",
    4: "unknown",   5: "free_flow", 6: "light", 7: "congested",
    8: "closed",    9: "unknown",
}


class ValenciaTrafficIngestor(BaseIngestor):
    """Fetches Valencia city real-time traffic state from ArcGIS REST API."""

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
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    VALENCIA_URL, timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json(content_type=None)
                    self.logger.warning("Valencia URL returned %d", resp.status)
            except Exception as exc:
                self.logger.warning("Valencia fetch failed: %s", exc)
        return None


def _parse(data: Any) -> list[dict[str, Any]]:
    """Parse ArcGIS JSON response — features[].attributes."""
    records: list[dict[str, Any]] = []
    ts = datetime.now(timezone.utc)

    features = data.get("features") if isinstance(data, dict) else []
    if not features:
        return records

    for feat in features:
        try:
            attrs = feat.get("attributes", {})
            seg_id = attrs.get("idtramo") or attrs.get("gid")
            if seg_id is None:
                continue

            estado_raw = attrs.get("estado")
            estado = int(estado_raw) if estado_raw is not None else 4
            if estado not in _ESTADO_TO_SCORE:
                estado = 4

            records.append({
                "seg_id": f"vlc_{seg_id}",
                "description": str(attrs.get("denominacion") or "").strip(),
                "estado": estado,
                "density_score": _ESTADO_TO_SCORE[estado],
                "density_level": _ESTADO_TO_LEVEL[estado],
                "source": "valencia_geoportal",
                "ts": ts,
            })
        except Exception:
            logger.debug("Skipping malformed Valencia feature: %s", feat)

    return records


def _to_line_protocol(record: dict[str, Any]) -> str:
    seg_id = record["seg_id"].replace(" ", r"\ ").replace(",", r"\,")
    return (
        f"valencia_traffic,seg_id={seg_id},source=valencia_geoportal "
        f"density_score={record['density_score']},"
        f"estado={record['estado']}i"
    )
