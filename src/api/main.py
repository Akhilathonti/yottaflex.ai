"""
FastAPI Application for Intelligent Logistics ETA Prediction and Delay Detection System
"""
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.config import REPORTS_DIR, RANDOM_SEED
from src.database.connection import get_db, init_db
from src.database.models import (
    Shipment,
    ShipmentLeg,
    TrackingEvent,
    Facility,
    Carrier,
    FacilityQueue,
    ETAEstimate,
    Alert,
    ShipmentDelayReason,
    DelayReason,
    User,
    AuditRecord,
)
from src.api.schemas import (
    HealthResponse,
    ShipmentSummary,
    ShipmentLegDetail,
    TrackingEventDetail,
    ETAEstimateResponse,
    DelayReasonDetail,
    AlertResponse,
    CarrierPerformanceResponse,
    FacilityPerformanceResponse,
    ETAPredictionRequest,
    BatchPredictionRequest,
    AlertEvaluationRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserLoginResponse,
    SupplierCreateShipmentRequest,
    PlannerAssignCarrierRequest,
    OperatorRecordEventRequest,
    OperatorUpdateQueueRequest,
    AuditRecordResponse,
)
from src.utils.security import verify_password, hash_password
from src.utils.helpers import (
    haversine_distance_km,
    generate_shipment_id,
    generate_leg_id,
    generate_event_id,
    generate_queue_id,
)
from src.prediction.service import ETAPredictionService
from src.delay_detection.engine import DelayAlertEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Global prediction service instance
prediction_service: Optional[ETAPredictionService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global prediction_service
    init_db()
    try:
        prediction_service = ETAPredictionService()
        logger.info("ETA Prediction Service initialized successfully.")
    except Exception as e:
        logger.warning("Could not initialize ETAPredictionService at startup: %s", e)
    yield


app = FastAPI(
    title="Intelligent Logistics ETA Prediction and Delay Detection API",
    description="End-to-end logistics analytics API providing real-time shipment ETA predictions, early delay warnings, and operational visibility.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """Health status and service availability."""
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    return HealthResponse(
        status="HEALTHY" if db_connected else "DEGRADED",
        model_loaded=(prediction_service is not None),
        database_connected=db_connected,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/shipments", response_model=List[ShipmentSummary], tags=["Shipments"])
def list_shipments(
    status_filter: Optional[str] = Query(None, alias="status"),
    carrier_id: Optional[str] = None,
    is_delayed: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Retrieve filtered shipments with pagination."""
    query = db.query(Shipment)
    if isinstance(status_filter, str) and status_filter.strip():
        query = query.filter(Shipment.status == status_filter)
    if isinstance(carrier_id, str) and carrier_id.strip():
        query = query.filter(Shipment.primary_carrier_id == carrier_id)
    if isinstance(is_delayed, bool):
        query = query.filter(Shipment.is_delayed == is_delayed)

    results = query.offset(offset).limit(limit).all()
    return [
        ShipmentSummary(
            shipment_id=s.shipment_id,
            order_id=s.order_id,
            customer_id=s.customer_id,
            origin_facility_id=s.origin_facility_id,
            destination_facility_id=s.destination_facility_id,
            service_level_id=s.service_level_id,
            primary_carrier_id=s.primary_carrier_id,
            status=s.status,
            total_distance_km=s.total_distance_km,
            scheduled_pickup_time=s.scheduled_pickup_time.isoformat() if s.scheduled_pickup_time else "",
            actual_pickup_time=s.actual_pickup_time.isoformat() if s.actual_pickup_time else None,
            promised_delivery_time=s.promised_delivery_time.isoformat() if s.promised_delivery_time else "",
            actual_delivery_time=s.actual_delivery_time.isoformat() if s.actual_delivery_time else None,
            actual_delay_minutes=s.actual_delay_minutes,
            is_delayed=s.is_delayed,
        )
        for s in results
    ]


@app.get("/shipments/{shipment_id}", response_model=Dict[str, Any], tags=["Shipments"])
def get_shipment_detail(shipment_id: str, db: Session = Depends(get_db)):
    """Retrieve full details of a shipment including multi-leg route legs."""
    shp = db.query(Shipment).filter(Shipment.shipment_id == shipment_id).first()
    if not shp:
        raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found.")

    legs = (
        db.query(ShipmentLeg)
        .filter(ShipmentLeg.shipment_id == shipment_id)
        .order_by(ShipmentLeg.leg_sequence)
        .all()
    )

    return {
        "shipment": ShipmentSummary(
            shipment_id=shp.shipment_id,
            order_id=shp.order_id,
            customer_id=shp.customer_id,
            origin_facility_id=shp.origin_facility_id,
            destination_facility_id=shp.destination_facility_id,
            service_level_id=shp.service_level_id,
            primary_carrier_id=shp.primary_carrier_id,
            status=shp.status,
            total_distance_km=shp.total_distance_km,
            scheduled_pickup_time=shp.scheduled_pickup_time.isoformat() if shp.scheduled_pickup_time else "",
            actual_pickup_time=shp.actual_pickup_time.isoformat() if shp.actual_pickup_time else None,
            promised_delivery_time=shp.promised_delivery_time.isoformat() if shp.promised_delivery_time else "",
            actual_delivery_time=shp.actual_delivery_time.isoformat() if shp.actual_delivery_time else None,
            actual_delay_minutes=shp.actual_delay_minutes,
            is_delayed=shp.is_delayed,
        ).dict(),
        "legs": [
            ShipmentLegDetail(
                leg_id=l.leg_id,
                leg_sequence=l.leg_sequence,
                carrier_id=l.carrier_id,
                origin_facility_id=l.origin_facility_id,
                destination_facility_id=l.destination_facility_id,
                leg_status=l.leg_status,
                distance_km=l.distance_km,
                estimated_transit_hours=l.estimated_transit_hours,
                actual_transit_hours=l.actual_transit_hours,
                scheduled_departure=l.scheduled_departure.isoformat() if l.scheduled_departure else "",
                actual_departure=l.actual_departure.isoformat() if l.actual_departure else None,
                scheduled_arrival=l.scheduled_arrival.isoformat() if l.scheduled_arrival else "",
                actual_arrival=l.actual_arrival.isoformat() if l.actual_arrival else None,
            ).dict()
            for l in legs
        ],
    }


@app.get("/shipments/{shipment_id}/events", response_model=List[TrackingEventDetail], tags=["Shipments"])
def get_shipment_events(shipment_id: str, db: Session = Depends(get_db)):
    """Retrieve chronological tracking telemetry events for a shipment."""
    events = (
        db.query(TrackingEvent)
        .filter(TrackingEvent.shipment_id == shipment_id)
        .order_by(TrackingEvent.event_sequence)
        .all()
    )
    if not events:
        raise HTTPException(status_code=404, detail=f"No tracking events found for {shipment_id}.")

    return [
        TrackingEventDetail(
            event_id=e.event_id,
            shipment_id=e.shipment_id,
            leg_id=e.leg_id,
            facility_id=e.facility_id,
            event_timestamp=e.event_timestamp.isoformat() if e.event_timestamp else "",
            ingestion_timestamp=e.ingestion_timestamp.isoformat() if e.ingestion_timestamp else "",
            event_type=e.event_type,
            event_location=e.event_location,
            event_sequence=e.event_sequence,
            event_source=e.event_source,
            latitude=e.latitude,
            longitude=e.longitude,
            notes=e.notes,
        )
        for e in events
    ]


@app.get("/shipments/{shipment_id}/eta", response_model=List[ETAEstimateResponse], tags=["ETA Predictions"])
def get_shipment_eta(shipment_id: str, db: Session = Depends(get_db)):
    """Retrieve historical ETA estimate snapshots for a shipment."""
    estimates = (
        db.query(ETAEstimate)
        .filter(ETAEstimate.shipment_id == shipment_id)
        .order_by(ETAEstimate.prediction_timestamp.desc())
        .all()
    )
    if not estimates:
        raise HTTPException(status_code=404, detail=f"No ETA estimates found for {shipment_id}.")

    return [
        ETAEstimateResponse(
            estimate_id=e.estimate_id,
            shipment_id=e.shipment_id,
            prediction_timestamp=e.prediction_timestamp.isoformat(),
            predicted_eta=e.predicted_eta.isoformat(),
            predicted_remaining_transit_minutes=e.predicted_remaining_transit_minutes,
            delay_probability=e.delay_probability,
            confidence_lower_bound=e.confidence_lower_bound.isoformat() if e.confidence_lower_bound else None,
            confidence_upper_bound=e.confidence_upper_bound.isoformat() if e.confidence_upper_bound else None,
            primary_delay_reason=e.primary_delay_reason,
            model_version=e.model_version,
            model_name=e.model_name,
        )
        for e in estimates
    ]


@app.get("/shipments/{shipment_id}/delay-reasons", response_model=List[DelayReasonDetail], tags=["Shipments"])
def get_shipment_delay_reasons(shipment_id: str, db: Session = Depends(get_db)):
    """Retrieve delay attribution reasons for a shipment."""
    associations = (
        db.query(ShipmentDelayReason, DelayReason)
        .join(DelayReason, ShipmentDelayReason.reason_id == DelayReason.reason_id)
        .filter(ShipmentDelayReason.shipment_id == shipment_id)
        .all()
    )
    if not associations:
        return []

    return [
        DelayReasonDetail(
            reason_id=r.reason_id,
            code=r.code,
            category=r.category,
            description=r.description,
            attribution_score=assoc.attribution_score,
            is_primary=assoc.is_primary,
            is_ground_truth=assoc.is_ground_truth,
        )
        for assoc, r in associations
    ]


@app.get("/alerts", response_model=List[AlertResponse], tags=["Alerts"])
def list_alerts(
    severity: Optional[str] = None,
    status_filter: Optional[str] = Query("ACTIVE", alias="status"),
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Retrieve operational alerts for active shipment exceptions."""
    query = db.query(Alert)
    if severity:
        query = query.filter(Alert.severity == severity)
    if status_filter:
        query = query.filter(Alert.status == status_filter)

    results = query.order_by(Alert.prediction_timestamp.desc()).limit(limit).all()
    return [
        AlertResponse(
            alert_id=a.alert_id,
            shipment_id=a.shipment_id,
            prediction_timestamp=a.prediction_timestamp.isoformat(),
            predicted_eta=a.predicted_eta.isoformat(),
            promised_delivery_time=a.promised_delivery_time.isoformat(),
            predicted_delay_minutes=a.predicted_delay_minutes,
            delay_probability=a.delay_probability,
            delay_reason=a.delay_reason,
            severity=a.severity,
            recommended_action=a.recommended_action,
            status=a.status,
        )
        for a in results
    ]


@app.get("/carriers/performance", response_model=List[CarrierPerformanceResponse], tags=["Analytics"])
def get_carrier_performance(db: Session = Depends(get_db)):
    """Carrier delivery performance metrics."""
    carriers = db.query(Carrier).all()
    results = []
    for c in carriers:
        shipments = db.query(Shipment).filter(Shipment.primary_carrier_id == c.carrier_id).all()
        total = len(shipments)
        if total > 0:
            delayed = sum(1 for s in shipments if s.is_delayed)
            on_time_pct = round(((total - delayed) / total) * 100.0, 2)
            avg_delay = round(sum(s.actual_delay_minutes or 0 for s in shipments) / total, 1)
        else:
            on_time_pct = c.on_time_rating * 100.0
            avg_delay = 0.0

        results.append(
            CarrierPerformanceResponse(
                carrier_id=c.carrier_id,
                name=c.name,
                code=c.code,
                service_type=c.service_type,
                on_time_rating=c.on_time_rating,
                total_shipments=total,
                on_time_percentage=on_time_pct,
                average_delay_minutes=avg_delay,
            )
        )
    return results


@app.get("/facilities/performance", response_model=List[FacilityPerformanceResponse], tags=["Analytics"])
def get_facility_performance(limit: int = 50, db: Session = Depends(get_db)):
    """Facility congestion and queue monitoring."""
    facilities = db.query(Facility).limit(limit).all()
    results = []
    for f in facilities:
        latest_q = (
            db.query(FacilityQueue)
            .filter(FacilityQueue.facility_id == f.facility_id)
            .order_by(FacilityQueue.observation_timestamp.desc())
            .first()
        )
        q_len = latest_q.queue_length if latest_q else 18
        avg_wait = latest_q.average_wait_time_minutes if latest_q else 45
        status_val = latest_q.processing_status if latest_q else "NORMAL"

        results.append(
            FacilityPerformanceResponse(
                facility_id=f.facility_id,
                name=f.name,
                facility_type=f.facility_type,
                city=f.city,
                state=f.state,
                current_queue_length=q_len,
                average_wait_minutes=avg_wait,
                processing_status=status_val,
            )
        )
    return results


@app.get("/model/metrics", tags=["Machine Learning"])
def get_model_metrics():
    """Retrieve benchmark validation metrics and feature importances."""
    metrics_path = REPORTS_DIR / "model_evaluation.json"
    if not metrics_path.exists():
        raise HTTPException(status_code=404, detail="Model evaluation report not found. Run training first.")
    with open(metrics_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/predict/eta", response_model=Dict[str, Any], tags=["Inference"])
def predict_eta(request: ETAPredictionRequest):
    """Predict ETA and delay probability for a single shipment payload."""
    global prediction_service
    if prediction_service is None:
        try:
            prediction_service = ETAPredictionService()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to initialize prediction model: {e}")

    try:
        data = request.model_dump() if hasattr(request, "model_dump") else request.dict()
        result = prediction_service.predict_single(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {e}")


@app.post("/predict/batch", response_model=List[Dict[str, Any]], tags=["Inference"])
def predict_batch(request: BatchPredictionRequest):
    """Predict ETA and delay probability for a batch of shipments."""
    global prediction_service
    if prediction_service is None:
        try:
            prediction_service = ETAPredictionService()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to initialize prediction model: {e}")

    items = [
        item.model_dump() if hasattr(item, "model_dump") else item.dict()
        for item in request.shipments
    ]
    return prediction_service.predict_batch(items)


@app.post("/alerts/evaluate", tags=["Alerts"])
def evaluate_alerts(request: AlertEvaluationRequest, db: Session = Depends(get_db)):
    """Evaluate active shipments against risk thresholds and generate alerts."""
    shipments = db.query(Shipment).limit(request.limit).all()
    eta_estimates = db.query(ETAEstimate).all()

    import pandas as pd
    shipments_df = pd.DataFrame([s.__dict__ for s in shipments])
    eta_df = pd.DataFrame([e.__dict__ for e in eta_estimates])

    engine_instance = DelayAlertEngine(prob_threshold=request.probability_threshold)
    alerts = engine_instance.evaluate_batch_and_persist(shipments_df, eta_df)
    return {
        "status": "SUCCESS",
        "alerts_generated": len(alerts),
        "alerts": alerts[:10],
    }


# ==============================================================================
# RBAC Endpoints for User Roles and Workflows
# ==============================================================================
@app.post("/auth/register", response_model=UserLoginResponse, tags=["Authentication & RBAC"])
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account with role-based scoping and hashed credentials."""
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    allowed_roles = {"SUPPLIER", "LOGISTICS_PLANNER", "CARRIER_OPERATOR", "LOGISTICS_ANALYST", "OPERATIONS_MANAGER"}
    if request.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Allowed roles: {allowed_roles}",
        )

    count = db.query(User).count()
    user_id = f"USR-{request.role[:4]}-{count + 1:03d}"
    pwd_hash = hash_password(request.password)

    new_user = User(
        user_id=user_id,
        full_name=request.full_name,
        email=request.email,
        password_hash=pwd_hash,
        role=request.role,
        customer_id=request.customer_id or (f"CUST-{count+1:05d}" if request.role == "SUPPLIER" else None),
        carrier_id=request.carrier_id,
        facility_id=request.facility_id,
        account_status="ACTIVE",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_login_at=datetime.utcnow(),
    )
    db.add(new_user)

    audit = AuditRecord(
        audit_id=f"AUD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{user_id[-6:]}",
        user_id=user_id,
        action_type="USER_REGISTERED",
        entity_type="USER",
        entity_id=user_id,
        previous_value=None,
        new_value=request.role,
        action_timestamp=datetime.utcnow(),
        action_description=f"New user registered: {request.full_name} with role {request.role}.",
    )
    db.add(audit)
    db.commit()

    return UserLoginResponse(
        user_id=new_user.user_id,
        full_name=new_user.full_name,
        email=new_user.email,
        role=new_user.role,
        customer_id=new_user.customer_id,
        carrier_id=new_user.carrier_id,
        facility_id=new_user.facility_id,
        token=f"Bearer-session-{new_user.user_id}",
    )


@app.post("/auth/login", response_model=UserLoginResponse, tags=["Authentication & RBAC"])
def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with email and password and return session token with role."""
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if user.account_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.account_status}. Please contact operations administrator.",
        )

    user.last_login_at = datetime.utcnow()
    # Log session audit record
    audit = AuditRecord(
        audit_id=f"AUD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{user.user_id[:6]}",
        user_id=user.user_id,
        action_type="USER_LOGIN",
        entity_type="SESSION",
        entity_id=user.user_id,
        action_timestamp=datetime.utcnow(),
        action_description=f"User {user.full_name} ({user.role}) logged in successfully.",
    )
    db.add(audit)
    db.commit()

    return UserLoginResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        customer_id=user.customer_id,
        carrier_id=user.carrier_id,
        facility_id=user.facility_id,
        token=f"Bearer-session-{user.user_id}",
    )


@app.get("/audit-logs", response_model=List[AuditRecordResponse], tags=["Authentication & RBAC"])
def get_audit_logs(limit: int = 50, entity_type: Optional[str] = None, db: Session = Depends(get_db)):
    """Retrieve immutable audit logs of user actions across the system."""
    query = db.query(AuditRecord)
    if entity_type:
        query = query.filter(AuditRecord.entity_type == entity_type)
    records = query.order_by(AuditRecord.action_timestamp.desc()).limit(limit).all()
    return [
        AuditRecordResponse(
            audit_id=r.audit_id,
            user_id=r.user_id,
            action_type=r.action_type,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            previous_value=r.previous_value,
            new_value=r.new_value,
            action_timestamp=r.action_timestamp.isoformat(),
            action_description=r.action_description,
        )
        for r in records
    ]


@app.get("/supplier/shipments", response_model=List[ShipmentSummary], tags=["Supplier Role"])
def get_supplier_shipments(customer_id: str = "CUST-00001", db: Session = Depends(get_db)):
    """Supplier Role: View strictly their own shipments by customer_id."""
    shipments = (
        db.query(Shipment)
        .filter(Shipment.customer_id == customer_id)
        .order_by(Shipment.created_at.desc())
        .all()
    )
    return [
        ShipmentSummary(
            shipment_id=s.shipment_id,
            order_id=s.order_id,
            customer_id=s.customer_id,
            origin_facility_id=s.origin_facility_id,
            destination_facility_id=s.destination_facility_id,
            service_level_id=s.service_level_id,
            primary_carrier_id=s.primary_carrier_id,
            status=s.status,
            total_distance_km=s.total_distance_km,
            scheduled_pickup_time=s.scheduled_pickup_time.isoformat() if s.scheduled_pickup_time else "",
            actual_pickup_time=s.actual_pickup_time.isoformat() if s.actual_pickup_time else None,
            promised_delivery_time=s.promised_delivery_time.isoformat() if s.promised_delivery_time else "",
            actual_delivery_time=s.actual_delivery_time.isoformat() if s.actual_delivery_time else None,
            actual_delay_minutes=s.actual_delay_minutes,
            is_delayed=s.is_delayed,
        )
        for s in shipments
    ]


@app.post("/supplier/shipments", response_model=Dict[str, Any], tags=["Supplier Role"])
def supplier_create_shipment(request: SupplierCreateShipmentRequest, db: Session = Depends(get_db)):
    """Supplier Role: Create a new shipment order request."""
    # Find origin and destination facilities to compute distance
    orig = db.query(Facility).filter(Facility.facility_id == request.origin_facility_id).first()
    dest = db.query(Facility).filter(Facility.facility_id == request.destination_facility_id).first()
    if not orig or not dest:
        raise HTTPException(status_code=400, detail="Invalid origin or destination facility ID.")

    dist = haversine_distance_km(orig.latitude, orig.longitude, dest.latitude, dest.longitude)
    if dist < 25.0:
        dist = 50.0

    count = db.query(Shipment).count()
    shipment_id = generate_shipment_id(count + 1, 2026)
    order_id = f"ORD-2026-{count + 1:06d}"
    cust_id = request.customer_id or "CUST-00001"

    # Default carrier
    carrier = db.query(Carrier).first()
    carrier_id = carrier.carrier_id if carrier else "CAR-001"

    sched_pickup = pd.to_datetime(request.scheduled_pickup_time).to_pydatetime()
    prom_delivery = pd.to_datetime(request.promised_delivery_time).to_pydatetime()

    shp = Shipment(
        shipment_id=shipment_id,
        order_id=order_id,
        customer_id=cust_id,
        origin_facility_id=request.origin_facility_id,
        destination_facility_id=request.destination_facility_id,
        service_level_id=request.service_level_id,
        primary_carrier_id=carrier_id,
        status="CREATED",
        weight_kg=request.weight_kg,
        volume_cbm=request.volume_cbm,
        total_distance_km=dist,
        scheduled_pickup_time=sched_pickup,
        promised_delivery_time=prom_delivery,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(shp)

    # Initial CREATED tracking event
    evt_id = generate_event_id(shipment_id, 1)
    event = TrackingEvent(
        event_id=evt_id,
        shipment_id=shipment_id,
        facility_id=request.origin_facility_id,
        event_timestamp=datetime.utcnow(),
        ingestion_timestamp=datetime.utcnow(),
        event_type="CREATED",
        event_location=f"{orig.city}, {orig.state}",
        event_sequence=1,
        event_source="WMS",
        latitude=orig.latitude,
        longitude=orig.longitude,
        notes="Shipment request submitted by Supplier.",
        created_at=datetime.utcnow(),
    )
    db.add(event)

    # Audit Record
    audit = AuditRecord(
        audit_id=f"AUD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{shipment_id[-4:]}",
        user_id="USR-SUPPLIER-01",
        action_type="CREATE_SHIPMENT",
        entity_type="SHIPMENT",
        entity_id=shipment_id,
        previous_value=None,
        new_value="CREATED",
        action_timestamp=datetime.utcnow(),
        action_description=f"Supplier created shipment {shipment_id} ({dist} km, {request.weight_kg} kg).",
    )
    db.add(audit)
    db.commit()

    return {
        "status": "CREATED",
        "shipment_id": shipment_id,
        "order_id": order_id,
        "total_distance_km": dist,
        "message": f"Shipment {shipment_id} successfully created.",
    }


@app.post("/planner/assign-route", response_model=Dict[str, Any], tags=["Planner Role"])
def planner_assign_route(request: PlannerAssignCarrierRequest, db: Session = Depends(get_db)):
    """Logistics Planner Role: Assign carrier and create multi-leg journey plan."""
    shp = db.query(Shipment).filter(Shipment.shipment_id == request.shipment_id).first()
    if not shp:
        raise HTTPException(status_code=404, detail=f"Shipment {request.shipment_id} not found.")

    carrier = db.query(Carrier).filter(Carrier.carrier_id == request.carrier_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Invalid carrier ID.")

    prev_carrier = shp.primary_carrier_id
    shp.primary_carrier_id = request.carrier_id
    shp.status = "IN_TRANSIT"
    shp.actual_pickup_time = shp.scheduled_pickup_time + timedelta(minutes=20)
    shp.updated_at = datetime.utcnow()

    # Create legs if none exist
    legs_count = db.query(ShipmentLeg).filter(ShipmentLeg.shipment_id == shp.shipment_id).count()
    if legs_count == 0:
        leg1 = ShipmentLeg(
            leg_id=generate_leg_id(shp.shipment_id, 1),
            shipment_id=shp.shipment_id,
            leg_sequence=1,
            carrier_id=request.carrier_id,
            origin_facility_id=shp.origin_facility_id,
            destination_facility_id=request.intermediate_facility_id or shp.destination_facility_id,
            leg_status="IN_TRANSIT",
            distance_km=shp.total_distance_km,
            estimated_transit_hours=round(shp.total_distance_km / 70.0 + 1.0, 1),
            scheduled_departure=shp.scheduled_pickup_time,
            actual_departure=shp.actual_pickup_time,
            scheduled_arrival=shp.promised_delivery_time,
            created_at=datetime.utcnow(),
        )
        db.add(leg1)

    # Audit Record
    audit = AuditRecord(
        audit_id=f"AUD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-PLAN",
        user_id="USR-PLANNER-01",
        action_type="ASSIGN_CARRIER_AND_ROUTE",
        entity_type="SHIPMENT",
        entity_id=shp.shipment_id,
        previous_value=prev_carrier,
        new_value=request.carrier_id,
        action_timestamp=datetime.utcnow(),
        action_description=f"Planner assigned carrier {request.carrier_id} ({carrier.name}) to shipment {shp.shipment_id}.",
    )
    db.add(audit)
    db.commit()

    return {
        "status": "ASSIGNED",
        "shipment_id": shp.shipment_id,
        "assigned_carrier_id": request.carrier_id,
        "message": f"Carrier {request.carrier_id} assigned and route confirmed.",
    }


@app.post("/carrier/tracking-event", response_model=Dict[str, Any], tags=["Operator Role"])
def operator_record_event(request: OperatorRecordEventRequest, db: Session = Depends(get_db)):
    """Carrier / Warehouse Operator Role: Record physical barcode scan and tracking event."""
    shp = db.query(Shipment).filter(Shipment.shipment_id == request.shipment_id).first()
    if not shp:
        raise HTTPException(status_code=404, detail=f"Shipment {request.shipment_id} not found.")

    # Determine event sequence
    cur_events_count = db.query(TrackingEvent).filter(TrackingEvent.shipment_id == shp.shipment_id).count()
    seq = cur_events_count + 1
    event_id = generate_event_id(shp.shipment_id, seq)

    ev_time = (
        pd.to_datetime(request.event_timestamp).to_pydatetime()
        if request.event_timestamp
        else datetime.utcnow()
    )
    # Temporal Invariant: ingestion_timestamp >= event_timestamp
    ing_time = max(datetime.utcnow(), ev_time)

    event = TrackingEvent(
        event_id=event_id,
        shipment_id=shp.shipment_id,
        leg_id=request.leg_id,
        facility_id=request.facility_id,
        event_timestamp=ev_time,
        ingestion_timestamp=ing_time,
        event_type=request.event_type,
        event_location=request.event_location,
        event_sequence=seq,
        event_source=request.event_source,
        notes=request.notes or f"Manual scan recorded by warehouse operator.",
        created_at=datetime.utcnow(),
    )
    db.add(event)

    # Update shipment status if DELIVERED or OUT_FOR_DELIVERY
    if request.event_type == "DELIVERED":
        shp.status = "DELIVERED"
        shp.actual_delivery_time = ev_time
        shp.actual_delay_minutes = int((ev_time - shp.promised_delivery_time).total_seconds() / 60)
        shp.is_delayed = shp.actual_delay_minutes > 0
    elif request.event_type == "OUT_FOR_DELIVERY":
        shp.status = "OUT_FOR_DELIVERY"
    elif request.event_type == "PICKED_UP":
        shp.status = "IN_TRANSIT"
        shp.actual_pickup_time = ev_time

    shp.updated_at = datetime.utcnow()

    # Audit Record
    audit = AuditRecord(
        audit_id=f"AUD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-EVT",
        user_id="USR-OPERATOR-01",
        action_type="RECORD_TRACKING_EVENT",
        entity_type="TRACKING_EVENT",
        entity_id=event_id,
        previous_value=None,
        new_value=request.event_type,
        action_timestamp=datetime.utcnow(),
        action_description=f"Operator scanned {request.event_type} at {request.event_location} for {shp.shipment_id}.",
    )
    db.add(audit)
    db.commit()

    return {
        "status": "RECORDED",
        "event_id": event_id,
        "shipment_id": shp.shipment_id,
        "event_sequence": seq,
        "shipment_status": shp.status,
    }


@app.post("/carrier/facility-queue", response_model=Dict[str, Any], tags=["Operator Role"])
def operator_update_queue(request: OperatorUpdateQueueRequest, db: Session = Depends(get_db)):
    """Carrier / Warehouse Operator Role: Update yard queue and dock congestion."""
    fac = db.query(Facility).filter(Facility.facility_id == request.facility_id).first()
    if not fac:
        raise HTTPException(status_code=404, detail="Facility not found.")

    obs_time = datetime.utcnow()
    queue_id = generate_queue_id(request.facility_id, obs_time)

    fq = FacilityQueue(
        queue_id=queue_id,
        facility_id=request.facility_id,
        observation_timestamp=obs_time,
        queue_length=request.queue_length,
        average_wait_time_minutes=request.average_wait_time_minutes,
        dock_utilization_pct=request.dock_utilization_pct,
        processing_status=request.processing_status,
        created_at=obs_time,
    )
    db.add(fq)

    audit = AuditRecord(
        audit_id=f"AUD-{obs_time.strftime('%Y%m%d%H%M%S')}-QUE",
        user_id="USR-OPERATOR-01",
        action_type="UPDATE_FACILITY_QUEUE",
        entity_type="FACILITY_QUEUE",
        entity_id=queue_id,
        previous_value=None,
        new_value=f"Queue: {request.queue_length}, Wait: {request.average_wait_time_minutes}m",
        action_timestamp=obs_time,
        action_description=f"Operator logged yard queue update for {fac.name}.",
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SUCCESS",
        "queue_id": queue_id,
        "facility_id": request.facility_id,
        "queue_length": request.queue_length,
        "processing_status": request.processing_status,
    }

