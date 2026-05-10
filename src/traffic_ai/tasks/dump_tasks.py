"""Nightly dump of InfluxDB measurements to Cloudflare R2 as Parquet files."""
from __future__ import annotations
import io
import logging
from datetime import datetime, timedelta, timezone

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from celery import shared_task
from influxdb_client import InfluxDBClient

from traffic_ai.config import settings

logger = logging.getLogger(__name__)

# Measurements to dump and their key fields
_MEASUREMENTS = {
    "madrid_traffic":    ["segment_id", "speed", "load", "occupancy", "intensity"],
    "barcelona_traffic": ["segment_id", "state_actual", "state_forecast"],
    "valencia_traffic":  ["segment_id", "state"],
    "dgt_camera":        ["camera_id", "road", "vehicle_count", "density_score", "camera_online"],
    "madrid_camera":     ["camera_id", "vehicle_count", "density_score", "camera_online"],
    "tomtom_flow":       ["point_id", "current_speed", "free_flow_speed", "density_score", "confidence"],
    "tomtom_incidents":  ["id", "type_name", "magnitude_name", "road", "city", "delay_s", "length_m", "lat", "lon"],
    "weather":           ["location", "temperature_2m", "wind_speed_10m", "precipitation", "relative_humidity_2m"],
}


def _get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def _query_measurement(client: InfluxDBClient, measurement: str, start: str, stop: str) -> pd.DataFrame:
    query = f"""
    from(bucket: "{settings.influx_bucket}")
      |> range(start: {start}, stop: {stop})
      |> filter(fn: (r) => r._measurement == "{measurement}")
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> keep(columns: ["_time"] + {list(_MEASUREMENTS[measurement])})
    """
    try:
        df = client.query_api().query_data_frame(query, org=settings.influx_org)
        if df is None or (isinstance(df, list) and len(df) == 0):
            return pd.DataFrame()
        if isinstance(df, list):
            df = pd.concat(df, ignore_index=True)
        if "_time" in df.columns:
            df = df.rename(columns={"_time": "timestamp"})
        drop_cols = [c for c in df.columns if c.startswith("_") or c in ("result", "table")]
        df = df.drop(columns=drop_cols, errors="ignore")
        return df
    except Exception:
        logger.exception("Failed to query measurement %s", measurement)
        return pd.DataFrame()


def _upload_parquet(r2, df: pd.DataFrame, key: str) -> bool:
    try:
        buf = io.BytesIO()
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, buf, compression="snappy")
        buf.seek(0)
        r2.put_object(Bucket=settings.r2_bucket, Key=key, Body=buf.getvalue())
        return True
    except Exception:
        logger.exception("Failed to upload %s to R2", key)
        return False


@shared_task(name="traffic_ai.tasks.dump_tasks.dump_influx_to_r2")
def dump_influx_to_r2(days_back: int = 1) -> dict:
    """Dump yesterday's InfluxDB data to R2 as Parquet, one file per measurement per day."""
    if not settings.r2_endpoint_url or not settings.r2_access_key_id:
        logger.warning("R2 credentials not configured — skipping dump")
        return {"status": "skipped", "reason": "no R2 credentials"}

    now = datetime.now(timezone.utc)
    stop_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = stop_dt - timedelta(days=days_back)
    date_str = start_dt.strftime("%Y-%m-%d")
    start = start_dt.isoformat()
    stop = stop_dt.isoformat()

    results = {}
    r2 = _get_r2_client()

    with InfluxDBClient(url=settings.influx_url, token=settings.influx_token, org=settings.influx_org) as client:
        for measurement in _MEASUREMENTS:
            df = _query_measurement(client, measurement, start, stop)
            if df.empty:
                logger.info("No data for %s on %s — skipping", measurement, date_str)
                results[measurement] = "empty"
                continue

            key = f"{measurement}/{date_str}.parquet"
            ok = _upload_parquet(r2, df, key)
            results[measurement] = f"uploaded {len(df)} rows → {key}" if ok else "upload_failed"
            logger.info("R2 dump %s: %s", measurement, results[measurement])

    return {"status": "done", "date": date_str, "measurements": results}
