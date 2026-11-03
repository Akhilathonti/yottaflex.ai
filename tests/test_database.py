"""
Database Schema, Constraints, and ORM Integrity Tests
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import (
    Base,
    ServiceLevel,
    Carrier,
    Facility,
    Shipment,
    ShipmentLeg,
    TrackingEvent,
)


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_schema_creation_and_insertion(test_db):
    # Insert Service Level
    sl = ServiceLevel(
        service_level_id="SL-TEST",
        name="Test Service",
        code="TEST",
        target_delivery_hours=24,
        delay_tolerance_minutes=15,
    )
    test_db.add(sl)

    # Insert Carrier
    carrier = Carrier(
        carrier_id="CAR-TEST",
        name="Test Carrier",
        code="TC",
        service_type="GROUND",
        on_time_rating=0.95,
    )
    test_db.add(carrier)

    # Insert Facility
    origin_fac = Facility(
        facility_id="FAC-001",
        name="Origin Hub",
        facility_type="ORIGIN_HUB",
        city="Chicago",
        state="IL",
        latitude=41.8781,
        longitude=-87.6298,
        capacity_daily_shipments=5000,
    )
    dest_fac = Facility(
        facility_id="FAC-002",
        name="Dest Depot",
        facility_type="DESTINATION_DEPOT",
        city="Dallas",
        state="TX",
        latitude=32.7767,
        longitude=-96.7970,
        capacity_daily_shipments=4000,
    )
    test_db.add_all([origin_fac, dest_fac])
    test_db.commit()

    # Query back
    queried_sl = test_db.query(ServiceLevel).filter_by(service_level_id="SL-TEST").first()
    assert queried_sl is not None
    assert queried_sl.target_delivery_hours == 24

    queried_carrier = test_db.query(Carrier).filter_by(carrier_id="CAR-TEST").first()
    assert queried_carrier is not None
    assert queried_carrier.on_time_rating == 0.95
