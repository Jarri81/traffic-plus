"""InfluxDB async client wrapper.

Creates a fresh client per call to avoid event-loop binding issues in Celery
tasks (each task runs in its own asyncio.new_event_loop()).
"""
from __future__ import annotations
import logging
from typing import Any
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from traffic_ai.config import settings

logger = logging.getLogger(__name__)


def _make_client() -> InfluxDBClientAsync:
    return InfluxDBClientAsync(
        url=settings.influx_url,
        token=settings.influx_token,
        org=settings.influx_org,
    )


async def write_points(record: str | list[str], bucket: str | None = None) -> None:
    """Write line-protocol points to InfluxDB."""
    async with _make_client() as client:
        write_api = client.write_api()
        await write_api.write(bucket=bucket or settings.influx_bucket, record=record)


async def query_points(query: str, bucket: str | None = None) -> list[dict[str, Any]]:
    """Execute a Flux query and return results as a list of dicts."""
    async with _make_client() as client:
        query_api = client.query_api()
        tables = await query_api.query(query)
    results: list[dict[str, Any]] = []
    for table in tables:
        for record in table.records:
            results.append(record.values)
    return results


async def close_influx_client() -> None:
    """No-op — kept for API compatibility; no singleton to close."""
    pass


def get_influx_client() -> InfluxDBClientAsync:
    """Return a new InfluxDB client. Caller is responsible for closing it."""
    return _make_client()
