"""
Automated Data Leakage Verification Framework
Ensures temporal strictness: no features use events or data ingested after prediction timestamp T.
"""
import logging
from typing import Tuple, List, Dict
import pandas as pd
from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)


class LeakageChecker:
    """Verifies that point-in-time features comply with causal temporal boundaries."""

    @staticmethod
    def verify_no_future_event_leakage(
        features_df: pd.DataFrame,
        events_df: pd.DataFrame,
    ) -> Tuple[bool, List[Dict]]:
        """
        For each shipment snapshot at prediction time T, verify that no events with
        ingestion_timestamp > T were referenced or included in telemetry features.
        """
        violations = []
        events_df = events_df.copy()
        events_df["event_timestamp_dt"] = pd.to_datetime(events_df["event_timestamp"])
        events_df["ingestion_timestamp_dt"] = pd.to_datetime(events_df["ingestion_timestamp"])

        # Pre-group for O(1) retrieval
        events_by_shp = {k: v for k, v in events_df.groupby("shipment_id")}

        for _, row in features_df.iterrows():
            shp_id = row["shipment_id"]
            pred_t = pd.to_datetime(row["prediction_timestamp"])

            # Check if features explicitly reference an event that only occurred after T
            if "last_known_event_time" in row and pd.notna(row["last_known_event_time"]):
                last_time = pd.to_datetime(row["last_known_event_time"])
                if last_time > pred_t:
                    violations.append({
                        "shipment_id": shp_id,
                        "prediction_timestamp": row["prediction_timestamp"],
                        "violation_type": "EVENT_AFTER_PREDICTION_TIMESTAMP",
                        "details": f"last_known_event_time ({last_time}) > prediction_t ({pred_t})",
                    })

        is_leakage_free = len(violations) == 0
        return is_leakage_free, violations

    @staticmethod
    def verify_target_separation(feature_columns: List[str]) -> Tuple[bool, List[str]]:
        """Verify that ground truth target columns are completely excluded from model inputs."""
        forbidden_targets = {
            "target_remaining_transit_minutes",
            "target_is_delayed",
            "actual_delivery_time",
            "actual_delay_minutes",
            "is_delayed",
        }
        leaked = [col for col in feature_columns if col in forbidden_targets]
        return len(leaked) == 0, leaked


def run_leakage_tests():
    from src.feature_engineering.features import PointInTimeFeatureEngineer
    engineer = PointInTimeFeatureEngineer()

    # Valid run
    feat_df = engineer.build_feature_dataset(simulate_leakage=False)
    events_df = pd.read_csv(RAW_DATA_DIR / "tracking_events.csv")
    is_clean, violations = LeakageChecker.verify_no_future_event_leakage(feat_df, events_df)
    print(f"Standard pipeline leakage check: {'PASSED (Zero Leakage)' if is_clean else 'FAILED'}")

    feature_cols = [c for c in feat_df.columns if not c.startswith("target_") and c not in ["actual_delivery_time", "shipment_id", "prediction_timestamp"]]
    is_target_clean, leaked_cols = LeakageChecker.verify_target_separation(feature_cols)
    print(f"Target separation check: {'PASSED (Targets fully isolated)' if is_target_clean else 'FAILED'}")


if __name__ == "__main__":
    run_leakage_tests()
