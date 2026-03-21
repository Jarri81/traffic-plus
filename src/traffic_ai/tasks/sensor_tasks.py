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

@app.task(name="traffic_ai.tasks.sensor_tasks.poll_madrid_loops", bind=True, max_retries=2)
def poll_madrid_loops(self) -> dict:
    """Fetch Madrid real-time traffic intensity from datos.madrid.es (5-min CSV)."""
    from traffic_ai.ingestors.madrid_loops import MadridLoopIngestor
    ingestor = MadridLoopIngestor()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(ingestor.start())
        results = loop.run_until_complete(ingestor.poll())
        logger.info("Madrid loops: ingested %d sensor readings", len(results))
        return {"ingested": len(results), "source": "madrid_loops"}
    except Exception as exc:
        logger.exception("Madrid loop ingestor failed")
        raise self.retry(exc=exc, countdown=60)
    finally:
        loop.close()


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
    from traffic_ai.db.database import init_db, async_session_factory

    async def _run() -> dict:
        await init_db()
        assert async_session_factory is not None
        async with async_session_factory() as session:
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

@app.task(name="traffic_ai.tasks.sensor_tasks.poll_dgt_cameras", bind=True, max_retries=2)
def poll_dgt_cameras(self) -> dict:
    """Fetch DGT national camera snapshots and run vehicle detection."""
    from traffic_ai.ingestors.dgt_cameras import DGTCameraIngestor
    ingestor = DGTCameraIngestor()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(ingestor.start())
        results = loop.run_until_complete(ingestor.poll())
        logger.info("DGT cameras: processed %d snapshots", len(results))
        return {"processed": len(results), "source": "dgt_cameras"}
    except Exception as exc:
        logger.exception("DGT camera ingestor failed")
        raise self.retry(exc=exc, countdown=120)
    finally:
        loop.close()


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


# ── Baseline recalculation ───────────────────────────────────────────────────

@app.task(name="traffic_ai.tasks.sensor_tasks.recalculate_baselines")
def recalculate_baselines() -> dict:
    """Recalculate speed baselines for all segments from InfluxDB history."""
    logger.info("Recalculating speed baselines")
    loop = asyncio.new_event_loop()
    try:
        async def _run():
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
            from traffic_ai.analytics.baseline import BaselineCalculator
            engine = create_async_engine(settings.database_url)
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with session_factory() as session:
                calculator = BaselineCalculator(db=session)
                count = await calculator.recalculate_all()
                await session.commit()
            await engine.dispose()
            return count
        count = loop.run_until_complete(_run())
    finally:
        loop.close()
    return {"segments_updated": count}
