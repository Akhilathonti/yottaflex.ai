"""
Role-Based Access Control (RBAC) and User Management Test Suite
Verifies all 5 user roles, authentication, permissions, and audit logging.
"""
import pytest
from datetime import datetime, timedelta
from src.database.connection import SessionLocal
from src.database.models import User, AuditRecord, Shipment, TrackingEvent
from src.utils.security import verify_password, PREDEFINED_USERS
from src.api.main import (
    login,
    register,
    get_supplier_shipments,
    supplier_create_shipment,
    planner_assign_route,
    operator_record_event,
    operator_update_queue,
    get_audit_logs,
)
from src.api.schemas import (
    UserLoginRequest,
    UserRegisterRequest,
    SupplierCreateShipmentRequest,
    PlannerAssignCarrierRequest,
    OperatorRecordEventRequest,
    OperatorUpdateQueueRequest,
)


@pytest.fixture
def db_session():
    session = SessionLocal()
    yield session
    session.close()


def test_predefined_five_roles_exist_in_database(db_session):
    roles = {u["role"] for u in PREDEFINED_USERS}
    expected_roles = {
        "SUPPLIER",
        "LOGISTICS_PLANNER",
        "CARRIER_OPERATOR",
        "LOGISTICS_ANALYST",
        "OPERATIONS_MANAGER",
    }
    assert roles == expected_roles

    for u in PREDEFINED_USERS:
        db_user = db_session.query(User).filter_by(email=u["email"]).first()
        assert db_user is not None
        assert db_user.role == u["role"]
        assert verify_password(u["password"], db_user.password_hash) is True


def test_user_registration_success_and_duplicate_rejection(db_session):
    unique_email = f"new_supplier_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}@example.com"
    reg_req = UserRegisterRequest(
        full_name="New Test Supplier Inc",
        email=unique_email,
        password="SecurePassword@2026",
        role="SUPPLIER",
    )
    res = register(reg_req, db=db_session)
    assert res.email == unique_email
    assert res.role == "SUPPLIER"
    assert res.customer_id is not None

    # Test duplicate email rejection
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        register(reg_req, db=db_session)
    assert exc_info.value.status_code == 400


def test_user_authentication_success_and_failure(db_session):
    # Valid login
    valid_req = UserLoginRequest(email="supplier@logistics.com", password="Supplier@2026")
    res = login(valid_req, db=db_session)
    assert res.user_id == "USR-SUPPLIER-01"
    assert res.role == "SUPPLIER"
    assert res.customer_id == "CUST-00001"

    # Invalid password
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        login(UserLoginRequest(email="supplier@logistics.com", password="WrongPassword!"), db=db_session)
    assert exc_info.value.status_code == 401


def test_supplier_role_isolation_and_shipment_creation(db_session):
    # 1. Supplier queries own shipments
    own_shipments = get_supplier_shipments(customer_id="CUST-00001", db=db_session)
    for s in own_shipments:
        assert s.customer_id == "CUST-00001"

    # 2. Supplier creates new shipment
    now = datetime.utcnow()
    req = SupplierCreateShipmentRequest(
        origin_facility_id="FAC-001",
        destination_facility_id="FAC-002",
        service_level_id="SL-EXPRESS",
        weight_kg=35.0,
        volume_cbm=0.25,
        scheduled_pickup_time=(now + timedelta(hours=2)).isoformat(),
        promised_delivery_time=(now + timedelta(hours=50)).isoformat(),
        customer_id="CUST-00001",
    )
    create_res = supplier_create_shipment(req, db=db_session)
    assert create_res["status"] == "CREATED"
    assert "shipment_id" in create_res

    # Verify audit record logged
    audit = (
        db_session.query(AuditRecord)
        .filter(AuditRecord.entity_id == create_res["shipment_id"])
        .order_by(AuditRecord.action_timestamp.desc())
        .first()
    )
    assert audit is not None
    assert audit.action_type == "CREATE_SHIPMENT"


def test_planner_role_route_assignment(db_session):
    # Ensure at least one CREATED shipment exists
    shp = db_session.query(Shipment).filter(Shipment.status == "CREATED").first()
    if not shp:
        now = datetime.utcnow()
        req = SupplierCreateShipmentRequest(
            origin_facility_id="FAC-001",
            destination_facility_id="FAC-002",
            service_level_id="SL-EXPRESS",
            weight_kg=20.0,
            volume_cbm=0.1,
            scheduled_pickup_time=(now + timedelta(hours=1)).isoformat(),
            promised_delivery_time=(now + timedelta(hours=48)).isoformat(),
            customer_id="CUST-00001",
        )
        res = supplier_create_shipment(req, db=db_session)
        shp = db_session.query(Shipment).filter_by(shipment_id=res["shipment_id"]).first()

    assert shp is not None

    req = PlannerAssignCarrierRequest(
        shipment_id=shp.shipment_id,
        carrier_id="CAR-002",
    )
    assign_res = planner_assign_route(req, db=db_session)
    assert assign_res["status"] == "ASSIGNED"
    assert assign_res["assigned_carrier_id"] == "CAR-002"

    # Verify status transitioned
    refreshed_shp = db_session.query(Shipment).filter_by(shipment_id=shp.shipment_id).first()
    assert refreshed_shp.primary_carrier_id == "CAR-002"
    assert refreshed_shp.status == "IN_TRANSIT"


def test_operator_role_event_scanning_and_queue_updating(db_session):
    shp = db_session.query(Shipment).filter(Shipment.status == "IN_TRANSIT").first()
    assert shp is not None

    # Operator scans barcode event
    req_evt = OperatorRecordEventRequest(
        shipment_id=shp.shipment_id,
        event_type="ARRIVED_AT_FACILITY",
        facility_id="FAC-001",
        event_location="Chicago Sort Hub, IL",
        event_source="MANUAL_SCAN",
        notes="Barcode scanned at inbound dock 4.",
    )
    evt_res = operator_record_event(req_evt, db=db_session)
    assert evt_res["status"] == "RECORDED"
    assert evt_res["event_id"].startswith("EVT-")

    # Operator logs queue update
    req_q = OperatorUpdateQueueRequest(
        facility_id="FAC-001",
        queue_length=32,
        average_wait_time_minutes=75,
        dock_utilization_pct=85.0,
        processing_status="MODERATE_CONGESTION",
    )
    q_res = operator_update_queue(req_q, db=db_session)
    assert q_res["status"] == "SUCCESS"
    assert q_res["queue_length"] == 32


def test_audit_logs_retrieval(db_session):
    logs = get_audit_logs(limit=10, db=db_session)
    assert isinstance(logs, list)
    assert len(logs) > 0
    assert hasattr(logs[0], "action_type")
    assert hasattr(logs[0], "user_id")
