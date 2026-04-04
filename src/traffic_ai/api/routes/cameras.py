"""Camera metrics endpoints — live data from InfluxDB camera ingestors."""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from traffic_ai.api.deps import get_current_user
from traffic_ai.config import settings
from traffic_ai.db.influx import query_points
from traffic_ai.ingestors.dgt_cameras import _DEFAULT_STRATEGY, _read_strategy
from traffic_ai.models.orm import User

logger = logging.getLogger(__name__)

router = APIRouter()

_STRATEGY_KEY = "camera:strategy"
_ROADS_CACHE_KEY = "camera:roads_cache"


def _image_url(cam_id: str, source: str) -> str:
    if source == "dgt":
        return f"https://infocar.dgt.es/etraffic/data/camaras/{cam_id}.jpg"
    # Madrid IDs stored as "madrid_123" — strip prefix
    numeric = cam_id.removeprefix("madrid_")
    import time as _time
    return f"https://informo.madrid.es/cameras/Camara{numeric}.jpg?v={int(_time.time())}"


@router.get("/cameras")
async def list_cameras(
    source: str | None = Query(None, description="Filter by source: dgt | madrid"),
    online_only: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return the latest metric snapshot for each known camera.

    Queries InfluxDB measurements `dgt_camera` and `madrid_camera` for the
    most recent reading per camera_id within the last 30 minutes.
    """
    results = []

    measurements = _resolve_measurements(source)
    for measurement, src_label in measurements:
        try:
            rows = await _query_latest_camera_metrics(measurement, limit)
            for row in rows:
                cam_id = row.get("camera_id", row.get("_measurement", "unknown"))
                online = row.get("camera_online", True)
                if online_only and not online:
                    continue
                results.append({
                    "id": cam_id,
                    "source": src_label,
                    "road": row.get("road", row.get("road_id", "")),
                    "vehicle_count": int(row.get("vehicle_count") or 0),
                    "density_score": round(float(row.get("density_score") or 0), 1),
                    "density_level": _density_level(float(row.get("density_score") or 0)),
                    "camera_online": bool(online),
                    "last_seen": row.get("_time", datetime.now(timezone.utc).isoformat()),
                    "image_url": _image_url(cam_id, src_label),
                })
        except Exception:
            logger.exception("Failed to query %s camera metrics", measurement)

    if not results:
        return _empty_camera_list(source)

    results.sort(key=lambda c: c["density_score"], reverse=True)
    return results[:limit]


@router.get("/cameras/stats")
async def camera_stats(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return aggregate camera statistics."""
    try:
        cameras = await list_cameras(
            source=None, online_only=False, limit=1000, current_user=current_user
        )
        total = len(cameras)
        online = sum(1 for c in cameras if c["camera_online"])
        offline = total - online
        avg_density = (
            sum(c["density_score"] for c in cameras) / total if total else 0
        )
        return {
            "total": total,
            "online": online,
            "offline": offline,
            "avg_density_score": round(avg_density, 1),
        }
    except Exception:
        logger.exception("Failed to compute camera stats")
        return {"total": 0, "online": 0, "offline": 0, "avg_density_score": 0.0}


# ── helpers ──────────────────────────────────────────────────────────────────


def _resolve_measurements(source: str | None) -> list[tuple[str, str]]:
    if source == "dgt":
        return [("dgt_camera", "dgt")]
    if source == "madrid":
        return [("madrid_camera", "madrid")]
    return [("dgt_camera", "dgt"), ("madrid_camera", "madrid")]


async def _query_latest_camera_metrics(measurement: str, limit: int) -> list[dict]:
    """Query most recent reading per camera from InfluxDB.

    Groups all fields for the same camera_id into a single row via pivot,
    so each returned dict represents one camera with all its fields present.
    """
    raw = await query_points(f"""
    from(bucket: "traffic_metrics")
      |> range(start: -30m)
      |> filter(fn: (r) => r._measurement == "{measurement}")
      |> last()
    """)

    # Group by camera_id tag → collect all field values into one dict
    by_cam: dict[str, dict] = {}
    for row in raw:
        cam_id = row.get("camera_id", "")
        if not cam_id:
            continue
        if cam_id not in by_cam:
            by_cam[cam_id] = {
                "camera_id": cam_id,
                "road": row.get("road", row.get("road_id", "")),
                "_time": row.get("_time"),
            }
        field = row.get("_field", "")
        val = row.get("_value")
        if field and val is not None:
            by_cam[cam_id][field] = val
        # Keep latest timestamp
        ts = row.get("_time")
        if ts and (by_cam[cam_id]["_time"] is None or ts > by_cam[cam_id]["_time"]):
            by_cam[cam_id]["_time"] = ts

    cameras = list(by_cam.values())
    return cameras[:limit]


def _density_level(score: float) -> str:
    if score < 15:
        return "free_flow"
    if score < 35:
        return "light"
    if score < 55:
        return "moderate"
    if score < 75:
        return "heavy"
    return "gridlock"


def _empty_camera_list(source: str | None) -> list[dict]:
    """Return stub entries so the UI shows something before ingestion starts."""
    sources = ["dgt", "madrid"] if source is None else [source]
    stubs = []
    for src in sources:
        for i in range(1, 4):
            stubs.append({
                "id": f"{src}_cam_{i:03d}",
                "source": src,
                "road": "",
                "vehicle_count": 0,
                "density_score": 0.0,
                "density_level": "unknown",
                "camera_online": False,
                "last_seen": None,
                "image_url": None,
            })
    return stubs


# ── Camera strategy endpoints ────────────────────────────────────────────────

@router.get("/cameras/strategy")
async def get_camera_strategy(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current camera gathering strategy and parameters."""
    strategy = _read_strategy()
    # Enrich with camera count estimate
    total, active = _estimate_camera_counts(strategy)
    batch_size = int(strategy.get("batch_size", 400))
    semaphore = int(strategy.get("semaphore", 30))
    cycle_minutes = round((active / batch_size) * (batch_size * 0.5 / 60), 1) if active else 0
    return {
        **strategy,
        "total_cameras": total,
        "active_cameras": active,
        "estimated_cycle_minutes": cycle_minutes,
    }


@router.put("/cameras/strategy")
async def set_camera_strategy(
    payload: dict,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Persist camera gathering strategy to Redis. Takes effect on next batch."""
    import redis as _redis

    mode = payload.get("mode", "all")
    if mode not in ("all", "roads", "bbox"):
        raise HTTPException(status_code=400, detail="mode must be 'all', 'roads', or 'bbox'")

    batch_size = max(50, min(800, int(payload.get("batch_size", 400))))
    semaphore  = max(5,  min(80,  int(payload.get("semaphore",  30))))

    strategy: dict[str, Any] = {
        "mode": mode,
        "roads": payload.get("roads", []),
        "bbox": payload.get("bbox", {}),
        "batch_size": batch_size,
        "semaphore": semaphore,
    }

    try:
        r = _redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        r.set(_STRATEGY_KEY, json.dumps(strategy))
        r.delete(_ROADS_CACHE_KEY)  # invalidate roads cache so counts refresh
        r.close()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}")

    total, active = _estimate_camera_counts(strategy)
    return {
        **strategy,
        "total_cameras": total,
        "active_cameras": active,
        "ok": True,
    }


@router.get("/cameras/roads")
async def list_camera_roads(
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return all roads with their camera counts, sorted by count desc.

    Result is cached in Redis for 1 hour (DGT XML rarely changes).
    """
    import redis as _redis

    try:
        r = _redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        cached = r.get(_ROADS_CACHE_KEY)
        if cached:
            r.close()
            return json.loads(cached)
    except Exception:
        r = None

    # Fetch live from DGT XML
    try:
        import aiohttp
        from traffic_ai.ingestors.dgt_cameras import _parse_dgt_datex2, _sort_by_priority

        async def _fetch():
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://nap.dgt.es/datex2/v3/dgt/DevicePublication/camaras_datex2_v36.xml",
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    return await resp.read()

        import asyncio
        xml_bytes = asyncio.get_event_loop().run_until_complete(_fetch())
        cameras = _parse_dgt_datex2(xml_bytes)
        road_counts: dict[str, int] = {}
        for cam in cameras:
            road = (cam.get("road") or "").strip()
            if road:
                road_counts[road] = road_counts.get(road, 0) + 1

        result = sorted(
            [{"road": r, "count": c} for r, c in road_counts.items()],
            key=lambda x: x["count"], reverse=True,
        )
        if r:
            r.set(_ROADS_CACHE_KEY, json.dumps(result), ex=3600)
            r.close()
        return result
    except Exception:
        logger.exception("Failed to fetch DGT camera road list")
        return []


def _estimate_camera_counts(strategy: dict) -> tuple[int, int]:
    """Return (total, active) camera counts based on strategy mode.

    Uses cached road list from Redis if available; falls back to totals.
    """
    TOTAL = 1916  # known total from DGT feed
    mode = strategy.get("mode", "all")
    if mode == "all":
        return TOTAL, TOTAL

    try:
        import redis as _redis
        r = _redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        cached = r.get(_ROADS_CACHE_KEY)
        r.close()
        if cached:
            roads_data = json.loads(cached)
            road_counts = {d["road"]: d["count"] for d in roads_data}

            if mode == "roads":
                selected = strategy.get("roads", [])
                active = sum(road_counts.get(r, 0) for r in selected)
                return TOTAL, active
    except Exception:
        pass

    # bbox or no cache — can't estimate accurately
    return TOTAL, TOTAL
