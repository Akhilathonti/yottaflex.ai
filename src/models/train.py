"""
Model Training and Comparison Pipeline
Implements chronological splitting, baseline vs ML comparison, and persistence of champion models.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.ensemble import (
    RandomForestRegressor,
    RandomForestClassifier,
    HistGradientBoostingRegressor,
    HistGradientBoostingClassifier,
)
from sklearn.preprocessing import StandardScaler

from src.config import PROCESSED_DATA_DIR, MODELS_DIR, REPORTS_DIR, RANDOM_SEED
from src.feature_engineering.features import PointInTimeFeatureEngineer
from src.models.baseline import HistoricalAverageBaselineModel
from src.models.evaluate import (
    evaluate_eta_regression,
    evaluate_delay_classification,
    evaluate_subgroups,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "total_distance_km",
    "remaining_route_distance_km",
    "weight_kg",
    "volume_cbm",
    "carrier_on_time_rating",
    "target_delivery_hours",
    "promised_remaining_hours",
    "elapsed_transit_hours",
    "facility_queue_length",
    "facility_queue_wait_minutes",
    "weather_active_flag",
    "weather_severity_score",
    "delayed_scans_count",
    "time_since_last_event_hours",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
]


def train_and_evaluate_models():
    """Execute complete chronological train, validation, evaluation, and model serialization."""
    features_path = PROCESSED_DATA_DIR / "features.csv"
    if not features_path.exists():
        logger.info("Features file not found. Running feature engineering pipeline...")
        engineer = PointInTimeFeatureEngineer()
        df = engineer.build_feature_dataset()
    else:
        df = pd.read_csv(features_path)

    # Sort strictly chronologically
    df = df.sort_values("prediction_timestamp").reset_index(drop=True)
    n_samples = len(df)
    train_end = int(0.70 * n_samples)
    val_end = int(0.85 * n_samples)

    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]
    test_df = df.iloc[val_end:]

    logger.info(
        "Chronological dataset splits: Train=%d (until %s), Val=%d, Test=%d (from %s to %s)",
        len(train_df),
        train_df["prediction_timestamp"].iloc[-1],
        len(val_df),
        len(test_df),
        test_df["prediction_timestamp"].iloc[0],
        test_df["prediction_timestamp"].iloc[-1],
    )

    X_train = train_df[FEATURE_COLUMNS]
    y_reg_train = train_df["target_remaining_transit_minutes"]
    y_cls_train = train_df["target_is_delayed"]

    X_test = test_df[FEATURE_COLUMNS]
    y_reg_test = test_df["target_remaining_transit_minutes"]
    y_cls_test = test_df["target_is_delayed"]

    # Scaler for linear models
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 1. BASELINE MODEL
    logger.info("Training Historical Average Baseline Model...")
    baseline = HistoricalAverageBaselineModel()
    baseline.fit(X_train, y_reg_train, y_cls_train)
    pred_base_reg = baseline.predict_remaining_minutes(X_test)
    pred_base_prob = baseline.predict_delay_probability(X_test)
    base_reg_metrics = evaluate_eta_regression(y_reg_test.to_numpy(), pred_base_reg)
    base_cls_metrics = evaluate_delay_classification(y_cls_test.to_numpy(), pred_base_prob)

    # 2. LINEAR / RIDGE MODEL
    logger.info("Training Ridge Regression & Logistic Regression...")
    ridge = Ridge(alpha=1.0, random_state=RANDOM_SEED)
    ridge.fit(X_train_scaled, y_reg_train)
    pred_ridge_reg = np.maximum(10.0, ridge.predict(X_test_scaled))
    ridge_reg_metrics = evaluate_eta_regression(y_reg_test.to_numpy(), pred_ridge_reg)

    log_reg = LogisticRegression(random_state=RANDOM_SEED)
    log_reg.fit(X_train_scaled, y_cls_train)
    pred_log_prob = log_reg.predict_proba(X_test_scaled)[:, 1]
    log_cls_metrics = evaluate_delay_classification(y_cls_test.to_numpy(), pred_log_prob)

    # 3. RANDOM FOREST
    logger.info("Training Random Forest Regressor & Classifier...")
    rf_reg = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=RANDOM_SEED, n_jobs=-1)
    rf_reg.fit(X_train, y_reg_train)
    pred_rf_reg = rf_reg.predict(X_test)
    rf_reg_metrics = evaluate_eta_regression(y_reg_test.to_numpy(), pred_rf_reg)

    rf_cls = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=RANDOM_SEED, n_jobs=-1)
    rf_cls.fit(X_train, y_cls_train)
    pred_rf_prob = rf_cls.predict_proba(X_test)[:, 1]
    rf_cls_metrics = evaluate_delay_classification(y_cls_test.to_numpy(), pred_rf_prob)

    # 4. GRADIENT BOOSTING (HistGradientBoosting / LightGBM algorithm)
    logger.info("Training Gradient Boosting (HistGradientBoosting)...")
    gb_reg = HistGradientBoostingRegressor(max_iter=120, max_depth=7, random_state=RANDOM_SEED)
    gb_reg.fit(X_train, y_reg_train)
    pred_gb_reg = gb_reg.predict(X_test)
    gb_reg_metrics = evaluate_eta_regression(y_reg_test.to_numpy(), pred_gb_reg)

    gb_cls = HistGradientBoostingClassifier(max_iter=100, max_depth=6, random_state=RANDOM_SEED)
    gb_cls.fit(X_train, y_cls_train)
    pred_gb_prob = gb_cls.predict_proba(X_test)[:, 1]
    gb_cls_metrics = evaluate_delay_classification(y_cls_test.to_numpy(), pred_gb_prob)

    # Feature Importance analysis (using Random Forest Gini importances)
    importances = rf_reg.feature_importances_
    feat_imp = sorted(
        [{"feature": col, "importance": round(float(imp), 4)} for col, imp in zip(FEATURE_COLUMNS, importances)],
        key=lambda x: x["importance"],
        reverse=True,
    )

    # Subgroup Evaluation
    test_with_preds = test_df.copy()
    test_with_preds["pred_remaining_minutes"] = pred_gb_reg
    weather_subgroup = evaluate_subgroups(
        test_with_preds, y_reg_test.to_numpy(), pred_gb_reg, "weather_active_flag"
    )

    # Model Summary Comparison
    evaluation_report = {
        "timestamp": datetime.utcnow().isoformat(),
        "random_seed": RANDOM_SEED,
        "sample_counts": {"train": len(train_df), "val": len(val_df), "test": len(test_df)},
        "regression_comparison": {
            "baseline_historical_avg": base_reg_metrics,
            "ridge_regression": ridge_reg_metrics,
            "random_forest": rf_reg_metrics,
            "gradient_boosting": gb_reg_metrics,
        },
        "classification_comparison": {
            "baseline_frequency": base_cls_metrics,
            "logistic_regression": log_cls_metrics,
            "random_forest": rf_cls_metrics,
            "gradient_boosting": gb_cls_metrics,
        },
        "feature_importances": feat_imp,
        "subgroups": {
            "weather_active_subgroup": weather_subgroup,
        },
        "champion_model": {
            "regressor": "HistGradientBoostingRegressor",
            "classifier": "HistGradientBoostingClassifier",
            "mae_minutes": gb_reg_metrics["mae_minutes"],
            "accuracy_within_30m_pct": gb_reg_metrics["accuracy_within_30m_pct"],
            "f1_score": gb_cls_metrics["f1_score"],
            "roc_auc": gb_cls_metrics["roc_auc"],
        },
    }

    # Save models
    champion_bundle = {
        "regressor": gb_reg,
        "classifier": gb_cls,
        "feature_columns": FEATURE_COLUMNS,
        "scaler": scaler,
        "metadata": evaluation_report["champion_model"],
    }
    bundle_path = MODELS_DIR / "eta_champion_bundle.joblib"
    joblib.dump(champion_bundle, bundle_path)
    logger.info("Saved champion model bundle -> %s", bundle_path)

    # Save reports
    json_path = REPORTS_DIR / "model_evaluation.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(evaluation_report, f, indent=2)

    md_path = REPORTS_DIR / "model_evaluation.md"
    md_content = f"""# Machine Learning Model Evaluation Report

**Evaluation Timestamp**: {evaluation_report['timestamp']}  
**Evaluation Holdout Period**: Chronological test split ({len(test_df)} observations)

---

## 1. ETA Regression Model Comparison

| Model | MAE (mins) | RMSE (mins) | MedAE (mins) | Acc ≤ 15m (%) | Acc ≤ 30m (%) | Acc ≤ 60m (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Historical Baseline** | {base_reg_metrics['mae_minutes']} | {base_reg_metrics['rmse_minutes']} | {base_reg_metrics['median_ae_minutes']} | {base_reg_metrics['accuracy_within_15m_pct']}% | {base_reg_metrics['accuracy_within_30m_pct']}% | {base_reg_metrics['accuracy_within_60m_pct']}% |
| **Ridge Regression** | {ridge_reg_metrics['mae_minutes']} | {ridge_reg_metrics['rmse_minutes']} | {ridge_reg_metrics['median_ae_minutes']} | {ridge_reg_metrics['accuracy_within_15m_pct']}% | {ridge_reg_metrics['accuracy_within_30m_pct']}% | {ridge_reg_metrics['accuracy_within_60m_pct']}% |
| **Random Forest** | {rf_reg_metrics['mae_minutes']} | {rf_reg_metrics['rmse_minutes']} | {rf_reg_metrics['median_ae_minutes']} | {rf_reg_metrics['accuracy_within_15m_pct']}% | {rf_reg_metrics['accuracy_within_30m_pct']}% | {rf_reg_metrics['accuracy_within_60m_pct']}% |
| **Gradient Boosting** | **{gb_reg_metrics['mae_minutes']}** | **{gb_reg_metrics['rmse_minutes']}** | **{gb_reg_metrics['median_ae_minutes']}** | **{gb_reg_metrics['accuracy_within_15m_pct']}%** | **{gb_reg_metrics['accuracy_within_30m_pct']}%** | **{gb_reg_metrics['accuracy_within_60m_pct']}%** |

---

## 2. Delay Probability Classification Comparison

| Model | Precision | Recall | F1-Score | ROC-AUC | PR-AUC | Brier Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline Frequency** | {base_cls_metrics['precision']} | {base_cls_metrics['recall']} | {base_cls_metrics['f1_score']} | {base_cls_metrics['roc_auc']} | {base_cls_metrics['pr_auc']} | {base_cls_metrics['brier_score']} |
| **Logistic Regression** | {log_cls_metrics['precision']} | {log_cls_metrics['recall']} | {log_cls_metrics['f1_score']} | {log_cls_metrics['roc_auc']} | {log_cls_metrics['pr_auc']} | {log_cls_metrics['brier_score']} |
| **Random Forest** | {rf_cls_metrics['precision']} | {rf_cls_metrics['recall']} | {rf_cls_metrics['f1_score']} | {rf_cls_metrics['roc_auc']} | {rf_cls_metrics['pr_auc']} | {rf_cls_metrics['brier_score']} |
| **Gradient Boosting** | **{gb_cls_metrics['precision']}** | **{gb_cls_metrics['recall']}** | **{gb_cls_metrics['f1_score']}** | **{gb_cls_metrics['roc_auc']}** | **{gb_cls_metrics['pr_auc']}** | **{gb_cls_metrics['brier_score']}** |

---

## 3. Top Feature Importances

| Feature Name | Importance Weight |
| :--- | :--- |
"""
    for imp in feat_imp[:8]:
        md_content += f"| `{imp['feature']}` | {imp['importance']} |\n"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info("Saved evaluation report -> %s and %s", json_path.name, md_path.name)
    return evaluation_report


if __name__ == "__main__":
    train_and_evaluate_models()
