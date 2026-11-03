"""
Pydantic Schemas for FastAPI Logistics ETA Prediction System
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    database_connected: bool
    timestamp: str


class ShipmentSummary(BaseModel):
    shipment_id: str
    order_id: str
    customer_id: str
    origin_facility_id: str
    destination_facility_id: str
    service_level_id: str
    primary_carrier_id: str
    status: str
    total_distance_km: float
    scheduled_pickup_time: str
    actual_pickup_time: Optional[str] = None
    promised_delivery_time: str
    actual_delivery_time: Optional[str] = None
    actual_delay_minutes: Optional[int] = None
    is_delayed: Optional[bool] = None


class ShipmentLegDetail(BaseModel):
    leg_id: str
    leg_sequence: int
    carrier_id: str
    origin_facility_id: str
    destination_facility_id: str
    leg_status: str
    distance_km: float
    estimated_transit_hours: float
    actual_transit_hours: Optional[float] = None
    scheduled_departure: str
    actual_departure: Optional[str] = None
    scheduled_arrival: str
    actual_arrival: Optional[str] = None


class TrackingEventDetail(BaseModel):
    event_id: str
    shipment_id: str
    leg_id: Optional[str] = None
    facility_id: Optional[str] = None
    event_timestamp: str
    ingestion_timestamp: str
    event_type: str
    event_location: str
    event_sequence: int
    event_source: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None


class ETAEstimateResponse(BaseModel):
    estimate_id: str
    shipment_id: str
    prediction_timestamp: str
    predicted_eta: str
    predicted_remaining_transit_minutes: float
    delay_probability: float
    confidence_lower_bound: Optional[str] = None
    confidence_upper_bound: Optional[str] = None
    primary_delay_reason: Optional[str] = None
    model_version: str
    model_name: str


class DelayReasonDetail(BaseModel):
    reason_id: str
    code: str
    category: str
    description: str
    attribution_score: float = 1.0
    is_primary: bool = True
    is_ground_truth: bool = True


class AlertResponse(BaseModel):
    alert_id: str
    shipment_id: str
    prediction_timestamp: str
    predicted_eta: str
    promised_delivery_time: str
    predicted_delay_minutes: int
    delay_probability: float
    delay_reason: str
    severity: str
    recommended_action: str
    status: str


class CarrierPerformanceResponse(BaseModel):
    carrier_id: str
    name: str
    code: str
    service_type: str
    on_time_rating: float
    total_shipments: int
    on_time_percentage: float
    average_delay_minutes: float


class FacilityPerformanceResponse(BaseModel):
    facility_id: str
    name: str
    facility_type: str
    city: str
    state: str
    current_queue_length: int
    average_wait_minutes: int
    processing_status: str


class ETAPredictionRequest(BaseModel):
    shipment_id: str = "SHP-2026-999999"
    prediction_timestamp: Optional[str] = None
    total_distance_km: float = 850.0
    remaining_route_distance_km: float = 850.0
    weight_kg: float = 18.5
    volume_cbm: float = 0.12
    carrier_on_time_rating: float = 0.92
    target_delivery_hours: int = 48
    promised_remaining_hours: float = 46.0
    elapsed_transit_hours: float = 2.0
    facility_queue_length: int = 24
    facility_queue_wait_minutes: int = 60
    weather_active_flag: int = 0
    weather_severity_score: int = 0
    delayed_scans_count: int = 0
    time_since_last_event_hours: float = 1.5
    hour_of_day: int = 14
    day_of_week: int = 2
    is_weekend: int = 0


class BatchPredictionRequest(BaseModel):
    shipments: List[ETAPredictionRequest]


class AlertEvaluationRequest(BaseModel):
    probability_threshold: float = 0.60
    limit: int = 100


# ==============================================================================
# RBAC and User Management Schemas
# ==============================================================================
class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserRegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    role: str = "SUPPLIER"  # SUPPLIER, LOGISTICS_PLANNER, CARRIER_OPERATOR, LOGISTICS_ANALYST, OPERATIONS_MANAGER
    customer_id: Optional[str] = None
    carrier_id: Optional[str] = None
    facility_id: Optional[str] = None


class UserLoginResponse(BaseModel):
    user_id: str
    full_name: str
    email: str
    role: str
    customer_id: Optional[str] = None
    carrier_id: Optional[str] = None
    facility_id: Optional[str] = None
    token: str


class SupplierCreateShipmentRequest(BaseModel):
    origin_facility_id: str
    destination_facility_id: str
    service_level_id: str = "SL-EXPRESS"
    weight_kg: float
    volume_cbm: float = 0.05
    scheduled_pickup_time: str
    promised_delivery_time: str
    customer_id: Optional[str] = None


class PlannerAssignCarrierRequest(BaseModel):
    shipment_id: str
    carrier_id: str
    route_id: Optional[str] = None
    intermediate_facility_id: Optional[str] = None


class OperatorRecordEventRequest(BaseModel):
    shipment_id: str
    event_type: str
    facility_id: Optional[str] = None
    leg_id: Optional[str] = None
    event_location: str
    event_source: str = "MANUAL_SCAN"
    notes: Optional[str] = None
    event_timestamp: Optional[str] = None


class OperatorUpdateQueueRequest(BaseModel):
    facility_id: str
    queue_length: int
    average_wait_time_minutes: int
    dock_utilization_pct: float
    processing_status: str = "NORMAL"


class AuditRecordResponse(BaseModel):
    audit_id: str
    user_id: str
    action_type: str
    entity_type: str
    entity_id: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    action_timestamp: str
    action_description: str

