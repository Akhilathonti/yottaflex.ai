"""
Data Quality and Validation Suite Tests
"""
import pandas as pd
import pytest
from src.config import RAW_DATA_DIR
from src.data_validation.validator import DataValidator


def test_validator_detects_deliberate_anomalies():
    validator = DataValidator(data_dir=RAW_DATA_DIR)
    report = validator.run_all_validations()

    # The suite should have executed all checks
    assert report.total_checks >= 15
    # The deliberate anomalies injected into raw data must be identified
    assert report.anomaly_detected_count > 0

    # Ensure temporal anomaly was caught
    issue_names = [i.check_name for i in report.issues]
    assert "INGESTION_AFTER_EVENT_TIME" in issue_names or "FOREIGN_KEY_INTEGRITY" in issue_names


def test_shipment_delay_formula_consistency():
    shipments = pd.read_csv(RAW_DATA_DIR / "shipments.csv")
    deliv = shipments.dropna(subset=["actual_delivery_time", "promised_delivery_time", "actual_delay_minutes"])

    # For valid baseline shipments, actual_delay_minutes = (actual_delivery - promised_delivery)
    act = pd.to_datetime(deliv["actual_delivery_time"])
    prom = pd.to_datetime(deliv["promised_delivery_time"])
    calc_mins = ((act - prom).dt.total_seconds() / 60.0).astype(int)

    # Except for any deliberate anomaly row, majority must match perfectly within 1 minute
    matches = (calc_mins - deliv["actual_delay_minutes"].astype(int)).abs() <= 1
    assert matches.mean() > 0.95
