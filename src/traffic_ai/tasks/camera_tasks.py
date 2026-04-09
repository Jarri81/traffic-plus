"""Celery tasks for camera frame processing."""
from __future__ import annotations
import asyncio
import logging

import aiohttp

from traffic_ai.celery_app import app
from traffic_ai.config import get_profile

logger = logging.getLogger(__name__)


@app.task(name="traffic_ai.tasks.camera_tasks.process_frame", bind=True, max_retries=3, default_retry_delay=30)
def process_frame(
    self,
    camera_id: str,
    url: str,
    road: str = "",
    measurement: str = "dgt_camera",
) -> dict:
    """Fetch a camera JPEG, run vehicle detection, write metrics to InfluxDB.

    Used when cameras are dispatched as individual Celery sub-tasks rather than
    processed inline inside the ingestor.  Each invocation is independent so
    a slow or offline camera doesn't block the rest of the batch.
    """
    profile = get_profile()

    async def _run() -> dict:
        from traffic_ai.db.influx import write_points
        from traffic_ai.ingestors.dgt_cameras import _detect_vehicles

        cam_id_esc = camera_id.replace(" ", r"\ ")
        road_esc = (road or "unknown").replace(" ", r"\ ")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        line = (
                            f"{measurement},camera_id={cam_id_esc},road={road_esc} "
                            f"vehicle_count=0i,density_score=0.0,camera_online=false"
                        )
                        await write_points([line])
                        return {"camera_id": camera_id, "camera_online": False, "road": road}
                    frame_bytes = await resp.read()
        except Exception as exc:
            logger.debug("Camera %s fetch failed: %s", camera_id, exc)
            return {"camera_id": camera_id, "camera_online": False, "road": road, "error": str(exc)}

        metrics = _detect_vehicles(frame_bytes)
        line = (
            f"{measurement},camera_id={cam_id_esc},road={road_esc} "
            f"vehicle_count={metrics['vehicle_count']}i,"
            f"density_score={metrics['density_score']},"
            f"camera_online=true"
        )
        await write_points([line])
        return {
            "camera_id": camera_id,
            "road": road,
            "camera_online": True,
            "onnx_enabled": profile.enable_onnx,
            **metrics,
        }

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_run())
        logger.info(
            "process_frame %s: online=%s vehicles=%d density=%.1f",
            camera_id,
            result.get("camera_online"),
            result.get("vehicle_count", 0),
            result.get("density_score", 0.0),
        )
        return result
    except Exception as exc:
        logger.exception("Frame processing failed for %s", camera_id)
        raise self.retry(exc=exc)
    finally:
        loop.close()
