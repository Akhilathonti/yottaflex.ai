"""
FastAPI Endpoints Direct Integration Test Suite
Tests endpoint handler functions, schemas, database querying, and predictions synchronously.
"""
import pytest
from src.database.connection import SessionLocal
from src.api.main import (
    health_check,
    list_shipments,
    get_shipment_detail,
    get_shipment_events,
    get_carrier_performance,
    get_facility_performance,
    get_model_metrics,
    predict_eta,
    predict_batch,
    evaluate_alerts,
)
from src.api.schemas import (
    ETAPredictionRequest,
    BatchPredictionRequest,
    AlertEvaluationRequest,
)


@pytest.fixture
def db_session():
    session = SessionLocal()
    yield session
    session.close()


def test_health_handler(db_session):
    res = health_check(db=db_session)
    assert res.status in ["HEALTHY", "DEGRADED"]
    assert res.database_connected is True


def test_list_shipments_handler(db_session):
    shipments = list_shipments(limit=5, offset=0, db=db_session)
    assert isinstance(shipments, list)
    assert len(shipments) > 0
    assert shipments[0].shipment_id.startswith("SHP-")


def test_shipment_detail_handler(db_session):
    shipments = list_shipments(limit=1, offset=0, db=db_session)
    shp_id = shipments[0].shipment_id

    detail = get_shipment_detail(shipment_id=shp_id, db=db_session)
    assert "shipment" in detail
    assert "legs" in detail
    assert detail["shipment"]["shipment_id"] == shp_id
    assert len(detail["legs"]) >= 1


def test_shipment_events_handler(db_session):
    shipments = list_shipments(limit=1, offset=0, db=db_session)
    shp_id = shipments[0].shipment_id

    events = get_shipment_events(shipment_id=shp_id, db=db_session)
    assert isinstance(events, list)
    assert len(events) > 0
    assert events[0].event_sequence == 1


def test_carrier_performance_handler(db_session):
    carriers = get_carrier_performance(db=db_session)
    assert len(carriers) > 0
    assert hasattr(carriers[0], "on_time_percentage")


def test_facilities_performance_handler(db_session):
    facilities = get_facility_performance(limit=5, db=db_session)
    assert len(facilities) > 0
    assert hasattr(facilities[0], "current_queue_length")


def test_model_metrics_handler():
    metrics = get_model_metrics()
    assert "regression_comparison" in metrics
    assert "champion_model" in metrics


def test_predict_eta_handler():
    req = ETAPredictionRequest(
        shipment_id="SHP-2026-UNITTEST",
        total_distance_km=650.0,
        remaining_route_distance_km=650.0,
        carrier_on_time_rating=0.93,
        facility_queue_length=20,
    )
    result = predict_eta(req)
    assert result["shipment_id"] == "SHP-2026-UNITTEST"
    assert result["predicted_remaining_transit_minutes"] > 0
    assert 0.0 <= result["delay_probability"] <= 1.0


def test_batch_predict_handler():
    req = BatchPredictionRequest(
        shipments=[
            ETAPredictionRequest(shipment_id=f"SHP-2026-B{i}", total_distance_km=500.0)
            for i in range(3)
        ]
    )
    results = predict_batch(req)
    assert len(results) == 3


def test_evaluate_alerts_handler(db_session):
    req = AlertEvaluationRequest(probability_threshold=0.50, limit=20)
    res = evaluate_alerts(req, db=db_session)
    assert res["status"] == "SUCCESS"
    assert "alerts_generated" in res
