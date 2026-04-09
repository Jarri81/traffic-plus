"""Risk scoring engine -- 7-factor model for road segment risk assessment."""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

_SAFE_ID = re.compile(r'^[a-zA-Z0-9_\-]+$')

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Map segment ID prefix → (influx measurement, speed field, tomtom point_id prefix)
_SEGMENT_CITY: dict[str, tuple[str, str, str]] = {
    "vlc-": ("valencia_traffic",  "speed_kmh",     "valencia_"),
    "bcn-": ("barcelona_traffic", "speed_kmh",     "barcelona_"),
}
_MADRID_DEFAULT = ("madrid_traffic", "speed_kmh", "madrid_")


def _city_info(segment_id: str) -> tuple[str, str, str]:
    """Return (measurement, speed_field, tomtom_prefix) for a segment ID."""
    for prefix, info in _SEGMENT_CITY.items():
        if segment_id.startswith(prefix):
            return info
    return _MADRID_DEFAULT

DEFAULT_WEIGHTS: dict[str, float] = {
    "speed_deviation": 0.22,
    "incident_proximity": 0.18,
    "flow_density": 0.18,
    "historical_baseline": 0.13,
    "infrastructure_health": 0.09,
    "time_day_pattern": 0.10,
    "weather": 0.10,
}


@dataclass
class RiskFactors:
    """Individual risk factor scores (0-100 each)."""
    speed_deviation: float = 0.0
    incident_proximity: float = 0.0
    flow_density: float = 0.0
    historical_baseline: float = 0.0
    infrastructure_health: float = 0.0
    time_day_pattern: float = 0.0
    weather: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "speed_deviation": self.speed_deviation,
            "incident_proximity": self.incident_proximity,
            "flow_density": self.flow_density,
            "historical_baseline": self.historical_baseline,
            "infrastructure_health": self.infrastructure_health,
            "time_day_pattern": self.time_day_pattern,
            "weather": self.weather,
        }


class RiskScoringEngine:
    """Computes composite risk scores using 7 weighted factors.

    Accepts an async database session for querying PostgreSQL and uses
    InfluxDB for time-series factor calculations.
    """
    def __init__(self, db: AsyncSession | None = None, weights: dict[str, float] | None = None) -> None:
        self.db = db
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    async def compute(self, segment_id: str) -> float:
        """Compute composite risk score (0-100) for a segment."""
        factors = await self._gather_factors(segment_id)
        score = self._weighted_sum(factors)
        return round(min(max(score, 0.0), 100.0), 2)

    async def compute_with_explanation(self, segment_id: str) -> dict[str, Any]:
        """Compute risk score with per-factor breakdown."""
        factors = await self._gather_factors(segment_id)
        score = round(min(max(self._weighted_sum(factors), 0.0), 100.0), 2)
        return {
            "segment_id": segment_id,
            "score": score,
            "level": self.score_to_level(score),
            "factors": factors.as_dict(),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _weighted_sum(self, factors: RiskFactors) -> float:
        fd = factors.as_dict()
        return sum(fd[n] * self.weights.get(n, 0.0) for n in fd)

    @staticmethod
    def score_to_level(score: float) -> str:
        """Convert a numeric risk score to a severity level string."""
        if score >= 75:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 25:
            return "medium"
        return "low"

    # Keep backward compatibility
    _score_to_level = score_to_level

    async def _gather_factors(self, segment_id: str) -> RiskFactors:
        """Gather all 7 risk factors for a segment."""
        factors = RiskFactors()
        for attr, calc in [
            ("speed_deviation", self._calc_speed_deviation),
            ("incident_proximity", self._calc_incident_proximity),
            ("flow_density", self._calc_flow_density),
            ("time_day_pattern", self._calc_time_factor),
            ("historical_baseline", self._calc_historical_baseline),
            ("infrastructure_health", self._calc_infrastructure_health),
            ("weather", self._calc_weather),
        ]:
            try:
                setattr(factors, attr, await calc(segment_id))
            except Exception:
                logger.exception("Error calculating %s for %s", attr, segment_id)
        return factors

    async def _calc_speed_deviation(self, segment_id: str) -> float:
        """Compare current city speed to free-flow baseline.

        Uses city-specific TomTom flow points so Madrid, Valencia, and Barcelona
        segments each get their own corridor speed rather than a global average.
        Returns 0-100: 0 = at free flow, 100 = standstill.
        """
        if not _SAFE_ID.match(segment_id):
            raise ValueError(f"Invalid segment_id for Flux query: {segment_id!r}")
        try:
            from traffic_ai.db.influx import query_points
            _, _, tomtom_prefix = _city_info(segment_id)
            query = f"""
            from(bucket: "traffic_metrics")
              |> range(start: -15m)
              |> filter(fn: (r) => r._measurement == "tomtom_flow")
              |> filter(fn: (r) => r._field == "current_speed" or r._field == "free_flow_speed")
              |> filter(fn: (r) => r.point_id =~ /^{tomtom_prefix}/)
              |> mean()
            """
            points = await query_points(query)
            if not points:
                return 0.0

            values: dict[str, float] = {}
            for p in points:
                field = p.get("_field", "")
                val = p.get("_value")
                if field and val is not None:
                    values[field] = float(val)

            current = values.get("current_speed", 0.0)
            free_flow = values.get("free_flow_speed", 0.0)
            if free_flow > 0:
                return min(max((1.0 - current / free_flow) * 100, 0.0), 100.0)
            return 0.0
        except Exception:
            logger.exception("Error in _calc_speed_deviation for %s", segment_id)
            return 0.0

    async def _calc_incident_proximity(self, segment_id: str) -> float:
        """Count active incidents within 15 km of the segment centroid.

        Uses PostGIS ST_DWithin (geography, metres) so the radius is consistent
        regardless of latitude.  Returns 0-100 based on count × avg severity.
        """
        if self.db is None:
            return 0.0
        try:
            from sqlalchemy import text
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            row = (await self.db.execute(
                text("""
                    SELECT COUNT(i.id), COALESCE(AVG(i.severity), 1)
                    FROM incidents i
                    JOIN road_segments s ON s.id = :seg_id
                    WHERE i.status = 'active'
                      AND i.location_geom IS NOT NULL
                      AND i.started_at >= :cutoff
                      AND ST_DWithin(
                          i.location_geom::geography,
                          ST_Centroid(s.geom)::geography,
                          15000
                      )
                """),
                {"seg_id": segment_id, "cutoff": cutoff},
            )).one_or_none()
            if row is None:
                return 0.0
            count, avg_severity = row[0], row[1]
            base = min(count / 5.0, 1.0) * 100
            severity_factor = min(float(avg_severity) / 5.0, 1.0) if avg_severity else 0.5
            return min(base * severity_factor, 100.0)
        except Exception:
            logger.exception("Error in _calc_incident_proximity for %s", segment_id)
            return 0.0

    async def _calc_flow_density(self, segment_id: str) -> float:
        """Mean density_score for the segment's city over the last 15 minutes.

        Routes to the city-specific InfluxDB measurement so Madrid, Valencia, and
        Barcelona segments reflect their own sensor network rather than a global mean.
        Returns 0-100 where higher means more congested.
        """
        if not _SAFE_ID.match(segment_id):
            raise ValueError(f"Invalid segment_id for Flux query: {segment_id!r}")
        try:
            from traffic_ai.db.influx import query_points
            measurement, _, _ = _city_info(segment_id)
            if not _SAFE_ID.match(measurement):
                raise ValueError(f"Invalid measurement for Flux query: {measurement!r}")
            query = f"""
            from(bucket: "traffic_metrics")
              |> range(start: -15m)
              |> filter(fn: (r) => r._measurement == "{measurement}")
              |> filter(fn: (r) => r._field == "density_score")
              |> mean()
            """
            points = await query_points(query)
            if not points:
                return 0.0
            values = [float(p.get("_value", 0)) for p in points if p.get("_value") is not None]
            if not values:
                return 0.0
            return min(max(sum(values) / len(values), 0.0), 100.0)
        except Exception:
            logger.exception("Error in _calc_flow_density for %s", segment_id)
            return 0.0

    async def _calc_weather(self, segment_id: str) -> float:
        """Get latest weather data and compute severity score.

        Returns a score 0-100 based on precipitation, wind, and visibility.
        """
        try:
            from traffic_ai.db.influx import query_points
            query = """
            from(bucket: "traffic_metrics")
              |> range(start: -1h)
              |> filter(fn: (r) => r._measurement == "weather")
              |> last()
            """
            points = await query_points(query)
            if not points:
                return 0.0

            # Gather latest weather values
            values: dict[str, float] = {}
            for p in points:
                field_name = p.get("_field", "")
                value = p.get("_value")
                if value is not None:
                    values[field_name] = float(value)

            score = 0.0
            # Precipitation: 0mm = 0, 10mm+ = 40 pts
            precip = values.get("precipitation_mm", 0)
            score += min(precip / 10.0, 1.0) * 40

            # Wind speed: 0 km/h = 0, 60+ km/h = 30 pts
            wind = values.get("wind_speed_kmh", 0)
            score += min(wind / 60.0, 1.0) * 30

            # Visibility / fog — 30 pts total.
            # NOAA / AEMET ingestors write visibility_m (preferred).
            # Open-Meteo archive does not provide visibility — it writes
            # cloud_cover_low_pct and fog_factor instead.
            if "visibility_m" in values:
                vis = values["visibility_m"]
                score += (1.0 - min(vis / 10000.0, 1.0)) * 30
            elif "fog_factor" in values:
                score += float(values["fog_factor"]) * 30
            elif "cloud_cover_low_pct" in values:
                score += min(float(values["cloud_cover_low_pct"]) / 100.0, 1.0) * 20

            return min(score, 100.0)
        except Exception:
            logger.exception("Error in _calc_weather for %s", segment_id)
            return 0.0

    async def _calc_infrastructure_health(self, segment_id: str) -> float:
        """Query asset condition scores for the segment.

        Returns a score 0-100 where higher means worse infrastructure health (higher risk).
        """
        if self.db is None:
            return 0.0
        try:
            from traffic_ai.models.orm import RoadAsset
            result = await self.db.execute(
                select(func.avg(RoadAsset.condition_score)).where(
                    RoadAsset.segment_id == segment_id,
                    RoadAsset.condition_score.isnot(None),
                )
            )
            avg_score = result.scalar()
            if avg_score is None:
                return 0.0
            # condition_score: 1=excellent, 5=terrible. Map to 0-100.
            return min(max((float(avg_score) - 1) / 4.0 * 100, 0.0), 100.0)
        except Exception:
            logger.exception("Error in _calc_infrastructure_health for %s", segment_id)
            return 0.0

    async def _calc_time_factor(self, segment_id: str) -> float:
        """Score based on time-of-day traffic patterns."""
        hour = datetime.now(timezone.utc).hour
        if 7 <= hour <= 9 or 16 <= hour <= 19:
            return 60.0  # Rush hours
        elif 22 <= hour or hour <= 5:
            return 40.0  # Late night (lower traffic but higher risk per vehicle)
        return 20.0

    async def _calc_historical_baseline(self, segment_id: str) -> float:
        """Compare current city density to its 6-hour rolling average.

        Uses the city-specific measurement so each city's baseline reflects its
        own sensor network. A large positive deviation means unusually high
        congestion relative to the recent norm.
        Returns 0-100.
        """
        if not _SAFE_ID.match(segment_id):
            raise ValueError(f"Invalid segment_id for Flux query: {segment_id!r}")
        try:
            import asyncio
            from traffic_ai.db.influx import query_points
            measurement, _, _ = _city_info(segment_id)
            if not _SAFE_ID.match(measurement):
                raise ValueError(f"Invalid measurement for Flux query: {measurement!r}")
            q_now = f"""
            from(bucket: "traffic_metrics")
              |> range(start: -15m)
              |> filter(fn: (r) => r._measurement == "{measurement}")
              |> filter(fn: (r) => r._field == "density_score")
              |> mean()
            """
            # Preceding window excludes the last 15 min so hist != current
            q_hist = f"""
            from(bucket: "traffic_metrics")
              |> range(start: -6h, stop: -15m)
              |> filter(fn: (r) => r._measurement == "{measurement}")
              |> filter(fn: (r) => r._field == "density_score")
              |> mean()
            """
            now_pts, hist_pts = await asyncio.gather(
                query_points(q_now), query_points(q_hist)
            )
            if not now_pts or not hist_pts:
                return 0.0
            current = float(now_pts[0].get("_value") or 0)
            hist = float(hist_pts[0].get("_value") or 0)
            if hist <= 0:
                return 0.0
            # How much worse than historical average (positive = more congested now)
            deviation = max(0.0, (current - hist) / max(hist, 1.0))
            return min(deviation * 100, 100.0)
        except Exception:
            logger.exception("Error in _calc_historical_baseline for %s", segment_id)
            return 0.0

    async def explain_with_shap(self, segment_id: str) -> dict[str, Any]:
        """SHAP-style explanation using factor contributions.

        Computes each factor's weighted contribution to the total score,
        providing a meaningful explanation of what drives the risk.
        """
        factors = await self._gather_factors(segment_id)
        fd = factors.as_dict()

        contributions: dict[str, float] = {}
        total = 0.0
        for name, value in fd.items():
            weight = self.weights.get(name, 0.0)
            contribution = value * weight
            contributions[name] = round(contribution, 4)
            total += contribution

        # Normalize to show relative importance
        relative: dict[str, float] = {}
        if total > 0:
            for name, contrib in contributions.items():
                relative[name] = round(contrib / total, 4)
        else:
            relative = {name: 0.0 for name in contributions}

        return {
            "segment_id": segment_id,
            "total_score": round(min(max(total, 0.0), 100.0), 2),
            "factor_contributions": contributions,
            "relative_importance": relative,
            "note": "Factor-based SHAP-style explanation. Full SHAP integration requires trained model artifact.",
        }
