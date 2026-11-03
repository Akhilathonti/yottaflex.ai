"""
End-to-End Prediction Service and Alerting Tests
"""
from datetime import datetime, timedelta
import pytest
from src.prediction.service import ETAPredictionService
from src.delay_detection.engine import DelayAlertEngine


@pytest.fixture
def prediction_service():
    return ETAPredictionService()


def test_single_shipment_prediction(prediction_service):
    payload = {
        "shipment_id": "SHP-2026-TEST01",
        "prediction_timestamp": "2026-07-01T12:00:00",
        "total_distance_km": 750.0,
        "remaining_route_distance_km": 750.0,
        "weight_kg": 25.0,
        "volume_cbm": 0.15,
        "carrier_on_time_rating": 0.94,
        "target_delivery_hours": 48,
        "promised_remaining_hours": 46.0,
        "elapsed_transit_hours": 2.0,
        "facility_queue_length": 15,
        "facility_queue_wait_minutes": 30,
        "weather_active_flag": 0,
        "weather_severity_score": 0,
        "delayed_scans_count": 0,
        "time_since_last_event_hours": 1.0,
        "hour_of_day": 12,
        "day_of_week": 2,
        "is_weekend": 0,
    }

    result = prediction_service.predict_single(payload)

    assert result["shipment_id"] == "SHP-2026-TEST01"
    assert result["predicted_remaining_transit_minutes"] > 0
    assert 0.0 <= result["delay_probability"] <= 1.0
    assert "predicted_eta" in result
    assert result["model_version"] == "v1.0.0-champion"


def test_batch_prediction(prediction_service):
    batch = [
        {"shipment_id": f"SHP-2026-B{i}", "total_distance_km": 400.0 + i * 100, "remaining_route_distance_km": 400.0}
        for i in range(5)
    ]
    results = prediction_service.predict_batch(batch)
    assert len(results) == 5
    for r in results:
        assert r["predicted_remaining_transit_minutes"] > 0


def test_delay_alert_generation():
    engine = DelayAlertEngine(prob_threshold=0.60)
    now = datetime(2026, 7, 1, 12, 0, 0)
    promised = now + timedelta(hours=2)
    predicted_late_eta = now + timedelta(hours=6)  # 4 hours late

    alert = engine.evaluate_shipment_risk(
        shipment_id="SHP-2026-ALERT01",
        predicted_eta=predicted_late_eta,
        promised_delivery_time=promised,
        delay_probability=0.88,
        current_status="IN_TRANSIT",
        weather_active=True,
    )

    assert alert is not None
    assert alert["shipment_id"] == "SHP-2026-ALERT01"
    assert alert["severity"] in ["HIGH", "CRITICAL"]
    assert alert["predicted_delay_minutes"] > 0
    assert alert["delay_reason"] == "WEATHER_DISRUPTION"
    assert "recommended_action" in alert
