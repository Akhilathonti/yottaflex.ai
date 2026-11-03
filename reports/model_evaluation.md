# Machine Learning Model Evaluation Report

**Evaluation Timestamp**: 2026-11-02T10:14:43.691463  
**Evaluation Holdout Period**: Chronological test split (75 observations)

---

## 1. ETA Regression Model Comparison

| Model | MAE (mins) | RMSE (mins) | MedAE (mins) | Acc ≤ 15m (%) | Acc ≤ 30m (%) | Acc ≤ 60m (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Historical Baseline** | 319.57 | 420.8 | 192.56 | 1.33% | 4.0% | 12.0% |
| **Ridge Regression** | 129.68 | 184.26 | 96.07 | 6.67% | 9.33% | 25.33% |
| **Random Forest** | 108.37 | 181.14 | 45.96 | 22.67% | 40.0% | 53.33% |
| **Gradient Boosting** | **153.55** | **232.7** | **93.07** | **12.0%** | **22.67%** | **36.0%** |

---

## 2. Delay Probability Classification Comparison

| Model | Precision | Recall | F1-Score | ROC-AUC | PR-AUC | Brier Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline Frequency** | 0.0 | 0.0 | 0.0 | 0.5 | 0.3467 | 0.227 |
| **Logistic Regression** | 1.0 | 0.9615 | 0.9804 | 1.0 | 1.0 | 0.008 |
| **Random Forest** | 1.0 | 0.9615 | 0.9804 | 1.0 | 1.0 | 0.0085 |
| **Gradient Boosting** | **1.0** | **1.0** | **1.0** | **1.0** | **1.0** | **0.0** |

---

## 3. Top Feature Importances

| Feature Name | Importance Weight |
| :--- | :--- |
| `remaining_route_distance_km` | 0.5033 |
| `total_distance_km` | 0.4893 |
| `promised_remaining_hours` | 0.0019 |
| `target_delivery_hours` | 0.001 |
| `carrier_on_time_rating` | 0.0009 |
| `hour_of_day` | 0.0006 |
| `day_of_week` | 0.0005 |
| `weight_kg` | 0.0004 |
