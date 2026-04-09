"""Train LSTM congestion prediction model and export to ONNX.

Usage
-----
    python scripts/train_congestion_model.py [--epochs 30] [--lookback-days 90]

Inputs
------
1. Madrid loop detector historical data  (datos.madrid.es CSV archives, 2013-present)
2. Open-Meteo historical weather archive  (free, no API key needed)
3. Optionally Barcelona / DGT loop data (same CSV format)

Output
------
  ~/.cache/traffic_ai/models/congestion_lstm.onnx  (~1-3 MB)

Training takes ~5-15 minutes on CPU for 90 days of Madrid data.

Requirements (training-only, not needed at runtime):
  pip install torch onnx scikit-learn pandas requests statsmodels
"""
from __future__ import annotations
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
CACHE_DIR = Path(os.environ.get("MODEL_CACHE_DIR", Path.home() / ".cache" / "traffic_ai" / "models"))
SCALER_PATH = CACHE_DIR / "congestion_scaler.json"
ONNX_OUT = CACHE_DIR / "congestion_lstm.onnx"

# ── Madrid historical data — direct ZIP downloads ────────────────────────────
# datos.gob.es CKAN API is broken (HTTP 500). Files are served directly from
# datos.madrid.es. URL pattern (verified 2024-03):
#   https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico/
#     resource/{ID}-transporte-ptomedida-historico-zip/download/
#     {ID}-transporte-ptomedida-historico-zip.zip
# Each ZIP contains a semicolon-delimited CSV (~80-90 MB uncompressed).
# Resource IDs verified against live portal (not derivable by formula).
MADRID_URL_TEMPLATE = (
    "https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico"
    "/resource/{rid}-transporte-ptomedida-historico-zip"
    "/download/{rid}-transporte-ptomedida-historico-zip.zip"
)

# (year, month) → resource_id  — verified 2019-01 through 2025-12
MADRID_RESOURCE_IDS: dict[tuple[int, int], str] = {
    # 2019
    (2019,  1): "208627-76",  (2019,  2): "208627-70",  (2019,  3): "208627-63",
    (2019,  4): "208627-57",  (2019,  5): "208627-120", (2019,  6): "208627-109",
    (2019,  7): "208627-39",  (2019,  8): "208627-32",  (2019,  9): "208627-25",
    (2019, 10): "208627-19",  (2019, 11): "208627-94",  (2019, 12): "208627-5",
    # 2020
    (2020,  1): "208627-150", (2020,  2): "208627-69",  (2020,  3): "208627-62",
    (2020,  4): "208627-56",  (2020,  5): "208627-51",  (2020,  6): "208627-45",
    (2020,  7): "208627-38",  (2020,  8): "208627-31",  (2020,  9): "208627-95",
    (2020, 10): "208627-18",  (2020, 11): "208627-129", (2020, 12): "208627-110",
    # 2021
    (2021,  1): "208627-75",  (2021,  2): "208627-121", (2021,  3): "208627-96",
    (2021,  4): "208627-151", (2021,  5): "208627-122", (2021,  6): "208627-44",
    (2021,  7): "208627-111", (2021,  8): "208627-97",  (2021,  9): "208627-115",
    (2021, 10): "208627-17",  (2021, 11): "208627-11",  (2021, 12): "208627-3",
    # 2022
    (2022,  1): "208627-82",  (2022,  2): "208627-68",  (2022,  3): "208627-124",
    (2022,  4): "208627-83",  (2022,  5): "208627-50",  (2022,  6): "208627-137",
    (2022,  7): "208627-114", (2022,  8): "208627-102", (2022,  9): "208627-24",
    (2022, 10): "208627-101", (2022, 11): "208627-10",  (2022, 12): "208627-0",
    # 2023
    (2023,  1): "208627-74",  (2023,  2): "208627-138", (2023,  3): "208627-61",
    (2023,  4): "208627-55",  (2023,  5): "208627-139", (2023,  6): "208627-140",
    (2023,  7): "208627-37",  (2023,  8): "208627-30",  (2023,  9): "208627-23",
    (2023, 10): "208627-84",  (2023, 11): "208627-125", (2023, 12): "208627-2",
    # 2024
    (2024,  1): "208627-141", (2024,  2): "208627-67",  (2024,  3): "208627-60",
    (2024,  4): "208627-54",  (2024,  5): "208627-49",  (2024,  6): "208627-43",
    (2024,  7): "208627-36",  (2024,  8): "208627-29",  (2024,  9): "208627-85",
    (2024, 10): "208627-16",  (2024, 11): "208627-9",   (2024, 12): "208627-1",
    # 2025 — discovered 2026-03 by probing resource IDs
    (2025,  1): "208627-73",  (2025,  2): "208627-103", (2025,  3): "208627-131",
    (2025,  4): "208627-86",  (2025,  5): "208627-112", (2025,  6): "208627-42",
    (2025,  7): "208627-123", (2025,  8): "208627-98",  (2025,  9): "208627-130",
    (2025, 10): "208627-15",  (2025, 11): "208627-100", (2025, 12): "208627-113",
}

# Columns in the 15-min measurement-point CSV (confirmed, semicolon-delimited):
#   idelem; tipo_elem; distrito; cod_cent; nombre; utm_x; utm_y;
#   longitud; latitud; fecha; intensidad; ocupacion; carga; nivelservicio;
#   error; subError
# 'intensidad' = vehicles/hour, 'ocupacion' = % occupancy, 'carga' = 0-100
# Note: no speed column in most historical files — we derive from carga.

# Open-Meteo historical archive — free, no key, CC BY 4.0
# Madrid city centre (lat=40.4168, lon=-3.7038)
# VERIFIED API parameter names (windspeed_10m, NOT wind_speed_10m;
# visibility is NOT available — use cloud_cover_low + weather_code for fog)
OPENMETEO_HIST_URL = (
    "https://archive-api.open-meteo.com/v1/archive"
    "?latitude=40.4168&longitude=-3.7038"
    "&start_date={start}&end_date={end}"
    "&hourly=temperature_2m,precipitation,windspeed_10m,cloud_cover_low,weather_code"
    "&timezone=Europe%2FMadrid"
)


# ── Feature columns (must match ml/congestion_model.py) ────────────────────
FEATURE_COLS = [
    "speed_kmh", "occupancy_pct", "flow_veh_per_min",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "precipitation_mm", "wind_speed_kmh", "temperature_c",
]
SEQ_LEN = 12          # 12 × 15-min = 3-hour lookback
HORIZONS = [15, 30, 60]  # predict 3 horizons simultaneously (minutes)
N_FEATURES = len(FEATURE_COLS)  # 10

# Two-stream: past traffic sequence + future weather forecast
WEATHER_COLS = ["precipitation_mm", "wind_speed_kmh", "temperature_c"]
WEATHER_IDXS = [FEATURE_COLS.index(c) for c in WEATHER_COLS]  # [7, 8, 9]
N_FORECAST_STEPS = 4   # next 4 × 15-min = 1-hour weather forecast


def main() -> None:
    parser = argparse.ArgumentParser(description="Train LSTM congestion model")
    parser.add_argument("--epochs", type=int, default=30, help="Training epochs")
    parser.add_argument("--lookback-days", type=int, default=90, help="Days of historical data")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--hidden-size", type=int, default=128, help="LSTM hidden units")
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--no-download", action="store_true", help="Skip data download (use cache)")
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=== Traffic AI — LSTM Congestion Model Training ===")
    logger.info("Lookback: %d days | Epochs: %d | Hidden: %d", args.lookback_days, args.epochs, args.hidden_size)

    # 1. Fetch data
    logger.info("Step 1/5 — Fetching historical data")
    sensor_df = fetch_madrid_historical(args.lookback_days, skip_download=args.no_download)
    weather_df = fetch_openmeteo_historical(args.lookback_days)

    if sensor_df is None or len(sensor_df) < SEQ_LEN * 10:
        logger.error("Not enough sensor data to train. Download failed or too few rows.")
        sys.exit(1)

    # 2. Merge + engineer features
    logger.info("Step 2/5 — Feature engineering (%d sensor rows)", len(sensor_df))
    df = merge_features(sensor_df, weather_df)

    # 3. Build sequences
    logger.info("Step 3/5 — Building training sequences")
    X, W, y, scaler_params = build_sequences(df)
    logger.info("  X shape: %s  W shape: %s  y shape: %s", X.shape, W.shape, y.shape)

    # Save scaler params (used at inference time inside the ONNX graph or as pre-processing)
    with open(SCALER_PATH, "w") as f:
        json.dump(scaler_params, f)
    logger.info("  Scaler saved: %s", SCALER_PATH)

    # 4. Train
    logger.info("Step 4/5 — Training")
    model = train(X, W, y, args, onnx_out=ONNX_OUT)

    # 5. Export to ONNX
    logger.info("Step 5/5 — Exporting to ONNX: %s", ONNX_OUT)
    export_onnx(model, ONNX_OUT)
    logger.info("Done. Model size: %.1f MB", ONNX_OUT.stat().st_size / 1e6)


# ── Data fetching ─────────────────────────────────────────────────────────────


def fetch_madrid_historical(lookback_days: int, skip_download: bool = False):
    """Download Madrid historical traffic ZIPs from datos.madrid.es.

    Each monthly ZIP contains a semicolon-delimited CSV with columns:
      idelem; tipo_elem; distrito; cod_cent; nombre; utm_x; utm_y;
      longitud; latitud; fecha; intensidad; ocupacion; carga; nivelservicio
      - intensidad  = vehicles/hour (flow)
      - ocupacion   = road occupancy 0-100 %
      - carga       = congestion index 0-100 (used as speed proxy)

    ZIPs are ~85 MB each; CSVs unzip to ~500 MB per month.
    Downloaded ZIPs are cached locally so reruns are instant.
    """
    try:
        import io
        import zipfile
        import pandas as pd
        import requests
    except ImportError:
        logger.error("pip install pandas requests is required for training")
        return None

    raw_dir = CACHE_DIR / "madrid_raw"
    raw_dir.mkdir(exist_ok=True)

    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=lookback_days)

    # Collect (year, month) pairs within the lookback window
    months_needed: list[tuple[int, int]] = []
    y, m = cutoff.year, cutoff.month
    while (y, m) <= (today.year, today.month):
        months_needed.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    dfs: list = []
    missing: list[tuple[int, int]] = []

    for year, month in months_needed:
        rid = MADRID_RESOURCE_IDS.get((year, month))
        if rid is None:
            missing.append((year, month))
            continue

        zip_path = raw_dir / f"madrid_{year}_{month:02d}.zip"
        url = MADRID_URL_TEMPLATE.format(rid=rid)

        if not zip_path.exists() and not skip_download:
            try:
                logger.info("  Downloading %d-%02d (%s)…", year, month, rid)
                r = requests.get(url, timeout=300, stream=True)
                if r.status_code != 200:
                    logger.warning("  HTTP %d for %d-%02d — skipping", r.status_code, year, month)
                    continue
                zip_path.write_bytes(r.content)
                logger.info("  Saved %s (%.1f MB)", zip_path.name, zip_path.stat().st_size / 1e6)
            except Exception as e:
                logger.warning("  Download failed for %d-%02d: %s", year, month, e)
                continue

        if zip_path.exists():
            logger.info("  Loading %d-%02d from cache…", year, month)
            df = _load_madrid_zip(zip_path)
            if df is not None:
                dfs.append(df)

    if missing:
        logger.warning(
            "No resource IDs for %d month(s) (outside 2019-2024 range): %s",
            len(missing),
            [f"{y}-{m:02d}" for y, m in missing[:6]],
        )

    if not dfs:
        logger.error(
            "No Madrid data loaded. Cannot train without real data.\n"
            "  Checked months: %s\n"
            "  Cache dir: %s\n"
            "  Re-run without --no-download or verify network access.",
            [f"{y}-{m:02d}" for y, m in months_needed[:6]],
            raw_dir,
        )
        return None

    logger.info("  Loaded %d monthly files", len(dfs))
    full = pd.concat(dfs, ignore_index=True)
    return _normalise_madrid_df(full)


def _load_madrid_zip(zip_path: Path):
    """Extract CSV from a monthly ZIP and return a city-level aggregated DataFrame.

    Each raw CSV has one row per sensor per 15-min slot (~4,000 sensors).
    We aggregate to city-wide averages per timestamp, reducing ~10M rows/month
    to ~3,000 rows/month so that pd.concat across 60 months stays in RAM.
    """
    import io
    import zipfile

    try:
        with zipfile.ZipFile(zip_path) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                logger.warning("No CSV in %s", zip_path.name)
                return None
            csv_name = max(csv_names, key=lambda n: zf.getinfo(n).file_size)
            with zf.open(csv_name) as f:
                raw = f.read()
    except Exception as e:
        logger.warning("Failed to open %s: %s", zip_path.name, e)
        return None

    return _parse_and_aggregate_madrid(raw, zip_path.name)


def _parse_and_aggregate_madrid(raw: bytes, source_name: str = ""):
    """Parse Madrid CSV bytes and aggregate all sensors to city-level per timestamp.

    Reads in 100k-row chunks to avoid OOM on large files (~500 MB uncompressed).
    Keeps only fecha, intensidad, ocupacion, carga (drops per-sensor metadata).
    Returns a DataFrame with one row per 15-min timestamp — ~3,000 rows/month.
    """
    import io
    import pandas as pd

    _KEEP = {"fecha", "intensidad", "ocupacion", "carga", "velocidad"}

    for sep in (";", ","):
        for enc in ("utf-8", "latin-1", "iso-8859-1"):
            try:
                # Peek at columns
                head = pd.read_csv(io.BytesIO(raw), sep=sep, encoding=enc, nrows=2, low_memory=False)
                if len(head.columns) <= 3:
                    continue
                cols_map = {c: c.strip().lower() for c in head.columns}
                use_cols = [orig for orig, norm in cols_map.items() if norm in _KEEP]
                if "fecha" not in [cols_map[c] for c in use_cols]:
                    continue  # no timestamp column — wrong separator

                # Read in chunks, normalise column names, keep only needed cols
                agg_chunks: list = []
                for chunk in pd.read_csv(
                    io.BytesIO(raw), sep=sep, encoding=enc,
                    usecols=use_cols, chunksize=100_000, low_memory=False,
                ):
                    chunk.columns = [c.strip().lower() for c in chunk.columns]
                    for col in ("intensidad", "ocupacion", "carga", "velocidad"):
                        if col in chunk.columns:
                            chunk[col] = pd.to_numeric(chunk[col], errors="coerce")
                    agg_chunks.append(chunk)

                df = pd.concat(agg_chunks, ignore_index=True)

                # Aggregate all sensors → city-level mean per timestamp
                num_cols = [c for c in ("intensidad", "ocupacion", "carga", "velocidad") if c in df.columns]
                city = df.groupby("fecha")[num_cols].mean().reset_index()
                logger.debug(
                    "Aggregated %s: %d timestamps (from %d raw rows)",
                    source_name, len(city), len(df),
                )
                return city

            except MemoryError:
                logger.warning("OOM reading %s — skipping", source_name)
                return None
            except Exception:
                continue

    logger.warning("Could not parse %s", source_name)
    return None


def _normalise_madrid_df(df):
    """Standardise column names from Madrid CSV to our internal schema.

    Confirmed 15-min measurement-point columns (semicolon delimited):
      idelem, tipo_elem, distrito, cod_cent, nombre, utm_x, utm_y,
      longitud, latitud, fecha, intensidad, ocupacion, carga, nivelservicio

    The 'carga' column (0-100 congestion index) is used to derive a
    pseudo-speed when no velocidad column is present:
      speed_proxy = free_flow_speed × (1 - carga/100)
    Free-flow speed defaults to 80 km/h (M-30 typical).
    """
    import pandas as pd

    # Lower-case all column names for consistent matching
    df.columns = [c.strip().lower() for c in df.columns]

    rename = {
        "intensidad": "flow_count",
        "ocupacion": "occupancy_pct",
        "velocidad": "speed_kmh",
        "carga": "carga",
        "fecha": "fecha",
        "idelem": "sensor_id",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    for col in ("flow_count", "occupancy_pct", "carga"):
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Derive speed from carga when not directly available
    if "speed_kmh" not in df.columns:
        FREE_FLOW = 80.0  # km/h — conservative M-30 free-flow speed
        df["speed_kmh"] = FREE_FLOW * (1.0 - df["carga"].clip(0, 100) / 100.0)
    else:
        df["speed_kmh"] = pd.to_numeric(df["speed_kmh"], errors="coerce").fillna(0)

    # Flow: intensidad is vehicles/hour → convert to per-min
    df["flow_veh_per_min"] = df["flow_count"] / 60.0

    # Hour of day from fecha timestamp
    if "fecha" in df.columns:
        try:
            df["hour"] = pd.to_datetime(df["fecha"], errors="coerce").dt.hour.fillna(0).astype(int)
            df["date"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date
        except Exception:
            df["hour"] = 0
            df["date"] = None
    elif "hour" not in df.columns:
        df["hour"] = 0

    return df


def _synthetic_sensor_data(days: int):
    """Generate realistic synthetic data when real CSV is unavailable."""
    import pandas as pd
    import numpy as np

    logger.info("Generating synthetic sensor data (%d days)", days)
    n = days * 24 * 12  # 5-min intervals
    rng = np.random.default_rng(42)
    t = np.arange(n)
    # Rush-hour pattern
    hours = (t * 5 // 60) % 24
    rush = ((hours >= 7) & (hours <= 9)) | ((hours >= 16) & (hours <= 19))
    speed_base = np.where(rush, 45.0, 90.0)
    speed = np.clip(speed_base + rng.normal(0, 8, n), 5, 130)
    flow = np.clip(np.where(rush, 60.0, 20.0) + rng.normal(0, 5, n), 0, 120)
    occ = np.clip(np.where(rush, 55.0, 15.0) + rng.normal(0, 5, n), 0, 100)
    return pd.DataFrame({
        "speed_kmh": speed,
        "flow_veh_per_min": flow / 5.0,
        "occupancy_pct": occ,
        "hour": hours,
        "date": pd.date_range("2025-01-01", periods=n, freq="5min").date,
    })


def fetch_openmeteo_historical(lookback_days: int):
    """Fetch weather from Open-Meteo historical archive (free, CC BY 4.0)."""
    try:
        import pandas as pd
        import requests
    except ImportError:
        return None

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=lookback_days + 1)
    url = OPENMETEO_HIST_URL.format(start=start, end=today)

    cached = CACHE_DIR / f"openmeteo_{start}_{today}.json"
    if cached.exists():
        with open(cached) as f:
            data = json.load(f)
    else:
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            data = r.json()
            with open(cached, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning("Open-Meteo fetch failed: %s — using zero weather", e)
            return None

    try:
        hourly = data.get("hourly", {})
        df = pd.DataFrame({
            "datetime": pd.to_datetime(hourly["time"]),
            "temperature_c": hourly.get("temperature_2m", [0] * len(hourly["time"])),
            "precipitation_mm": hourly.get("precipitation", [0] * len(hourly["time"])),
            # API param is 'windspeed_10m' (confirmed) not 'wind_speed_10m'
            "wind_speed_kmh": hourly.get("windspeed_10m", [0] * len(hourly["time"])),
            # visibility_m is NOT in Open-Meteo archive; use cloud_cover_low +
            # weather_code as fog proxy (codes 45=fog, 48=rime fog)
            "cloud_cover_low_pct": hourly.get("cloud_cover_low", [0] * len(hourly["time"])),
            "weather_code": hourly.get("weather_code", [0] * len(hourly["time"])),
        })
        # Derive a fog_factor 0-1: fog codes or high low-cloud cover
        df["fog_factor"] = (
            (df["weather_code"].isin([45, 48])).astype(float) * 0.7
            + (df["cloud_cover_low_pct"].clip(0, 100) / 100.0) * 0.3
        ).clip(0, 1)
        return df
    except Exception as e:
        logger.warning("Could not parse Open-Meteo response: %s", e)
        return None


# ── Feature engineering ───────────────────────────────────────────────────────


def merge_features(sensor_df, weather_df):
    """Merge sensor and weather data on hour, add cyclical time features."""
    import pandas as pd
    import numpy as np

    df = sensor_df.copy()

    if weather_df is not None:
        try:
            weather_df = weather_df.copy()
            weather_df["hour"] = weather_df["datetime"].dt.hour
            wx_cols = [c for c in ("temperature_c", "precipitation_mm", "wind_speed_kmh", "fog_factor")
                       if c in weather_df.columns]
            wx_hourly = weather_df.groupby("hour")[wx_cols].mean().reset_index()
            df = df.merge(wx_hourly, on="hour", how="left")
        except Exception as e:
            logger.warning("Weather merge failed: %s", e)

    defaults = {"temperature_c": 15.0, "precipitation_mm": 0.0, "wind_speed_kmh": 10.0, "fog_factor": 0.0}
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # Cyclical time features
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

    # Day of week — approximate from date if available
    if "date" in df.columns:
        try:
            df["dow"] = pd.to_datetime(df["date"]).dt.dayofweek
        except Exception:
            df["dow"] = 0
    else:
        df["dow"] = 0

    df["dow_sin"] = np.sin(2 * np.pi * df["dow"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["dow"] / 7)

    return df.dropna(subset=["speed_kmh"])


# ── Sequence building ─────────────────────────────────────────────────────────


def build_sequences(df):
    """Slide a window over the dataframe to create (X, y) training pairs."""
    import numpy as np

    feat_arr = df[FEATURE_COLS].values.astype(np.float32)

    # Compute mean/std for standardisation (saved as JSON scaler)
    mean = feat_arr.mean(axis=0)
    std = np.where(feat_arr.std(axis=0) > 1e-6, feat_arr.std(axis=0), 1.0)
    scaler = {"mean": mean.tolist(), "std": std.tolist(), "features": FEATURE_COLS}

    feat_norm = (feat_arr - mean) / std

    speed_col = FEATURE_COLS.index("speed_kmh")
    max_horizon_steps = max(HORIZONS) // 5  # steps for 60-min horizon

    X_list, W_list, y_list = [], [], []
    total = len(feat_norm)
    for i in range(SEQ_LEN, total - max_horizon_steps - N_FORECAST_STEPS):
        x = feat_norm[i - SEQ_LEN:i]                          # (SEQ_LEN, N_FEATURES)
        w = feat_norm[i:i + N_FORECAST_STEPS][:, WEATHER_IDXS]  # (N_FORECAST_STEPS, 3) — future weather
        targets = [feat_arr[i + (h // 15), speed_col] for h in HORIZONS]
        X_list.append(x)
        W_list.append(w)
        y_list.append(targets)

    X = np.stack(X_list, axis=0)                      # (N, SEQ_LEN, N_FEATURES)
    W = np.stack(W_list, axis=0).astype(np.float32)   # (N, N_FORECAST_STEPS, 3)
    y = np.array(y_list, dtype=np.float32)
    return X, W, y, scaler


# ── Model definition ──────────────────────────────────────────────────────────


def build_model(hidden_size: int, num_layers: int):
    """Build PyTorch LSTM model."""
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        logger.error("pip install torch is required for training")
        sys.exit(1)

    class CongestionLSTM(nn.Module):
        """Two-stream LSTM: traffic sequence + weather forecast."""
        def __init__(self, n_features: int, hidden: int, layers: int, n_outputs: int,
                     n_weather: int = len(WEATHER_COLS), n_forecast: int = N_FORECAST_STEPS):
            super().__init__()
            # Stream 1: traffic history
            self.lstm = nn.LSTM(
                n_features, hidden, layers,
                batch_first=True, dropout=0.2 if layers > 1 else 0.0,
            )
            # Stream 2: future weather forecast (flattened n_forecast × n_weather → 16)
            self.weather_fc = nn.Sequential(
                nn.Linear(n_weather * n_forecast, 16),
                nn.ReLU(),
            )
            # Fusion head
            self.fc = nn.Sequential(
                nn.Linear(hidden + 16, hidden // 2),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(hidden // 2, n_outputs),
            )

        def forward(self, x, w):
            lstm_out, _ = self.lstm(x)
            traffic = lstm_out[:, -1, :]           # (batch, hidden)
            weather = self.weather_fc(w.flatten(1))  # (batch, 16)
            return self.fc(torch.cat([traffic, weather], dim=1))

    return CongestionLSTM(N_FEATURES, hidden_size, num_layers, len(HORIZONS))


# ── Training loop ─────────────────────────────────────────────────────────────


def train(X, W, y, args, onnx_out: Path | None = None):
    """Train the two-stream LSTM and return the fitted model."""
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError:
        logger.error("pip install torch is required for training")
        sys.exit(1)

    import numpy as np

    # 80/20 train/val split
    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    W_train, W_val = W[:split], W[split:]
    y_train, y_val = y[:split], y[split:]

    train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(W_train), torch.from_numpy(y_train))
    val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(W_val), torch.from_numpy(y_val))

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("  Training on %s (%d train, %d val samples)", device, len(train_ds), len(val_ds))

    model = build_model(args.hidden_size, args.num_layers).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=3, factor=0.5)
    criterion = nn.HuberLoss()

    best_val = float("inf")
    best_state = None

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        for xb, wb, yb in train_loader:
            xb, wb, yb = xb.to(device), wb.to(device), yb.to(device)
            opt.zero_grad()
            pred = model(xb, wb)
            loss = criterion(pred, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            train_loss += loss.item() * len(xb)

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for xb, wb, yb in val_loader:
                xb, wb, yb = xb.to(device), wb.to(device), yb.to(device)
                val_loss += criterion(model(xb, wb), yb).item() * len(xb)

        train_loss /= len(train_ds)
        val_loss /= len(val_ds)
        scheduler.step(val_loss)

        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            # Save ONNX checkpoint immediately so crashes don't lose progress
            if onnx_out is not None:
                try:
                    _m = build_model(args.hidden_size, args.num_layers)
                    _m.load_state_dict(best_state)
                    export_onnx(_m, onnx_out)
                    logger.info("  Checkpoint saved (epoch %d, val=%.4f)", epoch, best_val)
                    del _m
                except Exception:
                    logger.exception("  Checkpoint save failed")

        if epoch % 5 == 0 or epoch == 1:
            logger.info("  Epoch %3d/%d  train=%.4f  val=%.4f", epoch, args.epochs, train_loss, val_loss)

    if best_state is not None:
        model.load_state_dict(best_state)
    logger.info("  Best val loss: %.4f", best_val)
    return model.cpu()


# ── ONNX export ───────────────────────────────────────────────────────────────


def export_onnx(model, output_path: Path) -> None:
    """Export PyTorch model to ONNX."""
    try:
        import torch
        import onnx
    except ImportError:
        logger.error("pip install torch onnx is required for export")
        sys.exit(1)

    dummy_seq = torch.zeros(1, SEQ_LEN, N_FEATURES)
    dummy_wx = torch.zeros(1, N_FORECAST_STEPS, len(WEATHER_COLS))
    model.eval()
    # Use legacy exporter (dynamo=False) for compatibility with torch 2.x on Windows
    torch.onnx.export(
        model,
        (dummy_seq, dummy_wx),
        str(output_path),
        input_names=["sequence", "weather_forecast"],
        output_names=["predictions"],
        dynamic_axes={
            "sequence": {0: "batch"},
            "weather_forecast": {0: "batch"},
            "predictions": {0: "batch"},
        },
        opset_version=18,
        dynamo=False,
    )
    # Validate
    import onnx as onnx_lib
    onnx_lib.checker.check_model(str(output_path))
    logger.info("ONNX model validated OK")


if __name__ == "__main__":
    main()
