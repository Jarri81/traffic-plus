"""Madrid city camera ingestor.

Fetches the Ayuntamiento de Madrid traffic camera list from the Open Data
KML feed, polls JPEG snapshots, runs optional YOLO11 vehicle detection,
and writes density metrics to InfluxDB.

Data sources (no auth, CC BY 4.0):
  Camera list:  https://datos.madrid.es/egob/catalogo/202088-0-trafico-camaras.kml
  Image URL:    https://informo.madrid.es/cameras/Camara{ID}.jpg?v={ts}
  Coverage:     M-30 ring road + central Madrid surface roads
  Refresh:      Every 5 minutes officially

Same ONNX inference logic as DGTCameraIngestor (shared _detect_vehicles → ml.vehicle_detector).
"""
from __future__ import annotations
import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import aiohttp

from traffic_ai.config import get_profile
from traffic_ai.db.influx import write_points
from traffic_ai.ingestors.base import BaseIngestor
from traffic_ai.ingestors.dgt_cameras import _advance_camera_index, _detect_vehicles, _to_line_madrid

logger = logging.getLogger(__name__)

MADRID_CAMERA_KML_URL = (
    "https://informo.madrid.es/informo/tmadrid/CCTV.kml"
)
MADRID_IMAGE_URL = "https://informo.madrid.es/cameras/Camara{camera_id}.jpg?v={ts}"


class MadridCameraIngestor(BaseIngestor):
    """Ingests traffic density metrics from Madrid city cameras."""

    def __init__(self, max_cameras: int | None = None) -> None:
        super().__init__(name="madrid_cameras")
        profile = get_profile()
        self.max_cameras = max_cameras or profile.max_cameras
        self._cameras: list[dict[str, Any]] = []
        self._camera_index: int = 0

    async def start(self) -> None:
        self._running = True
        await self._load_camera_list()
        self.logger.info(
            "MadridCameraIngestor started — %d cameras, polling %d per cycle",
            len(self._cameras), self.max_cameras,
        )

    async def stop(self) -> None:
        self._running = False

    async def poll(self) -> list[dict[str, Any]]:
        if not self._cameras:
            await self._load_camera_list()
            if not self._cameras:
                return []

        total = len(self._cameras)
        batch_size = min(self.max_cameras, total)
        start = _advance_camera_index("madrid_camera:index", batch_size, total)
        batch = [self._cameras[(start + i) % total] for i in range(batch_size)]

        async with aiohttp.ClientSession() as session:
            raw = await asyncio.gather(
                *[self._process_camera(session, cam) for cam in batch],
                return_exceptions=True,
            )

        results = [r for r in raw if r and not isinstance(r, Exception)]
        lines = [_to_line_madrid(r) for r in results]

        if lines:
            try:
                await write_points(lines)
            except Exception:
                self.logger.exception("Failed to write Madrid camera metrics")

        self.logger.info(
            "Madrid cameras: processed %d/%d in parallel, wrote %d metrics",
            len(results), batch_size, len(lines),
        )
        return results

    async def _process_camera(
        self, session: aiohttp.ClientSession, cam: dict[str, Any]
    ) -> dict[str, Any] | None:
        camera_id = cam["id"]
        url = MADRID_IMAGE_URL.format(camera_id=camera_id, ts=int(time.time() * 1000))
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return {"camera_id": camera_id, "camera_online": False, "ts": datetime.now(timezone.utc)}
                frame_bytes = await resp.read()
        except Exception:
            self.logger.debug("Madrid camera %s fetch failed", camera_id)
            return None

        metrics = _detect_vehicles(frame_bytes)
        return {
            "camera_id": f"madrid_{camera_id}",
            "name": cam.get("name", ""),
            "lat": cam.get("lat"),
            "lon": cam.get("lon"),
            "camera_online": True,
            **metrics,
            "ts": datetime.now(timezone.utc),
        }

    async def _load_camera_list(self) -> None:
        """Fetch and parse Madrid camera KML."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    MADRID_CAMERA_KML_URL, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        self.logger.warning("Madrid camera KML returned %d", resp.status)
                        return
                    kml_bytes = await resp.read()

            cameras = _parse_madrid_kml(kml_bytes)
            self._cameras = cameras
            self.logger.info("Loaded %d Madrid cameras from KML", len(cameras))
        except Exception:
            self.logger.exception("Failed to load Madrid camera list")


def _parse_madrid_kml(kml_bytes: bytes) -> list[dict[str, Any]]:
    """Parse Madrid camera KML. Each Placemark has a camera ID and coordinates.

    The feed uses the KML 2.2 namespace on <Placemark> but ExtendedData,
    Data, Value, and coordinates elements have no namespace prefix.
    """
    cameras: list[dict[str, Any]] = []
    try:
        # Strip UTF-8 BOM if present
        xml_str = kml_bytes.decode("utf-8-sig") if isinstance(kml_bytes, bytes) else kml_bytes
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        logger.warning("Failed to parse Madrid camera KML")
        return cameras

    ns = "http://earth.google.com/kml/2.2"

    for placemark in root.iter(f"{{{ns}}}Placemark"):
        camera_id = None
        name = ""

        # ExtendedData and Data/Value have no namespace in this feed
        ext = placemark.find("ExtendedData")
        if ext is None:
            ext = placemark.find(f"{{{ns}}}ExtendedData")
        if ext is not None:
            for data_elem in list(ext) + list(ext.iter()):
                tag = data_elem.tag.split("}")[-1] if "}" in data_elem.tag else data_elem.tag
                if tag != "Data":
                    continue
                attr = data_elem.get("name", "")
                val_elem = data_elem.find("Value") or data_elem.find(f"{{{ns}}}Value")
                val = val_elem.text.strip() if val_elem is not None and val_elem.text else ""
                if attr == "Numero":
                    camera_id = val
                elif attr == "Nombre":
                    name = val

        if not camera_id:
            continue

        # Coordinates: "lon,lat[,alt]" — no namespace
        lat = lon = None
        coords_elem = placemark.find(".//coordinates") or placemark.find(f".//{{{ns}}}coordinates")
        if coords_elem is not None and coords_elem.text:
            parts = coords_elem.text.strip().split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                except ValueError:
                    pass

        cameras.append({"id": camera_id, "name": name, "lat": lat, "lon": lon})

    return cameras
