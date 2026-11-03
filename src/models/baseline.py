"""
Baseline ETA Estimation Model based on Historical Averages
Provides the non-ML benchmark to demonstrate measurable machine learning improvement.
"""
from typing import Dict, Any
import numpy as np
import pandas as pd


class HistoricalAverageBaselineModel:
    """Estimates remaining transit minutes using historical mean velocity (km/h)."""

    def __init__(self):
        self.mean_velocity_kmh: float = 65.0
        self.mean_transit_minutes: float = 1200.0
        self.historical_delay_rate: float = 0.20

    def fit(self, X: pd.DataFrame, y_reg: pd.Series, y_cls: pd.Series = None) -> "HistoricalAverageBaselineModel":
        # Calculate average historical transit speed (distance / remaining transit time)
        dist = X["remaining_route_distance_km"]
        time_hours = y_reg / 60.0
        valid_mask = (time_hours > 0.5) & (dist > 10.0)
        if valid_mask.sum() > 0:
            velocities = dist[valid_mask] / time_hours[valid_mask]
            self.mean_velocity_kmh = float(np.median(velocities))
            self.mean_transit_minutes = float(np.mean(y_reg))
        if y_cls is not None:
            self.historical_delay_rate = float(np.mean(y_cls))
        return self

    def predict_remaining_minutes(self, X: pd.DataFrame) -> np.ndarray:
        dist = X["remaining_route_distance_km"]
        pred_hours = dist / max(10.0, self.mean_velocity_kmh)
        return (pred_hours * 60.0).to_numpy()

    def predict_delay_probability(self, X: pd.DataFrame) -> np.ndarray:
        # Return historical constant base rate
        return np.full(len(X), self.historical_delay_rate)
