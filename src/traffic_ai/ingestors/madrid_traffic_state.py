"""Madrid real-time traffic state ingestor.

Fetches the Informo Madrid per-tramo state XML — updated every 5 minutes by
the Ayuntamiento de Madrid traffic management centre.

This is different from the loop detector CSV ingestor (which gives raw vehicle
counts from individual sensors). This feed gives the *processed* state per road
section: speed, load, and a discrete congestion level.

Source:  https://informo.madrid.es/informo/tmadrid/pm.xml
License: Open data — Ayuntamiento de Madrid (CC BY 4.0)
Auth:    None

Fields per tramo (road section):
  id          — section identifier
  cod_via     — road code
  tipo_elem   — element type (M30, URB, etc.)
  descripcion — human-readable location
  velocidad   — average speed km/h (0 = no data)
  carga       — load percentage 0-100
  ocupacion   — occupancy percentage 0-100
  estado      — 0=no data, 1=fluid, 2=dense, 3=slow, 4=very slow,
                5=jam/retention, 6=closed
  st_x, st_y  — UTM coordinates (EPSG:23030)
"""
from __future__ import annotations
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import aiohttp

from traffic_ai.db.influx import write_points
from traffic_ai.ingestors.base import BaseIngestor

logger = logging.getLogger(__name__)

MADRID_STATE_URL = "https://informo.madrid.es/informo/tmadrid/pm.xml"

_ESTADO_TO_SCORE: dict[int, float] = {
    0: 0.0,   # no data
    1: 10.0,  # fluid
    2: 35.0,  # dense
    3: 55.0,  # slow
    4: 70.0,  # very slow
    5: 85.0,  # jam
    6: 100.0, # closed
}

_ESTADO_TO_LEVEL: dict[int, str] = {
    0: "unknown",
    1: "free_flow",
    2: "light",
    3: "moderate",
    4: "heavy",
    5: "congested",
    6: "closed",
}


class MadridTrafficStateIngestor(BaseIngestor):
    """Fetches Madrid per-tramo real-time traffic state from Informo XML."""

    def __init__(self) -> None:
        super().__init__(name="madrid_traffic_state")

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def poll(self) -> list[dict[str, Any]]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    MADRID_STATE_URL,
                    timeout=aiohttp.ClientTimeout(total=20),
                    headers={"Accept-Encoding": "gzip"},
                ) as resp:
                    if resp.status != 200:
                        self.logger.warning("Informo Madrid returned HTTP %d", resp.status)
                        return []
                    xml_bytes = await resp.read()
        except Exception:
            self.logger.exception("Failed to fetch Madrid traffic state XML")
            return []

        records = _parse_madrid_state_xml(xml_bytes)
        if not records:
            return []

        lines = [_to_line_protocol(r) for r in records]
        try:
            await write_points(lines)
            self.logger.info("Madrid traffic state: wrote %d tramo points", len(lines))
        except Exception:
            self.logger.exception("Failed to write Madrid traffic state to InfluxDB")

        return records


def _parse_madrid_state_xml(xml_bytes: bytes) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    ts = datetime.now(timezone.utc)
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        logger.warning("Failed to parse Madrid traffic state XML")
        return records

    for pm in root.iter("pm"):
        try:
            tramo_id = pm.get("id", "").strip()
            if not tramo_id:
                continue

            estado = int(pm.get("estado") or 0)
            velocidad_raw = pm.get("velocidad") or "0"
            try:
                speed = float(velocidad_raw)
            except ValueError:
                speed = 0.0

            carga_raw = pm.get("carga") or "0"
            try:
                load_pct = float(carga_raw)
            except ValueError:
                load_pct = 0.0

            ocupacion_raw = pm.get("ocupacion") or "0"
            try:
                occupancy_pct = float(ocupacion_raw)
            except ValueError:
                occupancy_pct = 0.0

            records.append({
                "tramo_id": f"mad_{tramo_id}",
                "road_code": pm.get("cod_via", ""),
                "tipo": pm.get("tipo_elem", ""),
                "description": pm.get("descripcion", "").strip(),
                "speed_kmh": speed,
                "load_pct": load_pct,
                "occupancy_pct": occupancy_pct,
                "estado": estado,
                "density_score": _ESTADO_TO_SCORE.get(estado, 0.0),
                "density_level": _ESTADO_TO_LEVEL.get(estado, "unknown"),
                "source": "madrid_informo",
                "ts": ts,
            })
        except Exception:
            logger.debug("Skipping malformed Madrid tramo element")

    return records


def _to_line_protocol(record: dict[str, Any]) -> str:
    tramo_id = record["tramo_id"].replace(" ", r"\ ").replace(",", r"\,")
    tipo = (record["tipo"] or "unknown").replace(" ", r"\ ")
    return (
        f"madrid_traffic,tramo_id={tramo_id},tipo={tipo},source=informo "
        f"speed_kmh={record['speed_kmh']},"
        f"load_pct={record['load_pct']},"
        f"occupancy_pct={record['occupancy_pct']},"
        f"density_score={record['density_score']},"
        f"estado={record['estado']}i"
    )
