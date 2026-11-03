"""
Inference Service for Real-time ETA and Delay Probability Prediction
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import joblib
import numpy as np
import pandas as pd

from src.config import MODELS_DIR
from src.models.train import FEATURE_COLUMNS
from src.utils.helpers import generate_eta_id

logger = logging.getLogger(__name__)


class ETAPredictionService:
    """Provides inference endpoints for single-shipment and batch ETA prediction."""

    def __init__(self):
        bundle_path = MODELS_DIR / "eta_champion_bundle.joblib"
        if not bundle_path.exists():
            raise FileNotFoundError(f"Model bundle not found at {bundle_path}. Run training first.")

        logger.info("Loading champion model bundle from %s...", bundle_path)
        bundle = joblib.load(bundle_path)
        self.regressor = bundle["regressor"]
        self.classifier = bundle["classifier"]
        self.feature_columns = bundle.get("feature_columns", FEATURE_COLUMNS)
        self.scaler = bundle.get("scaler")
        self.metadata = bundle.get("metadata", {})

    def predict_single(self, input_features: Dict[str, Any]) -> Dict[str, Any]:
        """Generate predicted remaining time, predicted ETA, and delay probability for a single shipment."""
        pred_time_val = input_features.get("prediction_timestamp")
        if not pred_time_val or pd.isna(pd.to_datetime(pred_time_val, errors="coerce")):
            pred_t = datetime.utcnow()
        else:
            pred_t = pd.to_datetime(pred_time_val).to_pydatetime()

        shipment_id = str(input_features.get("shipment_id", "SHP-UNKNOWN"))

        # Construct dataframe with required feature columns
        row = {col: float(input_features.get(col, 0.0)) for col in self.feature_columns}
        df_x = pd.DataFrame([row])

        # Inference
        remaining_minutes = float(max(15.0, self.regressor.predict(df_x)[0]))
        delay_prob = float(self.classifier.predict_proba(df_x)[0, 1])

        predicted_eta = pred_t + timedelta(minutes=remaining_minutes)

        # Confidence interval (+/- 30 mins or based on model standard error)
        conf_lower = predicted_eta - timedelta(minutes=30)
        conf_upper = predicted_eta + timedelta(minutes=30)

        # Attribute primary delay reason if high probability
        primary_reason = "NONE"
        if delay_prob > 0.50:
            if input_features.get("weather_active_flag", 0) > 0:
                primary_reason = "WEATHER_DISRUPTION"
            elif input_features.get("facility_queue_length", 0) > 40:
                primary_reason = "FACILITY_CONGESTION"
            elif input_features.get("carrier_on_time_rating", 1.0) < 0.88:
                primary_reason = "CARRIER_PERFORMANCE"
            elif input_features.get("delayed_scans_count", 0) > 0:
                primary_reason = "DELAYED_SCANS"
            else:
                primary_reason = "OPERATIONAL_HANDLING_DELAY"

        return {
            "estimate_id": generate_eta_id(shipment_id, pred_t),
            "shipment_id": shipment_id,
            "prediction_timestamp": pred_t.isoformat(),
            "predicted_eta": predicted_eta.isoformat(),
            "predicted_remaining_transit_minutes": round(remaining_minutes, 2),
            "delay_probability": round(delay_prob, 4),
            "confidence_lower_bound": conf_lower.isoformat(),
            "confidence_upper_bound": conf_upper.isoformat(),
            "primary_delay_reason": primary_reason,
            "model_version": "v1.0.0-champion",
            "model_name": "HistGradientBoostingRegressor",
        }

    def predict_batch(self, batch_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Perform vectorized batch inference across multiple shipments."""
        return [self.predict_single(item) for item in batch_items]
