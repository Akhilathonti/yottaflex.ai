"""
Feature Engineering and Target Isolation Tests
"""
import pandas as pd
import pytest
from src.config import PROCESSED_DATA_DIR
from src.feature_engineering.leakage_check import LeakageChecker
from src.models.train import FEATURE_COLUMNS


def test_feature_file_exists_and_has_valid_columns():
    feat_path = PROCESSED_DATA_DIR / "features.csv"
    assert feat_path.exists(), "Features CSV must be generated"

    df = pd.read_csv(feat_path)
    assert len(df) > 0

    # Ensure all model training columns exist
    for col in FEATURE_COLUMNS:
        assert col in df.columns, f"Missing feature column: {col}"


def test_target_columns_are_strictly_isolated():
    feat_path = PROCESSED_DATA_DIR / "features.csv"
    df = pd.read_csv(feat_path)

    # Targets must exist in the dataset for supervised training
    assert "target_remaining_transit_minutes" in df.columns
    assert "target_is_delayed" in df.columns

    # Check that FEATURE_COLUMNS contains NO ground-truth target columns
    is_isolated, leaked = LeakageChecker.verify_target_separation(FEATURE_COLUMNS)
    assert is_isolated, f"Target leakage detected in input feature columns: {leaked}"
