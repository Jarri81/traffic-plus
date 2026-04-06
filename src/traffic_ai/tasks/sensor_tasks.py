"""Celery tasks for sensor and open-data ingestion.

Tasks:
  poll_loop_detectors     — generic loop detector URLs (from config)
  poll_madrid_loops       — Madrid Ayuntamiento 4,000+ sensors (fixed public URL)
  poll_barcelona          — Barcelona Open Data BCN traffic state
  poll_dgt_incidents      — DGT national road incidents (DATEX II)
  recalculate_baselines   — rebuild speed baseline table from InfluxDB history
"""
from __future__ import annotations
import asyncio
import logging
from traffic_ai.celery_app import app
from traffic_ai.config import get_profile, settings

logger = logging.getLogger(__name__)


# ── Generic loop detector (configurable URLs) ────────────────────────────────

@app.task(name="traffic_ai.tasks.sensor_tasks.poll_loop_detectors")
def poll_loop_detectors() -> dict:
    """Poll generic loop detector URLs configured in LOOP_DETECTOR_URLS."""
    from traffic_ai.ingestors.loop_detector import LoopDetectorIngestor
    profile = get_profile()
    detector_urls = settings.loop_detector_url_list
    logger.info(
        "Polling generic loop detectors (max=%d, configured=%d)",
        profile.max_loop_detectors, len(detector_urls),
    )
    ingestor = LoopDetectorIngestor(detector_urls=detector_urls[:profile.max_loop_detectors])
    loop = asyncio.new_event_loop()
    try:
        results = loop.run_until_complete(ingestor.poll())
    finally:
        loop.close()
    return {"polled": len(results)}


# ── Madrid Ayuntamiento loop detectors ───────────────────────────────────────

@app.task(name="traffic_ai.tasks.sensor_tasks.poll_madrid_loops", bind=True, max_retries=0)
def poll_madrid_loops(self) -> dict:
    """Legacy task — datos.madrid.es CSV feed replaced by pm.xml (poll_madrid_traffic_state)."""
    return {"ingested": 0, "source": "madrid_loops"}


# ── Barcelona Open Data BCN ──────────────────────────────────────────────────

@app.task(name="traffic_ai.tasks.sensor_tasks.poll_barcelona", bind=True, max_retries=2)
def poll_barcelona(self) -> dict:
    """Fetch Barcelona real-time traffic state from Open Data BCN."""
    from traffic_ai.ingestors.barcelona import BarcelonaIngestor
    ingestor = BarcelonaIngestor()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(ingestor.start())
        results = loop.run_until_complete(ingestor.poll())
        logger.info("Barcelona: ingested %d traffic state records", len(results))
        return {"ingested": len(results), "source": "barcelona"}
    except Exception as exc:
        logger.exception("Barcelona ingestor failed")
        raise self.retry(exc=exc, countdown=60)
    finally:
        loop.close()


# ── DGT incidents ────────────────────────────────────────────────────────────

@app.task(name="traffic_ai.tasks.sensor_tasks.poll_dgt_incidents", bind=True, max_retries=2)
def poll_dgt_incidents(self) -> dict:
    """Fetch DGT national road incidents from DATEX II XML feed."""
    from traffic_ai.ingestors.dgt_incidents import DGTIncidentsIngestor
    import traffic_ai.db.database as db

    async def _run() -> dict:
        await db.init_db()
        assert db.async_session_factory is not None
        async with db.async_session_factory() as session:
            ingestor = DGTIncidentsIngestor(db=session)
            await ingestor.start()
            results = await ingestor.poll()
            await session.commit()
        return {"parsed": len(results), "source": "dgt_incidents"}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:
        logger.exception("DGT incidents ingestor failed")
        raise self.retry(exc=exc, countdown=120)
    finally:
        loop.close()


# ── DGT camera polling ───────────────────────────────────────────────────────
# Singleton ingestor — persists round-robin cursor across task invocations
_dgt_camera_ingestor = None

@app.task(name="traffic_ai.tasks.sensor_tasks.poll_dgt_cameras", bind=True, max_retries=0)
def poll_dgt_cameras(self) -> dict:
    """Fetch one batch of DGT camera snapshots and run vehicle detection.

    Uses a Redis lock to prevent overlapping runs. Beat fires every 30s;
    if the previous batch is still running the task skips immediately.
    This gives continuous back-to-back processing with no idle gaps.
    Camera list is sorted once: major highways first, then round-robin.
    """
    import redis as _redis
    global _dgt_camera_ingestor

    LOCK_KEY = "dgt_cameras:running"
    LOCK_TTL = 300  # 5-min safety TTL in case of crash

    r = _redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
    acquired = r.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL)
    if not acquired:
        logger.debug("DGT cameras: previous batch still running, skipping")
        return {"processed": 0, "source": "dgt_cameras", "skipped": True}

    from traffic_ai.ingestors.dgt_cameras import DGTCameraIngestor
    if _dgt_camera_ingestor is None:
        _dgt_camera_ingestor = DGTCameraIngestor()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_dgt_camera_ingestor.start())
        results = loop.run_until_complete(_dgt_camera_ingestor.poll())
        logger.info("DGT cameras: processed %d snapshots", len(results))
        return {"processed": len(results), "source": "dgt_cameras"}
    except Exception as exc:
        logger.exception("DGT camera ingestor failed")
        return {"processed": 0, "source": "dgt_cameras", "error": str(exc)}
    finally:
        loop.close()
        r.delete(LOCK_KEY)


# ── Madrid city cameras ──────────────────────────────────────────────────────

@app.task(name="traffic_ai.tasks.sensor_tasks.poll_madrid_cameras", bind=True, max_retries=2)
def poll_madrid_cameras(self) -> dict:
    """Fetch Madrid city camera snapshots and run vehicle detection."""
    from traffic_ai.ingestors.madrid_cameras import MadridCameraIngestor
    ingestor = MadridCameraIngestor()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(ingestor.start())
        results = loop.run_until_complete(ingestor.poll())
        logger.info("Madrid cameras: processed %d snapshots", len(results))
        return {"processed": len(results), "source": "madrid_cameras"}
    except Exception as exc:
        logger.exception("Madrid camera ingestor failed")
        raise self.retry(exc=exc, countdown=120)
    finally:
        loop.close()


# ── Madrid real-time traffic state (Informo tramos) ──────────────────────────

@app.task(name="traffic_ai.tasks.sensor_tasks.poll_madrid_traffic_state", bind=True, max_retries=2)
def poll_madrid_traffic_state(self) -> dict:
    """Fetch Madrid per-tramo real-time state from informo.madrid.es XML (5-min)."""
    from traffic_ai.ingestors.madrid_traffic_state import MadridTrafficStateIngestor
    ingestor = MadridTrafficStateIngestor()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(ingestor.start())
        results = loop.run_until_complete(ingestor.poll())
        logger.info("Madrid traffic state: ingested %d tramo readings", len(results))
        return {"ingested": len(results), "source": "madrid_traffic_state"}
    except Exception as exc:
        logger.exception("Madrid traffic state ingestor failed")
        raise self.retry(exc=exc, countdown=60)
    finally:
        loop.close()


# ── Valencia real-time traffic state ─────────────────────────────────────────

@app.task(name="traffic_ai.tasks.sensor_tasks.poll_valencia_traffic", bind=True, max_retries=2)
def poll_valencia_traffic(self) -> dict:
    """Fetch Valencia city real-time traffic state from RTOD open API (3-min)."""
    from traffic_ai.ingestors.valencia_traffic import ValenciaTrafficIngestor
    ingestor = ValenciaTrafficIngestor()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(ingestor.start())
        results = loop.run_until_complete(ingestor.poll())
        logger.info("Valencia traffic: ingested %d segment readings", len(results))
        return {"ingested": len(results), "source": "valencia_traffic"}
    except Exception as exc:
        logger.exception("Valencia traffic ingestor failed")
        raise self.retry(exc=exc, countdown=60)
    finally:
        loop.close()


# ── TomTom national incidents ────────────────────────────────────────────────

@app.task(name="traffic_ai.tasks.sensor_tasks.poll_tomtom_incidents", bind=True, max_retries=2)
def poll_tomtom_incidents(self) -> dict:
    """Fetch national Spain incidents from TomTom Traffic API (5-min, 1 call/poll)."""
    from traffic_ai.ingestors.tomtom import TomTomIncidentsIngestor
    ingestor = TomTomIncidentsIngestor()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(ingestor.start())
        results = loop.run_until_complete(ingestor.poll())
        logger.info("TomTom incidents: ingested %d records", len(results))
        return {"ingested": len(results), "source": "tomtom_incidents"}
    except Exception as exc:
        logger.exception("TomTom incidents ingestor failed")
        raise self.retry(exc=exc, countdown=60)
    finally:
        loop.close()


@app.task(name="traffic_ai.tasks.sensor_tasks.poll_tomtom_flow", bind=True, max_retries=2)
def poll_tomtom_flow(self) -> dict:
    """Fetch flow data for key Spanish highway points from TomTom (10-min)."""
    from traffic_ai.ingestors.tomtom import TomTomFlowIngestor
    ingestor = TomTomFlowIngestor()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(ingestor.start())
        results = loop.run_until_complete(ingestor.poll())
        logger.info("TomTom flow: ingested %d point readings", len(results))
        return {"ingested": len(results), "source": "tomtom_flow"}
    except Exception as exc:
        logger.exception("TomTom flow ingestor failed")
        raise self.retry(exc=exc, countdown=60)
    finally:
        loop.close()

