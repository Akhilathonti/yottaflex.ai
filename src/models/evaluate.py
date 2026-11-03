"""
Model Evaluation and Metrics Module
Calculates regression, classification, subgroup, and calibration metrics without synthetic fabrication.
"""
from typing import Dict, Any, List
import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    median_absolute_error,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    brier_score_loss,
)


def evaluate_eta_regression(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculate all standard regression accuracy metrics."""
    errors = np.abs(y_true - y_pred)
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    med_ae = float(median_absolute_error(y_true, y_pred))

    pct_within_15m = float(np.mean(errors <= 15.0) * 100.0)
    pct_within_30m = float(np.mean(errors <= 30.0) * 100.0)
    pct_within_60m = float(np.mean(errors <= 60.0) * 100.0)

    return {
        "mae_minutes": round(mae, 2),
        "rmse_minutes": round(rmse, 2),
        "median_ae_minutes": round(med_ae, 2),
        "accuracy_within_15m_pct": round(pct_within_15m, 2),
        "accuracy_within_30m_pct": round(pct_within_30m, 2),
        "accuracy_within_60m_pct": round(pct_within_60m, 2),
    }


def evaluate_delay_classification(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.5) -> Dict[str, Any]:
    """Calculate precision, recall, F1, ROC-AUC, PR-AUC, and Brier score."""
    y_pred = (y_prob >= threshold).astype(int)

    precision = float(precision_score(y_true, y_pred, zero_division=0))
    recall = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    try:
        roc_auc = float(roc_auc_score(y_true, y_prob))
    except Exception:
        roc_auc = 0.5

    try:
        pr_auc = float(average_precision_score(y_true, y_prob))
    except Exception:
        pr_auc = float(np.mean(y_true))

    brier = float(brier_score_loss(y_true, y_prob))
    cm = confusion_matrix(y_true, y_pred).tolist()

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(brier, 4),
        "confusion_matrix": cm,
    }


def evaluate_subgroups(
    df: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    subgroup_col: str,
) -> Dict[str, Dict[str, float]]:
    """Evaluate MAE and error metrics across distinct operational cohorts."""
    results = {}
    unique_groups = df[subgroup_col].dropna().unique()
    for grp in unique_groups:
        mask = (df[subgroup_col] == grp).to_numpy()
        if mask.sum() >= 5:
            mae = float(mean_absolute_error(y_true[mask], y_pred[mask]))
            rmse = float(np.sqrt(mean_squared_error(y_true[mask], y_pred[mask])))
            results[str(grp)] = {
                "count": int(mask.sum()),
                "mae_minutes": round(mae, 2),
                "rmse_minutes": round(rmse, 2),
            }
    return results
