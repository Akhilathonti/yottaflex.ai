"""
SQLAlchemy ORM Models for Logistics ETA Prediction and Delay Detection System
Full compatibility with PostgreSQL and SQLite.
"""
from datetime import datetime, time
from typing import Optional, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Time,
    ForeignKey,
    Text,
    Index,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ServiceLevel(Base):
    __tablename__ = "service_levels"

    service_level_id = Column(String(32), primary_key=True)
    name = Column(String(64), nullable=False, unique=True)
    code = Column(String(16), nullable=False, unique=True)
    target_delivery_hours = Column(Integer, nullable=False)
    guaranteed = Column(Boolean, nullable=False, default=False)
    delay_tolerance_minutes = Column(Integer, nullable=False, default=30)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    shipments = relationship("Shipment", back_populates="service_level")


class Carrier(Base):
    __tablename__ = "carriers"

    carrier_id = Column(String(32), primary_key=True)
    name = Column(String(128), nullable=False)
    code = Column(String(16), nullable=False, unique=True)
    service_type = Column(String(32), nullable=False)  # GROUND, AIR_EXPRESS, FREIGHT, HYBRID
    contact_email = Column(String(128), nullable=True)
    on_time_rating = Column(Float, nullable=False, default=0.90)
    active_fleet_size = Column(Integer, nullable=False, default=100)
    operating_status = Column(String(16), nullable=False, default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    shipments = relationship("Shipment", back_populates="carrier")
    legs = relationship("ShipmentLeg", back_populates="carrier")


class Facility(Base):
    __tablename__ = "facilities"

    facility_id = Column(String(32), primary_key=True)
    name = Column(String(128), nullable=False)
    facility_type = Column(String(32), nullable=False)
    city = Column(String(64), nullable=False)
    state = Column(String(32), nullable=False)
    country = Column(String(32), nullable=False, default="USA")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    capacity_daily_shipments = Column(Integer, nullable=False)
    current_utilization_rate = Column(Float, nullable=False, default=0.65)
    operating_hours_start = Column(Time, nullable=False, default=time(6, 0))
    operating_hours_end = Column(Time, nullable=False, default=time(22, 0))
    cutoff_time = Column(Time, nullable=False, default=time(18, 0))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    queues = relationship("FacilityQueue", back_populates="facility", cascade="all, delete-orphan")
    tracking_events = relationship("TrackingEvent", back_populates="facility")
    weather_associations = relationship("FacilityWeatherEvent", back_populates="facility", cascade="all, delete-orphan")


class Route(Base):
    __tablename__ = "routes"

    route_id = Column(String(32), primary_key=True)
    origin_facility_id = Column(String(32), ForeignKey("facilities.facility_id"), nullable=False)
    destination_facility_id = Column(String(32), ForeignKey("facilities.facility_id"), nullable=False)
    distance_km = Column(Float, nullable=False)
    standard_duration_hours = Column(Float, nullable=False)
    highway_corridor = Column(String(64), nullable=True)
    risk_factor = Column(Float, nullable=False, default=1.0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    origin_facility = relationship("Facility", foreign_keys=[origin_facility_id])
    destination_facility = relationship("Facility", foreign_keys=[destination_facility_id])
    legs = relationship("ShipmentLeg", back_populates="route")


class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id = Column(String(64), primary_key=True)
    order_id = Column(String(64), nullable=False)
    customer_id = Column(String(64), nullable=False)
    origin_facility_id = Column(String(32), ForeignKey("facilities.facility_id"), nullable=False)
    destination_facility_id = Column(String(32), ForeignKey("facilities.facility_id"), nullable=False)
    service_level_id = Column(String(32), ForeignKey("service_levels.service_level_id"), nullable=False)
    primary_carrier_id = Column(String(32), ForeignKey("carriers.carrier_id"), nullable=False)
    status = Column(String(32), nullable=False, default="CREATED")
    weight_kg = Column(Float, nullable=False)
    volume_cbm = Column(Float, nullable=False)
    total_distance_km = Column(Float, nullable=False)
    scheduled_pickup_time = Column(DateTime, nullable=False)
    actual_pickup_time = Column(DateTime, nullable=True)
    promised_delivery_time = Column(DateTime, nullable=False)
    actual_delivery_time = Column(DateTime, nullable=True)
    actual_delay_minutes = Column(Integer, nullable=True)
    is_delayed = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    origin_facility = relationship("Facility", foreign_keys=[origin_facility_id])
    destination_facility = relationship("Facility", foreign_keys=[destination_facility_id])
    service_level = relationship("ServiceLevel", back_populates="shipments")
    carrier = relationship("Carrier", back_populates="shipments")
    legs = relationship("ShipmentLeg", back_populates="shipment", cascade="all, delete-orphan", order_by="ShipmentLeg.leg_sequence")
    tracking_events = relationship("TrackingEvent", back_populates="shipment", cascade="all, delete-orphan", order_by="TrackingEvent.event_sequence")
    eta_estimates = relationship("ETAEstimate", back_populates="shipment", cascade="all, delete-orphan")
    delay_reasons = relationship("ShipmentDelayReason", back_populates="shipment", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="shipment", cascade="all, delete-orphan")


class ShipmentLeg(Base):
    __tablename__ = "shipment_legs"

    leg_id = Column(String(64), primary_key=True)
    shipment_id = Column(String(64), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False)
    leg_sequence = Column(Integer, nullable=False)
    route_id = Column(String(32), ForeignKey("routes.route_id"), nullable=True)
    carrier_id = Column(String(32), ForeignKey("carriers.carrier_id"), nullable=False)
    origin_facility_id = Column(String(32), ForeignKey("facilities.facility_id"), nullable=False)
    destination_facility_id = Column(String(32), ForeignKey("facilities.facility_id"), nullable=False)
    leg_status = Column(String(32), nullable=False, default="PENDING")
    distance_km = Column(Float, nullable=False)
    estimated_transit_hours = Column(Float, nullable=False)
    actual_transit_hours = Column(Float, nullable=True)
    scheduled_departure = Column(DateTime, nullable=False)
    actual_departure = Column(DateTime, nullable=True)
    scheduled_arrival = Column(DateTime, nullable=False)
    actual_arrival = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    shipment = relationship("Shipment", back_populates="legs")
    route = relationship("Route", back_populates="legs")
    carrier = relationship("Carrier", back_populates="legs")
    origin_facility = relationship("Facility", foreign_keys=[origin_facility_id])
    destination_facility = relationship("Facility", foreign_keys=[destination_facility_id])
    tracking_events = relationship("TrackingEvent", back_populates="leg")

    __table_args__ = (
        UniqueConstraint("shipment_id", "leg_sequence", name="uq_shipment_leg_seq"),
    )


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    event_id = Column(String(64), primary_key=True)
    shipment_id = Column(String(64), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False)
    leg_id = Column(String(64), ForeignKey("shipment_legs.leg_id", ondelete="SET NULL"), nullable=True)
    facility_id = Column(String(32), ForeignKey("facilities.facility_id", ondelete="SET NULL"), nullable=True)
    event_timestamp = Column(DateTime, nullable=False)
    ingestion_timestamp = Column(DateTime, nullable=False)
    event_type = Column(String(32), nullable=False)
    event_location = Column(String(128), nullable=False)
    event_sequence = Column(Integer, nullable=False)
    event_source = Column(String(32), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    shipment = relationship("Shipment", back_populates="tracking_events")
    leg = relationship("ShipmentLeg", back_populates="tracking_events")
    facility = relationship("Facility", back_populates="tracking_events")

    __table_args__ = (
        Index("idx_tracking_events_shipment_seq", "shipment_id", "event_sequence"),
        Index("idx_tracking_events_event_time", "event_timestamp"),
        Index("idx_tracking_events_ingestion_time", "ingestion_timestamp"),
    )


class FacilityQueue(Base):
    __tablename__ = "facility_queues"

    queue_id = Column(String(64), primary_key=True)
    facility_id = Column(String(32), ForeignKey("facilities.facility_id", ondelete="CASCADE"), nullable=False)
    observation_timestamp = Column(DateTime, nullable=False)
    queue_length = Column(Integer, nullable=False)
    average_wait_time_minutes = Column(Integer, nullable=False)
    dock_utilization_pct = Column(Float, nullable=False)
    processing_status = Column(String(32), nullable=False, default="NORMAL")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    facility = relationship("Facility", back_populates="queues")

    __table_args__ = (
        UniqueConstraint("facility_id", "observation_timestamp", name="uq_facility_observation"),
        Index("idx_queues_facility_time", "facility_id", "observation_timestamp"),
    )


class WeatherEvent(Base):
    __tablename__ = "weather_events"

    weather_event_id = Column(String(64), primary_key=True)
    event_type = Column(String(32), nullable=False)
    severity = Column(String(16), nullable=False)
    affected_region = Column(String(128), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    visibility_miles = Column(Float, nullable=True)
    wind_speed_mph = Column(Float, nullable=True)
    precipitation_mm = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    facility_associations = relationship("FacilityWeatherEvent", back_populates="weather_event", cascade="all, delete-orphan")


class FacilityWeatherEvent(Base):
    __tablename__ = "facility_weather_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    facility_id = Column(String(32), ForeignKey("facilities.facility_id", ondelete="CASCADE"), nullable=False)
    weather_event_id = Column(String(64), ForeignKey("weather_events.weather_event_id", ondelete="CASCADE"), nullable=False)
    impact_level = Column(String(16), nullable=False, default="MEDIUM")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    facility = relationship("Facility", back_populates="weather_associations")
    weather_event = relationship("WeatherEvent", back_populates="facility_associations")

    __table_args__ = (
        UniqueConstraint("facility_id", "weather_event_id", name="uq_fac_weather"),
    )


class DelayReason(Base):
    __tablename__ = "delay_reasons"

    reason_id = Column(String(32), primary_key=True)
    code = Column(String(32), nullable=False, unique=True)
    category = Column(String(32), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    shipment_associations = relationship("ShipmentDelayReason", back_populates="delay_reason")


class ShipmentDelayReason(Base):
    __tablename__ = "shipment_delay_reasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shipment_id = Column(String(64), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False)
    reason_id = Column(String(32), ForeignKey("delay_reasons.reason_id"), nullable=False)
    attribution_score = Column(Float, nullable=False, default=1.0)
    is_primary = Column(Boolean, nullable=False, default=False)
    is_ground_truth = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    shipment = relationship("Shipment", back_populates="delay_reasons")
    delay_reason = relationship("DelayReason", back_populates="shipment_associations")

    __table_args__ = (
        UniqueConstraint("shipment_id", "reason_id", "is_ground_truth", name="uq_shipment_delay_reason"),
    )


class ETAEstimate(Base):
    __tablename__ = "eta_estimates"

    estimate_id = Column(String(64), primary_key=True)
    shipment_id = Column(String(64), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False)
    prediction_timestamp = Column(DateTime, nullable=False)
    predicted_eta = Column(DateTime, nullable=False)
    predicted_remaining_transit_minutes = Column(Float, nullable=False)
    delay_probability = Column(Float, nullable=False)
    model_version = Column(String(32), nullable=False)
    model_name = Column(String(64), nullable=False)
    confidence_lower_bound = Column(DateTime, nullable=True)
    confidence_upper_bound = Column(DateTime, nullable=True)
    primary_delay_reason = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    shipment = relationship("Shipment", back_populates="eta_estimates")

    __table_args__ = (
        Index("idx_eta_shipment_pred_time", "shipment_id", "prediction_timestamp"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String(64), primary_key=True)
    shipment_id = Column(String(64), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False)
    prediction_timestamp = Column(DateTime, nullable=False)
    predicted_eta = Column(DateTime, nullable=False)
    promised_delivery_time = Column(DateTime, nullable=False)
    predicted_delay_minutes = Column(Integer, nullable=False)
    delay_probability = Column(Float, nullable=False)
    delay_reason = Column(String(64), nullable=False)
    severity = Column(String(16), nullable=False)
    recommended_action = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    shipment = relationship("Shipment", back_populates="alerts")

    __table_args__ = (
        Index("idx_alerts_shipment_status", "shipment_id", "status"),
        Index("idx_alerts_severity", "severity"),
    )


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(32), primary_key=True)
    full_name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=False, unique=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False)  # SUPPLIER, LOGISTICS_PLANNER, CARRIER_OPERATOR, LOGISTICS_ANALYST, OPERATIONS_MANAGER
    customer_id = Column(String(64), nullable=True)  # For SUPPLIER scoping
    carrier_id = Column(String(32), ForeignKey("carriers.carrier_id", ondelete="SET NULL"), nullable=True)
    facility_id = Column(String(32), ForeignKey("facilities.facility_id", ondelete="SET NULL"), nullable=True)
    account_status = Column(String(16), nullable=False, default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    audit_records = relationship("AuditRecord", back_populates="user", cascade="all, delete-orphan")


class AuditRecord(Base):
    __tablename__ = "audit_records"

    audit_id = Column(String(64), primary_key=True)
    user_id = Column(String(32), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String(64), nullable=False)  # CREATE_SHIPMENT, ASSIGN_CARRIER, RECORD_EVENT, UPDATE_QUEUE, etc.
    entity_type = Column(String(32), nullable=False)  # SHIPMENT, SHIPMENT_LEG, TRACKING_EVENT, FACILITY_QUEUE, ALERT, etc.
    entity_id = Column(String(64), nullable=False)
    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    action_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    action_description = Column(Text, nullable=False)

    user = relationship("User", back_populates="audit_records")

    __table_args__ = (
        Index("idx_audit_user_action", "user_id", "action_timestamp"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
    )

