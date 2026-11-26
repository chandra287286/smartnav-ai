"""
ETA Prediction Service (Baseline & Historical-Factor Model).

IMPORTANT: Outputs from this module represent model-predicted travel times
("Predicted traffic") and are kept strictly separate from live traffic
provider observations ("Live traffic" or "Live traffic unavailable").
"""

from datetime import datetime, timezone
from typing import Dict, Optional

BASE_FREE_FLOW_SPEED_KMH = {
    "driving": 48.0,
    "cycling": 16.0,
    "walking": 4.8,
}

CONGESTION_FACTOR = {
    "low": 1.0,
    "moderate": 1.18,
    "heavy": 1.42,
    "severe": 1.75,
    "unknown": 1.0,
}


def time_of_day_congestion_multiplier(dt: datetime, profile: str = "driving") -> float:
    """Estimate typical time-of-day/day-of-week road congestion multiplier."""
    if profile != "driving":
        return 1.0

    hour = dt.hour + dt.minute / 60.0
    is_weekend = dt.weekday() >= 5

    if is_weekend:
        if 11.0 <= hour <= 19.0:
            return 1.12
        return 1.02

    # Weekday morning & evening rush windows
    if 7.5 <= hour <= 10.0:
        return 1.28
    if 16.5 <= hour <= 20.0:
        return 1.32
    if 10.0 < hour < 16.5:
        return 1.10
    return 1.0


def predict_eta_seconds(
    distance_meters: float,
    base_duration_seconds: float,
    profile: str = "driving",
    observed_speed_kmh: Optional[float] = None,
    historical_avg_speed_kmh: Optional[float] = None,
    congestion_level: str = "unknown",
    weather_factor: float = 1.0,
    reference_time: Optional[datetime] = None,
) -> float:
    """
    Compute baseline ML/heuristic ETA prediction in seconds.
    Combines provider free-flow/base duration, time-of-day factor,
    observed speed vs historical speed blend, and congestion factor.
    """
    if distance_meters <= 0:
        return 0.0

    dt = reference_time or datetime.now(timezone.utc)
    tod_mult = time_of_day_congestion_multiplier(dt, profile)
    cong_mult = CONGESTION_FACTOR.get(congestion_level, 1.0)
    safe_weather = max(1.0, min(1.5, weather_factor))

    # Base duration from routing graph
    base_sec = base_duration_seconds if base_duration_seconds > 0 else (
        (distance_meters / 1000.0) / BASE_FREE_FLOW_SPEED_KMH.get(profile, 40.0) * 3600.0
    )

    if observed_speed_kmh and observed_speed_kmh > 1.0 and profile == "driving":
        hist_speed = historical_avg_speed_kmh or BASE_FREE_FLOW_SPEED_KMH["driving"]
        blended_speed = 0.65 * observed_speed_kmh + 0.35 * hist_speed
        speed_based_sec = (distance_meters / 1000.0) / blended_speed * 3600.0
        predicted = 0.5 * speed_based_sec + 0.5 * (base_sec * max(tod_mult, cong_mult))
    else:
        predicted = base_sec * max(tod_mult, cong_mult)

    return round(predicted * safe_weather, 1)


def compare_prediction_vs_observed(predicted_seconds: float, observed_seconds: float) -> Dict[str, float]:
    """Compare predicted duration against actual observed trip duration for accuracy auditing."""
    if observed_seconds <= 0:
        return {"absolute_error_seconds": 0.0, "relative_error_pct": 0.0}
    abs_err = abs(predicted_seconds - observed_seconds)
    rel_err = (abs_err / observed_seconds) * 100.0
    return {
        "absolute_error_seconds": round(abs_err, 2),
        "relative_error_pct": round(rel_err, 2),
    }
