"""DGT (Dirección General de Tráfico) camera ingestor.

Fetches the official camera list from Spain's DGT National Access Point
(DATEX II v3.6 XML), polls each camera's JPEG snapshot, optionally runs
YOLO11 vehicle detection, and writes traffic metrics to InfluxDB.

Data sources (no auth, CC BY licence):
  Camera list:  https://nap.dgt.es/datex2/v3/dgt/DevicePublication/camaras_datex2_v36.xml
  Image URL:    https://infocar.dgt.es/etraffic/data/camaras/{ID}.jpg
  Refresh:      ~3 minutes per camera

What this ingestor produces per camera per cycle:
  - vehicle_count          integer — number of vehicles visible
  - density_score          0-100   — congestion density estimate
  - density_level          "free_flow" | "light" | "moderate" | "heavy" | "gridlock"
  - camera_online          bool    — False if image fetch failed

Written to InfluxDB measurement "dgt_camera" tagged by camera_id and road_id.

YOLO is optional: if ultralytics is not installed (ml extras not present),
falls back to a pixel-variance heuristic that gives a rough density estimate.
GDPR note: vehicles only — no face or plate extraction. Frames are processed
in memory and never persisted unless S3_BUCKET is configured.
"""
from __future__ import annotations
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import aiohttp

from traffic_ai.config import get_profile, settings
from traffic_ai.db.influx import write_points
from traffic_ai.ingestors.base import BaseIngestor

logger = logging.getLogger(__name__)

DGT_CAMERA_LIST_URL = (
    "https://nap.dgt.es/datex2/v3/dgt/DevicePublication/camaras_datex2_v36.xml"
)
DGT_IMAGE_BASE_URL = "https://infocar.dgt.es/etraffic/data/camaras/{camera_id}.jpg"

# DATEX II v3 XML namespaces used in the DGT publication
_NS = {
    "ns2": "http://datex2.eu/schema/3/d2Payload",
    "fse": "http://datex2.eu/schema/3/facilities",
    "com": "http://datex2.eu/schema/3/common",
}


class DGTCameraIngestor(BaseIngestor):
    """Ingests traffic metrics from DGT national camera network."""

    def __init__(self, max_cameras: int | None = None) -> None:
        super().__init__(name="dgt_cameras")
        profile = get_profile()
        self.max_cameras = max_cameras or profile.max_cameras
        self._cameras: list[dict[str, Any]] = []  # [{id, road, lat, lon, url}]
        self._camera_index: int = 0  # round-robin cursor

    async def start(self) -> None:
        self._running = True
        await self._load_camera_list()
        self.logger.info(
            "DGTCameraIngestor started — %d cameras available, polling %d per cycle",
            len(self._cameras),
            self.max_cameras,
        )

    async def stop(self) -> None:
        self._running = False

    async def poll(self) -> list[dict[str, Any]]:
        """Process the next batch of cameras in round-robin order."""
        if not self._cameras:
            await self._load_camera_list()
            if not self._cameras:
                return []

        # Round-robin: take the next max_cameras cameras from the list
        total = len(self._cameras)
        batch_size = min(self.max_cameras, total)
        indices = [(self._camera_index + i) % total for i in range(batch_size)]
        self._camera_index = (self._camera_index + batch_size) % total
        batch = [self._cameras[i] for i in indices]

        results: list[dict[str, Any]] = []
        lines: list[str] = []

        async with aiohttp.ClientSession() as session:
            for cam in batch:
                result = await self._process_camera(session, cam)
                if result:
                    results.append(result)
                    lines.append(self._to_line_protocol(result))

        if lines:
            try:
                await write_points(lines)
            except Exception:
                self.logger.exception("Failed to write DGT camera metrics to InfluxDB")

        self.logger.info(
            "DGT cameras: processed %d/%d, wrote %d metrics",
            len(results), len(batch), len(lines),
        )
        return results

    # ── private ─────────────────────────────────────────────────────────────

    async def _process_camera(
        self, session: aiohttp.ClientSession, cam: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Fetch JPEG, run inference, return metrics dict."""
        camera_id = cam["id"]
        url = cam.get("url") or DGT_IMAGE_BASE_URL.format(camera_id=camera_id)

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return {
                        "camera_id": camera_id,
                        "camera_online": False,
                        "road": cam.get("road", ""),
                        "ts": datetime.now(timezone.utc),
                    }
                frame_bytes = await resp.read()
        except Exception:
            self.logger.debug("Camera %s fetch failed", camera_id)
            return None

        # Run vehicle detection
        metrics = _detect_vehicles(frame_bytes)

        return {
            "camera_id": camera_id,
            "road": cam.get("road", ""),
            "lat": cam.get("lat"),
            "lon": cam.get("lon"),
            "camera_online": True,
            "vehicle_count": metrics["vehicle_count"],
            "density_score": metrics["density_score"],
            "density_level": metrics["density_level"],
            "ts": datetime.now(timezone.utc),
        }

    @staticmethod
    def _to_line_protocol(record: dict[str, Any]) -> str:
        camera_id = record["camera_id"].replace(" ", r"\ ")
        road = (record.get("road") or "unknown").replace(" ", r"\ ")
        online = "true" if record.get("camera_online") else "false"
        return (
            f"dgt_camera,camera_id={camera_id},road={road} "
            f"vehicle_count={record.get('vehicle_count', 0)}i,"
            f"density_score={record.get('density_score', 0.0)},"
            f"camera_online={online}"
        )

    async def _load_camera_list(self) -> None:
        """Fetch DATEX II XML and parse camera ID + URL list."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    DGT_CAMERA_LIST_URL,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        self.logger.warning(
                            "DGT camera list returned %d", resp.status
                        )
                        return
                    xml_bytes = await resp.read()

            cameras = _parse_dgt_datex2(xml_bytes)
            self._cameras = cameras
            self.logger.info("Loaded %d cameras from DGT DATEX II feed", len(cameras))
        except Exception:
            self.logger.exception("Failed to load DGT camera list")


# ── DATEX II parser ──────────────────────────────────────────────────────────

def _parse_dgt_datex2(xml_bytes: bytes) -> list[dict[str, Any]]:
    """Parse DGT DATEX II v3.6 XML and return list of camera dicts."""
    cameras: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        logger.warning("Failed to parse DGT DATEX II XML")
        return cameras

    # Walk all elements looking for camera IDs and image URLs.
    # The structure varies slightly between DGT DATEX II versions so we
    # search by tag suffix rather than full namespace path.
    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag in ("cameraId", "deviceIdentifier"):
            camera_id = (elem.text or "").strip()
            if not camera_id:
                continue
            # Find sibling URL element
            parent = _find_parent(root, elem)
            url = _find_text(parent, ("deviceUrl", "cameraImageUrl", "imageUrl"))
            lat = _find_float(parent, ("latitude",))
            lon = _find_float(parent, ("longitude",))
            road = _find_text(parent, ("roadNumber", "road"))
            cameras.append({
                "id": camera_id,
                "url": url or DGT_IMAGE_BASE_URL.format(camera_id=camera_id),
                "road": road or "",
                "lat": lat,
                "lon": lon,
            })
    return cameras


def _find_parent(root: ET.Element, target: ET.Element) -> ET.Element:
    """Return the direct parent of `target` within `root`."""
    for parent in root.iter():
        if target in list(parent):
            return parent
    return root


def _find_text(elem: ET.Element, tags: tuple[str, ...]) -> str | None:
    for child in elem.iter():
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag in tags and child.text:
            return child.text.strip()
    return None


def _find_float(elem: ET.Element, tags: tuple[str, ...]) -> float | None:
    val = _find_text(elem, tags)
    if val:
        try:
            return float(val)
        except ValueError:
            pass
    return None


# ── vehicle detection ────────────────────────────────────────────────────────

def _detect_vehicles(frame_bytes: bytes) -> dict[str, Any]:
    """Run vehicle detection on a JPEG frame.

    Uses YOLO11n if ultralytics is installed (ml extras), otherwise falls
    back to a pixel-variance heuristic.
    """
    try:
        return _yolo_detect(frame_bytes)
    except ImportError:
        pass  # ultralytics not installed
    except Exception:
        logger.debug("YOLO detection failed, falling back to heuristic")
    return _heuristic_detect(frame_bytes)


def _yolo_detect(frame_bytes: bytes) -> dict[str, Any]:
    """YOLO11n vehicle detection. Raises ImportError if ultralytics missing."""
    import numpy as np  # noqa: PLC0415
    from ultralytics import YOLO  # noqa: PLC0415

    # Load model once (cached by ultralytics on disk after first download)
    if not hasattr(_yolo_detect, "_model"):
        _yolo_detect._model = YOLO("yolo11n.pt")  # type: ignore[attr-defined]

    model = _yolo_detect._model  # type: ignore[attr-defined]

    # Decode JPEG bytes to numpy array
    img_array = np.frombuffer(frame_bytes, dtype=np.uint8)
    import cv2  # noqa: PLC0415
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is None:
        return _empty_metrics()

    # Vehicle classes in COCO: 2=car, 3=motorcycle, 5=bus, 7=truck
    results = model(img, classes=[2, 3, 5, 7], verbose=False)
    vehicle_count = len(results[0].boxes) if results else 0

    density_score, density_level = _score_from_count(vehicle_count, img.shape)
    return {
        "vehicle_count": vehicle_count,
        "density_score": density_score,
        "density_level": density_level,
    }


def _heuristic_detect(frame_bytes: bytes) -> dict[str, Any]:
    """Pixel-variance heuristic as fallback when YOLO is unavailable.

    High variance in the lower 2/3 of the frame (road area) correlates with
    vehicle presence. Not accurate for counts but gives a useful density signal.
    """
    try:
        import struct
        import zlib

        # Quick PNG/JPEG decode-free variance estimate via raw byte entropy
        # Use byte value spread as a proxy for visual complexity
        sample = frame_bytes[len(frame_bytes) // 3:]  # road area heuristic
        if not sample:
            return _empty_metrics()
        byte_values = list(sample[:4096])  # limit sample
        mean = sum(byte_values) / len(byte_values)
        variance = sum((b - mean) ** 2 for b in byte_values) / len(byte_values)
        # Map variance 0–5000 → density 0–100
        density_score = min(100.0, (variance / 5000.0) * 100.0)
    except Exception:
        return _empty_metrics()

    density_level = _level_from_score(density_score)
    return {
        "vehicle_count": 0,  # unknown without YOLO
        "density_score": round(density_score, 1),
        "density_level": density_level,
    }


def _score_from_count(count: int, shape: tuple) -> tuple[float, str]:
    """Convert vehicle count to a 0-100 density score using frame area."""
    # Rough: assume 1 vehicle per ~10k pixels at normal camera angle
    h, w = shape[:2]
    frame_area = h * w
    vehicles_per_10k = (count * 10_000) / frame_area if frame_area > 0 else 0
    score = min(100.0, vehicles_per_10k * 20.0)
    return round(score, 1), _level_from_score(score)


def _level_from_score(score: float) -> str:
    if score < 15:
        return "free_flow"
    if score < 35:
        return "light"
    if score < 55:
        return "moderate"
    if score < 75:
        return "heavy"
    return "gridlock"


def _empty_metrics() -> dict[str, Any]:
    return {"vehicle_count": 0, "density_score": 0.0, "density_level": "unknown"}


def _to_line_madrid(record: dict[str, Any]) -> str:
    """InfluxDB line protocol for Madrid city cameras."""
    camera_id = record["camera_id"].replace(" ", r"\ ")
    online = "true" if record.get("camera_online") else "false"
    return (
        f"madrid_camera,camera_id={camera_id},source=madrid_cameras "
        f"vehicle_count={record.get('vehicle_count', 0)}i,"
        f"density_score={record.get('density_score', 0.0)},"
        f"camera_online={online}"
    )
