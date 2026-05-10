"""Celery application configuration."""
from celery import Celery
from celery.schedules import crontab
from traffic_ai.config import settings, get_profile

app = Celery(
    "traffic_ai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "traffic_ai.tasks.sensor_tasks",
        "traffic_ai.tasks.risk_tasks",
        "traffic_ai.tasks.weather_tasks",
        "traffic_ai.tasks.camera_tasks",
        "traffic_ai.tasks.dump_tasks",
    ],
)
app.conf.update(
    task_serializer="json", accept_content=["json"], result_serializer="json",
    timezone="UTC", enable_utc=True, task_track_started=True, task_acks_late=True,
    worker_prefetch_multiplier=1, worker_concurrency=settings.celery_concurrency,
    worker_max_tasks_per_child=50,
    task_default_queue="default",
    task_reject_on_worker_lost=True,
    task_queue_max_priority=10,
    task_default_priority=5,
    # Camera tasks go to a dedicated queue consumed by celery_camera_worker.
    # This prevents 50s ONNX+HTTP batches from starving state/incident tasks.
    task_routes={
        "traffic_ai.tasks.sensor_tasks.poll_dgt_cameras":    {"queue": "cameras"},
        "traffic_ai.tasks.sensor_tasks.poll_madrid_cameras": {"queue": "cameras"},
    },
)
_profile = get_profile()
app.conf.beat_schedule = {
    # ── Barcelona Open Data BCN — traffic state, updated every 5 min
    "poll-barcelona": {
        "task": "traffic_ai.tasks.sensor_tasks.poll_barcelona",
        "schedule": 300.0,  # match source refresh rate — no point polling faster
        "options": {"priority": 7},
    },
    # ── DGT national incidents — incidents change slowly; 10 min is sufficient
    "poll-dgt-incidents": {
        "task": "traffic_ai.tasks.sensor_tasks.poll_dgt_incidents",
        "schedule": 600.0,
        "options": {"priority": 6},
    },
    # ── DGT national cameras — Redis-locked, back-to-back batches of 200
    # Beat fires every 30s; Redis lock prevents overlapping runs.
    # At ~5s/batch (200 cams) → all 1,916 cameras cycled every ~5 min.
    "poll-dgt-cameras": {
        "task": "traffic_ai.tasks.sensor_tasks.poll_dgt_cameras",
        "schedule": 30.0,
        "options": {"priority": 3},  # lower priority than state tasks
    },
    # ── Madrid city cameras — round-robin, 5-min official refresh
    "poll-madrid-cameras": {
        "task": "traffic_ai.tasks.sensor_tasks.poll_madrid_cameras",
        "schedule": 300.0,
        "options": {"priority": 3},
    },
    # ── Madrid Informo per-tramo traffic state — updated every 5 min
    "poll-madrid-traffic-state": {
        "task": "traffic_ai.tasks.sensor_tasks.poll_madrid_traffic_state",
        "schedule": 300.0,  # match source refresh rate
        "options": {"priority": 7},
    },
    # ── Valencia city real-time traffic state — updated every 3 min
    "poll-valencia-traffic": {
        "task": "traffic_ai.tasks.sensor_tasks.poll_valencia_traffic",
        "schedule": 180.0,  # match source refresh rate
        "options": {"priority": 7},
    },
    # ── TomTom flow — 40 intercity corridor points, every 30 min
    # 40 × 48 polls/day = 1,920 calls/day (77% of 2,500 free-tier limit).
    # 30-min resolution sufficient for MITMA hourly crosscheck validation.
    # Points cover Spain-wide corridors where sensor networks have no coverage.
    "poll-tomtom-flow": {
        "task": "traffic_ai.tasks.sensor_tasks.poll_tomtom_flow",
        "schedule": 1800.0,
        "options": {"priority": 6},
    },
    # ── Nightly R2 dump — runs at 02:00 UTC, dumps previous day to Cloudflare R2
    "dump-influx-to-r2": {
        "task": "traffic_ai.tasks.dump_tasks.dump_influx_to_r2",
        "schedule": crontab(hour=2, minute=0),
        "options": {"priority": 2},
    },
    # ── Weather
    "poll-weather": {
        "task": "traffic_ai.tasks.weather_tasks.poll_all_weather",
        "schedule": float(_profile.weather_poll_interval_s),
    },
    # ── Risk scoring — disabled until loop detector data populates RoadSegment table.
    # compute_all_risk_scores queries ALL segments (potentially 2.7M) and dispatches
    # one task per segment — OOMs the worker with no data to score.
    # "compute-risk-scores": {
    #     "task": "traffic_ai.tasks.risk_tasks.compute_all_risk_scores",
    #     "schedule": float(_profile.risk_compute_interval_s),
    # },
    # ── Baseline recalculation — disabled until loop detector data exists
    # Iterates 2.7M segments × InfluxDB queries — prohibitively slow with no data.
    # Re-enable once loop_detector measurements appear in InfluxDB.
    # "recalculate-baselines": {
    #     "task": "traffic_ai.tasks.sensor_tasks.recalculate_baselines",
    #     "schedule": float(_profile.baseline_recalc_interval_s),
    # },
}
