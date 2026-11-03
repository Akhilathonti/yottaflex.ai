"""
Temporal Causality & Data Leakage Prevention Tests
Includes automated leakage check and deliberate negative test case.
"""
from datetime import datetime, timedelta
import pandas as pd
import pytest
from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR
from src.feature_engineering.features import PointInTimeFeatureEngineer
from src.feature_engineering.leakage_check import LeakageChecker


def test_standard_pipeline_has_zero_leakage():
    feat_path = PROCESSED_DATA_DIR / "features.csv"
    if feat_path.exists():
        feat_df = pd.read_csv(feat_path)
    else:
        engineer = PointInTimeFeatureEngineer()
        feat_df = engineer.build_feature_dataset(simulate_leakage=False)

    events_df = pd.read_csv(RAW_DATA_DIR / "tracking_events.csv")
    is_clean, violations = LeakageChecker.verify_no_future_event_leakage(feat_df, events_df)
    assert is_clean, f"Data leakage detected in standard pipeline: {violations}"


def test_deliberate_leakage_is_detected():
    """
    Deliberate test case: Inject future event into features and verify that
    the leakage verification framework identifies the causality breach.
    """
    events_df = pd.read_csv(RAW_DATA_DIR / "tracking_events.csv")

    # Construct mock features dataframe where last_known_event_time is in the future
    pred_time = datetime(2026, 7, 1, 10, 0, 0)
    future_event_time = pred_time + timedelta(hours=5)

    mock_leaked_features = pd.DataFrame([
        {
            "shipment_id": "SHP-2026-000001",
            "prediction_timestamp": pred_time.isoformat(),
            "last_known_event_time": future_event_time.isoformat(),  # 5 hours in the future!
            "total_distance_km": 500.0,
        }
    ])

    is_clean, violations = LeakageChecker.verify_no_future_event_leakage(mock_leaked_features, events_df)

    # Must fail because future event was included
    assert not is_clean, "Validation framework should have detected the simulated future event leakage!"
    assert len(violations) > 0
    assert violations[0]["violation_type"] == "EVENT_AFTER_PREDICTION_TIMESTAMP"
