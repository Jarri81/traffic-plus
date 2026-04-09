"""LSTM congestion prediction model — ONNX Runtime inference.

Architecture
------------
Input features (per time-step):
  speed_kmh, occupancy_pct, flow_veh_per_min, hour_sin, hour_cos,
  dow_sin, dow_cos, precipitation_mm, wind_speed_kmh, temperature_c

Sequence length: 12 steps (default 5-min steps → 60-min history)
Output: predicted speed_kmh at H-minute horizon (default 30 min)

The trained model is saved as an ONNX file so inference needs only
onnxruntime (MIT license) — no PyTorch/TensorFlow at runtime.

Training: see scripts/train_congestion_model.py
ONNX export: produces ~/.cache/traffic_ai/models/congestion_lstm.onnx
"""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Feature columns (must match training order)
FEATURE_COLS = [
    "speed_kmh",
    "occupancy_pct",
    "flow_veh_per_min",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "precipitation_mm",
    "wind_speed_kmh",
    "temperature_c",
]
N_FEATURES = len(FEATURE_COLS)
SEQ_LEN = 12  # 12 × 15-min steps = 3h history

# Horizon → output index mapping (all horizons trained as multi-output)
HORIZONS = {15: 0, 30: 1, 60: 2}

# Two-stream: weather forecast branch
WEATHER_COLS = ["precipitation_mm", "wind_speed_kmh", "temperature_c"]
WEATHER_IDXS = [FEATURE_COLS.index(c) for c in WEATHER_COLS]  # [7, 8, 9]
N_FORECAST_STEPS = 4  # next 4 × 15-min = 1-hour forecast

# Open-Meteo free forecast API (Madrid city centre)
_OPENMETEO_FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=40.4168&longitude=-3.7038"
    "&hourly=precipitation,windspeed_10m,temperature_2m"
    "&forecast_days=1&timezone=Europe%2FMadrid"
)

_CACHE_DIR = Path(
    os.environ.get(
        "MODEL_CACHE_DIR",
        Path.home() / ".cache" / "traffic_ai" / "models",
    )
)
ONNX_PATH = _CACHE_DIR / "congestion_lstm.onnx"


# ── Inference ────────────────────────────────────────────────────────────────


class CongestionPredictor:
    """ONNX Runtime LSTM inference wrapper.

    Loads the ONNX model lazily on first call.
    Falls back to the STL seasonal baseline when the model file is absent.
    """

    def __init__(self, model_path: Path | None = None) -> None:
        self._model_path = model_path or ONNX_PATH
        self._session = None

    def predict(
        self,
        sequence: "np.ndarray",
        horizon_minutes: int = 30,
        weather_forecast: "np.ndarray | None" = None,
    ) -> dict[str, Any]:
        """Predict speed and congestion level.

        Parameters
        ----------
        sequence:
            Float32 array of shape (SEQ_LEN, N_FEATURES).
        horizon_minutes:
            Prediction horizon — one of 15, 30, 60.
        weather_forecast:
            Optional float32 array of shape (N_FORECAST_STEPS, 3) with
            normalized (precip, wind, temp) for the next hour. When None,
            zeros are used (average weather assumption).

        Returns
        -------
        dict with keys: predicted_speed_kmh, congestion_level, confidence,
        horizon_minutes, model.
        """
        horizon_minutes = _nearest_horizon(horizon_minutes)
        if weather_forecast is None:
            weather_forecast = np.zeros((N_FORECAST_STEPS, len(WEATHER_COLS)), dtype=np.float32)
        try:
            session = self._get_session()
            return self._infer(session, sequence, weather_forecast, horizon_minutes)
        except Exception as exc:
            logger.warning("LSTM inference failed (%s), using heuristic", exc)
            return _heuristic_predict(sequence, horizon_minutes)

    # ── private ──────────────────────────────────────────────────────────────

    def _get_session(self):
        if self._session is None:
            import onnxruntime as ort  # noqa: PLC0415
            if not self._model_path.exists():
                raise FileNotFoundError(
                    f"Congestion model not found: {self._model_path}. "
                    "Run scripts/train_congestion_model.py first."
                )
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.inter_op_num_threads = 2
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._session = ort.InferenceSession(
                str(self._model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            logger.info("Loaded LSTM congestion model from %s", self._model_path)
        return self._session

    def _infer(self, session, sequence: "np.ndarray", weather_forecast: "np.ndarray", horizon_minutes: int) -> dict[str, Any]:
        # Ensure correct shapes: (1, SEQ_LEN, N_FEATURES) and (1, N_FORECAST_STEPS, 3)
        seq = np.asarray(sequence, dtype=np.float32)
        if seq.ndim == 2:
            seq = seq[np.newaxis, ...]
        wx = np.asarray(weather_forecast, dtype=np.float32)
        if wx.ndim == 2:
            wx = wx[np.newaxis, ...]

        outputs = session.run(None, {"sequence": seq, "weather_forecast": wx})

        # outputs[0] shape: (1, len(HORIZONS)) — raw speed predictions
        preds = outputs[0][0]  # (len(HORIZONS),)
        h_idx = HORIZONS.get(horizon_minutes, 1)
        predicted_speed = float(np.clip(preds[h_idx], 0, 200))

        # Confidence: inverse of normalised prediction variance across horizons
        variance = float(np.var(preds))
        confidence = float(np.clip(1.0 - variance / 2000.0, 0.3, 0.95))

        # Derive congestion level from speed vs free-flow proxy
        free_flow = float(np.max(preds))  # highest horizon often = free flow
        ratio = predicted_speed / free_flow if free_flow > 0 else 0.5
        level = _ratio_to_level(ratio)

        return {
            "predicted_speed_kmh": round(predicted_speed, 1),
            "congestion_level": level,
            "confidence": round(confidence, 3),
            "horizon_minutes": horizon_minutes,
            "model": "lstm_onnx",
        }


# ── Module-level singleton ────────────────────────────────────────────────────

_predictor: CongestionPredictor | None = None


def get_predictor() -> CongestionPredictor:
    global _predictor
    if _predictor is None:
        _predictor = CongestionPredictor()
    return _predictor


def predict_congestion(
    sequence: "np.ndarray",
    horizon_minutes: int = 30,
    weather_forecast: "np.ndarray | None" = None,
) -> dict[str, Any]:
    """Module-level convenience wrapper."""
    return get_predictor().predict(sequence, horizon_minutes, weather_forecast)


async def fetch_weather_forecast() -> "np.ndarray":
    """Fetch next-hour weather forecast from Open-Meteo and return normalised
    (N_FORECAST_STEPS, 3) array ready for ONNX input.

    Uses the scaler saved during training to normalise the raw values.
    Falls back to zeros (average conditions) on any error.
    """
    import json
    try:
        import aiohttp
        from datetime import datetime, timezone as _tz

        async with aiohttp.ClientSession() as sess:
            async with sess.get(_OPENMETEO_FORECAST_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Open-Meteo returned {resp.status}")
                data = await resp.json()

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        precip = hourly.get("precipitation", [])
        wind = hourly.get("windspeed_10m", [])
        temp = hourly.get("temperature_2m", [])

        # Find the index of the current hour
        now_str = datetime.now(_tz.utc).strftime("%Y-%m-%dT%H:00")
        # Try local time string too (Open-Meteo returns local time)
        from datetime import datetime as _dt
        now_local = _dt.now().strftime("%Y-%m-%dT%H:00")
        idx = next((i for i, t in enumerate(times) if t == now_local or t == now_str), 0)

        # Build N_FORECAST_STEPS rows by interpolating hourly → 15-min
        rows = []
        for step in range(N_FORECAST_STEPS):
            hour_offset = step / 4.0  # 0.0, 0.25, 0.5, 0.75
            i0 = idx + int(hour_offset)
            i1 = min(i0 + 1, len(times) - 1)
            frac = hour_offset - int(hour_offset)
            p = float(precip[i0]) * (1 - frac) + float(precip[i1]) * frac if precip else 0.0
            w = float(wind[i0]) * (1 - frac) + float(wind[i1]) * frac if wind else 0.0
            t = float(temp[i0]) * (1 - frac) + float(temp[i1]) * frac if temp else 15.0
            rows.append([p, w, t])

        raw = np.array(rows, dtype=np.float32)  # (4, 3)

        # Normalise using training scaler
        scaler_path = _CACHE_DIR / "congestion_scaler.json"
        if scaler_path.exists():
            scaler = json.loads(scaler_path.read_text())
            mean = np.array(scaler["mean"], dtype=np.float32)[WEATHER_IDXS]
            std = np.array(scaler["std"], dtype=np.float32)[WEATHER_IDXS]
            raw = (raw - mean) / std

        return raw

    except Exception as exc:
        logger.debug("Weather forecast fetch failed (%s), using zeros", exc)
        return np.zeros((N_FORECAST_STEPS, len(WEATHER_COLS)), dtype=np.float32)


# ── Feature engineering helpers ──────────────────────────────────────────────


def encode_time_features(hour: int, dow: int) -> tuple[float, float, float, float]:
    """Cyclically encode hour and day-of-week to avoid discontinuities."""
    hour_sin = float(np.sin(2 * np.pi * hour / 24))
    hour_cos = float(np.cos(2 * np.pi * hour / 24))
    dow_sin = float(np.sin(2 * np.pi * dow / 7))
    dow_cos = float(np.cos(2 * np.pi * dow / 7))
    return hour_sin, hour_cos, dow_sin, dow_cos


def build_feature_row(
    speed_kmh: float,
    occupancy_pct: float,
    flow_veh_per_min: float,
    hour: int,
    dow: int,
    precipitation_mm: float = 0.0,
    wind_speed_kmh: float = 0.0,
    temperature_c: float = 15.0,
) -> "np.ndarray":
    """Build a single time-step feature vector (N_FEATURES,)."""
    h_sin, h_cos, d_sin, d_cos = encode_time_features(hour, dow)
    return np.array([
        speed_kmh,
        occupancy_pct,
        flow_veh_per_min,
        h_sin, h_cos,
        d_sin, d_cos,
        precipitation_mm,
        wind_speed_kmh,
        temperature_c,
    ], dtype=np.float32)


def build_sequence_from_influx(
    points: list[dict],
    weather_values: dict[str, float] | None = None,
) -> "np.ndarray | None":
    """Build (SEQ_LEN, N_FEATURES) array from InfluxDB query results.

    Parameters
    ----------
    points:
        List of dicts from query_points with keys: _time, speed_kmh,
        occupancy_pct, flow_veh_per_min.
    weather_values:
        Latest weather reading dict with optional keys: precipitation_mm,
        wind_speed_kmh, temperature_c.
    """
    from datetime import datetime, timezone  # noqa: PLC0415

    if not points:
        return None

    wx = weather_values or {}
    rows = []
    for p in points[-SEQ_LEN:]:
        ts = p.get("_time")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        row = build_feature_row(
            speed_kmh=float(p.get("speed_kmh") or p.get("_value") or 0),
            occupancy_pct=float(p.get("occupancy_pct", 0)),
            flow_veh_per_min=float(p.get("flow_veh_per_min", 0)),
            hour=ts.hour,
            dow=ts.weekday(),
            precipitation_mm=float(wx.get("precipitation_mm", 0)),
            wind_speed_kmh=float(wx.get("wind_speed_kmh", 0)),
            temperature_c=float(wx.get("temperature_c", 15)),
        )
        rows.append(row)

    if len(rows) < 2:
        return None

    # Pad to SEQ_LEN with first row if short
    while len(rows) < SEQ_LEN:
        rows.insert(0, rows[0])

    return np.stack(rows[-SEQ_LEN:], axis=0)  # (SEQ_LEN, N_FEATURES)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _nearest_horizon(minutes: int) -> int:
    return min(HORIZONS, key=lambda h: abs(h - minutes))


def _ratio_to_level(ratio: float) -> str:
    if ratio >= 0.85:
        return "free_flow"
    if ratio >= 0.65:
        return "moderate"
    if ratio >= 0.40:
        return "heavy"
    return "gridlock"


def _heuristic_predict(sequence: "np.ndarray", horizon_minutes: int) -> dict[str, Any]:
    """Simple last-observation + time-decay fallback."""
    try:
        last_speed = float(sequence[-1, 0])  # speed_kmh column
        # Very light persistence: assume mild improvement toward free flow
        decay = 1.0 + (horizon_minutes / 60.0) * 0.05
        predicted_speed = min(last_speed * decay, 130.0)
        level = _ratio_to_level(predicted_speed / 100.0)
        return {
            "predicted_speed_kmh": round(predicted_speed, 1),
            "congestion_level": level,
            "confidence": 0.30,
            "horizon_minutes": horizon_minutes,
            "model": "heuristic",
        }
    except Exception:
        return {
            "predicted_speed_kmh": 50.0,
            "congestion_level": "unknown",
            "confidence": 0.10,
            "horizon_minutes": horizon_minutes,
            "model": "heuristic",
        }
