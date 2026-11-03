-- ============================================================================
-- Intelligent Logistics ETA Prediction and Delay Detection System
-- Production PostgreSQL Relational Database Schema
-- Seed / Benchmark Year: 2026
-- ============================================================================

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing tables in reverse dependency order if recreating
DROP TABLE IF EXISTS alerts CASCADE;
DROP TABLE IF EXISTS shipment_delay_reasons CASCADE;
DROP TABLE IF EXISTS facility_weather_events CASCADE;
DROP TABLE IF EXISTS delay_reasons CASCADE;
DROP TABLE IF EXISTS eta_estimates CASCADE;
DROP TABLE IF EXISTS tracking_events CASCADE;
DROP TABLE IF EXISTS facility_queues CASCADE;
DROP TABLE IF EXISTS weather_events CASCADE;
DROP TABLE IF EXISTS shipment_legs CASCADE;
DROP TABLE IF EXISTS routes CASCADE;
DROP TABLE IF EXISTS shipments CASCADE;
DROP TABLE IF EXISTS facilities CASCADE;
DROP TABLE IF EXISTS carriers CASCADE;
DROP TABLE IF EXISTS service_levels CASCADE;

-- ----------------------------------------------------------------------------
-- 1. Service Level Master Table
-- ----------------------------------------------------------------------------
CREATE TABLE service_levels (
    service_level_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE,
    code VARCHAR(16) NOT NULL UNIQUE,
    target_delivery_hours INTEGER NOT NULL CHECK (target_delivery_hours > 0),
    guaranteed BOOLEAN NOT NULL DEFAULT FALSE,
    delay_tolerance_minutes INTEGER NOT NULL DEFAULT 30 CHECK (delay_tolerance_minutes >= 0),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 2. Carrier Master Table
-- ----------------------------------------------------------------------------
CREATE TABLE carriers (
    carrier_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    code VARCHAR(16) NOT NULL UNIQUE,
    service_type VARCHAR(32) NOT NULL CHECK (service_type IN ('GROUND', 'AIR_EXPRESS', 'FREIGHT', 'HYBRID')),
    contact_email VARCHAR(128),
    on_time_rating NUMERIC(4, 3) NOT NULL DEFAULT 0.900 CHECK (on_time_rating >= 0.0 AND on_time_rating <= 1.0),
    active_fleet_size INTEGER NOT NULL DEFAULT 100 CHECK (active_fleet_size >= 0),
    operating_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (operating_status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 3. Facility Master Table
-- ----------------------------------------------------------------------------
CREATE TABLE facilities (
    facility_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    facility_type VARCHAR(32) NOT NULL CHECK (facility_type IN ('ORIGIN_HUB', 'SORTATION_CENTER', 'DISTRIBUTION_CENTER', 'CROSS_DOCK', 'DESTINATION_DEPOT')),
    city VARCHAR(64) NOT NULL,
    state VARCHAR(32) NOT NULL,
    country VARCHAR(32) NOT NULL DEFAULT 'USA',
    latitude NUMERIC(9, 6) NOT NULL CHECK (latitude >= -90.0 AND latitude <= 90.0),
    longitude NUMERIC(9, 6) NOT NULL CHECK (longitude >= -180.0 AND longitude <= 180.0),
    capacity_daily_shipments INTEGER NOT NULL CHECK (capacity_daily_shipments > 0),
    current_utilization_rate NUMERIC(4, 3) NOT NULL DEFAULT 0.650 CHECK (current_utilization_rate >= 0.0 AND current_utilization_rate <= 2.0),
    operating_hours_start TIME NOT NULL DEFAULT '06:00:00',
    operating_hours_end TIME NOT NULL DEFAULT '22:00:00',
    cutoff_time TIME NOT NULL DEFAULT '18:00:00',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 4. Route Master Table
-- ----------------------------------------------------------------------------
CREATE TABLE routes (
    route_id VARCHAR(32) PRIMARY KEY,
    origin_facility_id VARCHAR(32) NOT NULL REFERENCES facilities(facility_id) ON DELETE RESTRICT,
    destination_facility_id VARCHAR(32) NOT NULL REFERENCES facilities(facility_id) ON DELETE RESTRICT,
    distance_km NUMERIC(8, 2) NOT NULL CHECK (distance_km > 0),
    standard_duration_hours NUMERIC(6, 2) NOT NULL CHECK (standard_duration_hours > 0),
    highway_corridor VARCHAR(64),
    risk_factor NUMERIC(3, 2) NOT NULL DEFAULT 1.00 CHECK (risk_factor >= 0.5 AND risk_factor <= 3.0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_route_distinct_facilities CHECK (origin_facility_id <> destination_facility_id)
);

-- ----------------------------------------------------------------------------
-- 5. Shipment Table
-- ----------------------------------------------------------------------------
CREATE TABLE shipments (
    shipment_id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL,
    customer_id VARCHAR(64) NOT NULL,
    origin_facility_id VARCHAR(32) NOT NULL REFERENCES facilities(facility_id),
    destination_facility_id VARCHAR(32) NOT NULL REFERENCES facilities(facility_id),
    service_level_id VARCHAR(32) NOT NULL REFERENCES service_levels(service_level_id),
    primary_carrier_id VARCHAR(32) NOT NULL REFERENCES carriers(carrier_id),
    status VARCHAR(32) NOT NULL DEFAULT 'CREATED' CHECK (status IN ('CREATED', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'EXCEPTION', 'CANCELLED')),
    weight_kg NUMERIC(8, 2) NOT NULL CHECK (weight_kg > 0),
    volume_cbm NUMERIC(6, 3) NOT NULL CHECK (volume_cbm > 0),
    total_distance_km NUMERIC(8, 2) NOT NULL CHECK (total_distance_km > 0),
    scheduled_pickup_time TIMESTAMP WITH TIME ZONE NOT NULL,
    actual_pickup_time TIMESTAMP WITH TIME ZONE,
    promised_delivery_time TIMESTAMP WITH TIME ZONE NOT NULL,
    actual_delivery_time TIMESTAMP WITH TIME ZONE,
    actual_delay_minutes INTEGER,
    is_delayed BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_shipment_pickup_before_promised CHECK (scheduled_pickup_time < promised_delivery_time)
);

-- ----------------------------------------------------------------------------
-- 6. Shipment Leg Table
-- ----------------------------------------------------------------------------
CREATE TABLE shipment_legs (
    leg_id VARCHAR(64) PRIMARY KEY,
    shipment_id VARCHAR(64) NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    leg_sequence INTEGER NOT NULL CHECK (leg_sequence >= 1),
    route_id VARCHAR(32) REFERENCES routes(route_id),
    carrier_id VARCHAR(32) NOT NULL REFERENCES carriers(carrier_id),
    origin_facility_id VARCHAR(32) NOT NULL REFERENCES facilities(facility_id),
    destination_facility_id VARCHAR(32) NOT NULL REFERENCES facilities(facility_id),
    leg_status VARCHAR(32) NOT NULL DEFAULT 'PENDING' CHECK (leg_status IN ('PENDING', 'IN_TRANSIT', 'COMPLETED', 'CANCELLED')),
    distance_km NUMERIC(8, 2) NOT NULL CHECK (distance_km > 0),
    estimated_transit_hours NUMERIC(6, 2) NOT NULL CHECK (estimated_transit_hours > 0),
    actual_transit_hours NUMERIC(6, 2),
    scheduled_departure TIMESTAMP WITH TIME ZONE NOT NULL,
    actual_departure TIMESTAMP WITH TIME ZONE,
    scheduled_arrival TIMESTAMP WITH TIME ZONE NOT NULL,
    actual_arrival TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_shipment_leg_seq UNIQUE (shipment_id, leg_sequence)
);

-- ----------------------------------------------------------------------------
-- 7. Tracking Event Table
-- ----------------------------------------------------------------------------
CREATE TABLE tracking_events (
    event_id VARCHAR(64) PRIMARY KEY,
    shipment_id VARCHAR(64) NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    leg_id VARCHAR(64) REFERENCES shipment_legs(leg_id) ON DELETE SET NULL,
    facility_id VARCHAR(32) REFERENCES facilities(facility_id) ON DELETE SET NULL,
    event_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    ingestion_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    event_type VARCHAR(32) NOT NULL CHECK (event_type IN (
        'CREATED', 'PICKED_UP', 'ARRIVED_AT_FACILITY', 'SORTING_COMPLETED',
        'DEPARTED_FACILITY', 'IN_TRANSIT_SCAN', 'OUT_FOR_DELIVERY',
        'DELIVERED', 'EXCEPTION', 'WEATHER_HOLD', 'DELIVERY_ATTEMPTED'
    )),
    event_location VARCHAR(128) NOT NULL,
    event_sequence INTEGER NOT NULL CHECK (event_sequence >= 1),
    event_source VARCHAR(32) NOT NULL CHECK (event_source IN ('EDI', 'GPS_TRACKER', 'MOBILE_APP', 'MANUAL_SCAN', 'WMS', 'SIMULATOR')),
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_ingestion_gte_event CHECK (ingestion_timestamp >= event_timestamp)
);

-- ----------------------------------------------------------------------------
-- 8. Facility Queue Observations Table
-- ----------------------------------------------------------------------------
CREATE TABLE facility_queues (
    queue_id VARCHAR(64) PRIMARY KEY,
    facility_id VARCHAR(32) NOT NULL REFERENCES facilities(facility_id) ON DELETE CASCADE,
    observation_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    queue_length INTEGER NOT NULL CHECK (queue_length >= 0),
    average_wait_time_minutes INTEGER NOT NULL CHECK (average_wait_time_minutes >= 0),
    dock_utilization_pct NUMERIC(5, 2) NOT NULL CHECK (dock_utilization_pct >= 0.0 AND dock_utilization_pct <= 100.0),
    processing_status VARCHAR(32) NOT NULL DEFAULT 'NORMAL' CHECK (processing_status IN ('NORMAL', 'MODERATE_CONGESTION', 'SEVERE_CONGESTION')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_facility_observation UNIQUE (facility_id, observation_timestamp)
);

-- ----------------------------------------------------------------------------
-- 9. Weather Event Table
-- ----------------------------------------------------------------------------
CREATE TABLE weather_events (
    weather_event_id VARCHAR(64) PRIMARY KEY,
    event_type VARCHAR(32) NOT NULL CHECK (event_type IN ('SNOW_STORM', 'BLIZZARD', 'HEAVY_RAIN', 'FLOOD', 'FOG', 'HIGH_WINDS', 'TORNADO', 'ICE_STORM')),
    severity VARCHAR(16) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'SEVERE')),
    affected_region VARCHAR(128) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    visibility_miles NUMERIC(4, 1) CHECK (visibility_miles >= 0),
    wind_speed_mph NUMERIC(5, 1) CHECK (wind_speed_mph >= 0),
    precipitation_mm NUMERIC(6, 1) CHECK (precipitation_mm >= 0),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_weather_duration CHECK (end_time > start_time)
);

-- ----------------------------------------------------------------------------
-- 10. Facility Weather Event Bridge Table (N:M)
-- ----------------------------------------------------------------------------
CREATE TABLE facility_weather_events (
    id SERIAL PRIMARY KEY,
    facility_id VARCHAR(32) NOT NULL REFERENCES facilities(facility_id) ON DELETE CASCADE,
    weather_event_id VARCHAR(64) NOT NULL REFERENCES weather_events(weather_event_id) ON DELETE CASCADE,
    impact_level VARCHAR(16) NOT NULL DEFAULT 'MEDIUM' CHECK (impact_level IN ('LOW', 'MEDIUM', 'HIGH', 'SEVERE')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fac_weather UNIQUE (facility_id, weather_event_id)
);

-- ----------------------------------------------------------------------------
-- 11. Delay Reason Master Table
-- ----------------------------------------------------------------------------
CREATE TABLE delay_reasons (
    reason_id VARCHAR(32) PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    category VARCHAR(32) NOT NULL CHECK (category IN ('ENVIRONMENTAL', 'OPERATIONAL', 'CARRIER', 'DATA_QUALITY', 'OTHER')),
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 12. ETA Estimates History Table
-- ----------------------------------------------------------------------------
CREATE TABLE eta_estimates (
    estimate_id VARCHAR(64) PRIMARY KEY,
    shipment_id VARCHAR(64) NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    prediction_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    predicted_eta TIMESTAMP WITH TIME ZONE NOT NULL,
    predicted_remaining_transit_minutes NUMERIC(8, 2) NOT NULL CHECK (predicted_remaining_transit_minutes >= 0),
    delay_probability NUMERIC(4, 3) NOT NULL CHECK (delay_probability >= 0.0 AND delay_probability <= 1.0),
    model_version VARCHAR(32) NOT NULL,
    model_name VARCHAR(64) NOT NULL,
    confidence_lower_bound TIMESTAMP WITH TIME ZONE,
    confidence_upper_bound TIMESTAMP WITH TIME ZONE,
    primary_delay_reason VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 13. Shipment Delay Reason Association Table (N:M)
-- ----------------------------------------------------------------------------
CREATE TABLE shipment_delay_reasons (
    id SERIAL PRIMARY KEY,
    shipment_id VARCHAR(64) NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    reason_id VARCHAR(32) NOT NULL REFERENCES delay_reasons(reason_id) ON DELETE RESTRICT,
    attribution_score NUMERIC(4, 3) NOT NULL DEFAULT 1.000 CHECK (attribution_score >= 0.0 AND attribution_score <= 1.0),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_ground_truth BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_shipment_delay_reason UNIQUE (shipment_id, reason_id, is_ground_truth)
);

-- ----------------------------------------------------------------------------
-- 14. Operational Alerts Table
-- ----------------------------------------------------------------------------
CREATE TABLE alerts (
    alert_id VARCHAR(64) PRIMARY KEY,
    shipment_id VARCHAR(64) NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    prediction_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    predicted_eta TIMESTAMP WITH TIME ZONE NOT NULL,
    promised_delivery_time TIMESTAMP WITH TIME ZONE NOT NULL,
    predicted_delay_minutes INTEGER NOT NULL,
    delay_probability NUMERIC(4, 3) NOT NULL,
    delay_reason VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    recommended_action TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 15. User Authentication & Role Master Table
-- ----------------------------------------------------------------------------
CREATE TABLE users (
    user_id VARCHAR(32) PRIMARY KEY,
    full_name VARCHAR(128) NOT NULL,
    email VARCHAR(128) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(32) NOT NULL CHECK (role IN ('SUPPLIER', 'LOGISTICS_PLANNER', 'CARRIER_OPERATOR', 'LOGISTICS_ANALYST', 'OPERATIONS_MANAGER')),
    customer_id VARCHAR(64),
    carrier_id VARCHAR(32) REFERENCES carriers(carrier_id) ON DELETE SET NULL,
    facility_id VARCHAR(32) REFERENCES facilities(facility_id) ON DELETE SET NULL,
    account_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (account_status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE
);

-- ----------------------------------------------------------------------------
-- 16. User Activity & Operational Audit Log Table
-- ----------------------------------------------------------------------------
CREATE TABLE audit_records (
    audit_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    action_type VARCHAR(64) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    entity_id VARCHAR(64) NOT NULL,
    previous_value TEXT,
    new_value TEXT,
    action_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    action_description TEXT NOT NULL
);

-- ============================================================================
-- Indexes for High Performance Logistics Analytics and Point-in-time Queries
-- ============================================================================
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_carrier ON shipments(primary_carrier_id);
CREATE INDEX idx_shipments_origin_dest ON shipments(origin_facility_id, destination_facility_id);
CREATE INDEX idx_shipments_promised ON shipments(promised_delivery_time);
CREATE INDEX idx_shipments_is_delayed ON shipments(is_delayed);

CREATE INDEX idx_legs_shipment_seq ON shipment_legs(shipment_id, leg_sequence);
CREATE INDEX idx_legs_carrier ON shipment_legs(carrier_id);
CREATE INDEX idx_legs_status ON shipment_legs(leg_status);

CREATE INDEX idx_events_shipment_seq ON tracking_events(shipment_id, event_sequence);
CREATE INDEX idx_events_event_time ON tracking_events(event_timestamp);
CREATE INDEX idx_events_ingestion_time ON tracking_events(ingestion_timestamp);
CREATE INDEX idx_events_facility ON tracking_events(facility_id);
CREATE INDEX idx_events_type ON tracking_events(event_type);

CREATE INDEX idx_queues_facility_time ON facility_queues(facility_id, observation_timestamp);
CREATE INDEX idx_weather_time ON weather_events(start_time, end_time);
CREATE INDEX idx_weather_severity ON weather_events(severity);

CREATE INDEX idx_eta_shipment_pred_time ON eta_estimates(shipment_id, prediction_timestamp);
CREATE INDEX idx_alerts_shipment_status ON alerts(shipment_id, status);
CREATE INDEX idx_alerts_severity ON alerts(severity);
