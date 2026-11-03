# Logistics ETA Prediction & Delay Detection Data Dictionary

## Overview
This document specifies the data model, entity structures, field types, validation rules, constraints, and operational lifecycle states for the Intelligent Logistics ETA Prediction and Delay Detection System.

---

## 1. `service_levels` (Master Table)
Defines customer contract service tiers, transit time commitments, and SLA delay tolerance thresholds.

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `service_level_id` | VARCHAR(32) | NO | PK | Deterministic identifier (e.g. `SL-OVERNIGHT`, `SL-EXPRESS`, `SL-STANDARD`, `SL-ECONOMY`) |
| `name` | VARCHAR(64) | NO | None | Unique descriptive name (e.g. `Next-Day Air Priority`) |
| `code` | VARCHAR(16) | NO | None | Unique short code (`OVERNIGHT`, `EXPRESS`, `STANDARD`, `ECONOMY`) |
| `target_delivery_hours` | INTEGER | NO | None | Contractual delivery window from pickup (e.g., 24, 48, 72, 120 hrs). Must be > 0. |
| `guaranteed` | BOOLEAN | NO | None | Whether the SLA includes a money-back refund guarantee |
| `delay_tolerance_minutes`| INTEGER | NO | None | Buffer before contractual SLA breach penalty triggers (e.g. 15, 30, 60 mins). Must be >= 0. |
| `description` | TEXT | YES | None | Detailed service level agreement specifications |
| `created_at` | TIMESTAMPTZ | NO | None | Record creation timestamp |

---

## 2. `carriers` (Master Table)
Fleet operators and logistics transport partners performing shipment leg transit.

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `carrier_id` | VARCHAR(32) | NO | PK | Format: `CAR-001`, `CAR-002`, etc. |
| `name` | VARCHAR(128) | NO | None | Operating carrier name (e.g. `Apex Freight Systems`) |
| `code` | VARCHAR(16) | NO | None | Unique carrier IATA/SCAC code (`APEX`, `SWFT`, `BLAZ`, etc.) |
| `service_type` | VARCHAR(32) | NO | None | Enum: `GROUND`, `AIR_EXPRESS`, `FREIGHT`, `HYBRID` |
| `contact_email` | VARCHAR(128) | YES | None | Operations dispatch email |
| `on_time_rating` | NUMERIC(4,3)| NO | None | Historical baseline reliability rating [0.000 to 1.000] |
| `active_fleet_size` | INTEGER | NO | None | Current active linehaul vehicles/planes. Must be >= 0. |
| `operating_status` | VARCHAR(16) | NO | None | Enum: `ACTIVE`, `INACTIVE`, `SUSPENDED` |
| `created_at` | TIMESTAMPTZ | NO | None | Record creation timestamp |

---

## 3. `facilities` (Master Table)
Logistics nodes including origin hubs, sortation centers, distribution centers, cross-docks, and destination delivery depots.

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `facility_id` | VARCHAR(32) | NO | PK | Format: `FAC-001` through `FAC-100` |
| `name` | VARCHAR(128) | NO | None | Facility name (e.g. `Chicago Central Sortation Hub`) |
| `facility_type` | VARCHAR(32) | NO | None | Enum: `ORIGIN_HUB`, `SORTATION_CENTER`, `DISTRIBUTION_CENTER`, `CROSS_DOCK`, `DESTINATION_DEPOT` |
| `city` | VARCHAR(64) | NO | None | City name |
| `state` | VARCHAR(32) | NO | None | State code (e.g. `IL`, `OH`, `TX`, `CA`) |
| `country` | VARCHAR(32) | NO | None | Country code (Default: `USA`) |
| `latitude` | NUMERIC(9,6)| NO | None | Geographical latitude [-90.000000 to 90.000000] |
| `longitude` | NUMERIC(9,6)| NO | None | Geographical longitude [-180.000000 to 180.000000] |
| `capacity_daily_shipments`| INTEGER| NO | None | Peak sort capacity per 24h window. Must be > 0. |
| `current_utilization_rate`| NUMERIC(4,3)| NO| None | Utilization ratio [0.000 to 2.000] (>1.0 indicates backlogged queue) |
| `operating_hours_start` | TIME | NO | None | Daily shift start (Default: `06:00:00`) |
| `operating_hours_end` | TIME | NO | None | Daily shift end (Default: `22:00:00`) |
| `cutoff_time` | TIME | NO | None | Outbound linehaul cutoff (Default: `18:00:00`) |
| `is_active` | BOOLEAN | NO | None | Active operational state |
| `created_at` | TIMESTAMPTZ | NO | None | Record creation timestamp |

---

## 4. `routes` (Master Table)
Pre-defined transportation lanes connecting two distinct facilities.

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `route_id` | VARCHAR(32) | NO | PK | Format: `RT-0001` |
| `origin_facility_id` | VARCHAR(32) | NO | FK -> `facilities.facility_id` | Lane origin facility |
| `destination_facility_id`| VARCHAR(32)| NO | FK -> `facilities.facility_id` | Lane destination facility (origin != destination) |
| `distance_km` | NUMERIC(8,2)| NO | None | True geodesic/road distance in kilometers (> 0) |
| `standard_duration_hours`| NUMERIC(6,2)| NO | None | Baseline transit time under nominal speed limits (> 0) |
| `highway_corridor` | VARCHAR(64) | YES | None | Primary highway corridor (e.g. `I-80 W`, `I-95 S`) |
| `risk_factor` | NUMERIC(3,2)| NO | None | Historical volatility/congestion multiplier [0.50 to 3.00] |
| `is_active` | BOOLEAN | NO | None | Route status |
| `created_at` | TIMESTAMPTZ | NO | None | Record creation timestamp |

---

## 5. `shipments` (Core Entity)
End-to-end package transport order moving from origin to destination across 1 or more legs.

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `shipment_id` | VARCHAR(64) | NO | PK | Format: `SHP-2026-000001` |
| `order_id` | VARCHAR(64) | NO | None | Customer order reference: `ORD-2026-XXXXXX` |
| `customer_id` | VARCHAR(64) | NO | None | Customer account reference: `CUST-XXXXXX` |
| `origin_facility_id` | VARCHAR(32) | NO | FK -> `facilities.facility_id` | First pickup / hub facility |
| `destination_facility_id`| VARCHAR(32)| NO | FK -> `facilities.facility_id` | Final delivery depot facility |
| `service_level_id` | VARCHAR(32) | NO | FK -> `service_levels.service_level_id` | SLA commitment tier |
| `primary_carrier_id`| VARCHAR(32) | NO | FK -> `carriers.carrier_id` | Primary contracted carrier |
| `status` | VARCHAR(32) | NO | None | Enum: `CREATED`, `IN_TRANSIT`, `OUT_FOR_DELIVERY`, `DELIVERED`, `EXCEPTION`, `CANCELLED` |
| `weight_kg` | NUMERIC(8,2)| NO | None | Gross weight in kg (> 0) |
| `volume_cbm` | NUMERIC(6,3)| NO | None | Cubic meters volume (> 0) |
| `total_distance_km` | NUMERIC(8,2)| NO | None | Total route distance (> 0) |
| `scheduled_pickup_time`| TIMESTAMPTZ| NO | None | Scheduled origin pickup timestamp |
| `actual_pickup_time`| TIMESTAMPTZ | YES| None | Actual origin dispatch timestamp |
| `promised_delivery_time`| TIMESTAMPTZ| NO| None | Contractual delivery deadline (`scheduled_pickup + SLA`) |
| `actual_delivery_time`| TIMESTAMPTZ | YES| None | Actual delivery scan timestamp (NULL if in transit) |
| `actual_delay_minutes`| INTEGER | YES| None | `(actual_delivery_time - promised_delivery_time)` in minutes |
| `is_delayed` | BOOLEAN | YES| None | Ground-truth flag: `TRUE` if `actual_delay_minutes > 0` |
| `created_at` | TIMESTAMPTZ | NO | None | Record ingestion timestamp |
| `updated_at` | TIMESTAMPTZ | NO | None | Record update timestamp |

---

## 6. `shipment_legs` (Child Entity)
Individual segments of a multi-leg journey (e.g. Origin -> Sort Hub -> Dest Depot).

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `leg_id` | VARCHAR(64) | NO | PK | Format: `LEG-SHP-2026-000001-01` |
| `shipment_id` | VARCHAR(64) | NO | FK -> `shipments.shipment_id` | Parent shipment identifier |
| `leg_sequence` | INTEGER | NO | None | 1-indexed leg sequence (1, 2, 3...) |
| `route_id` | VARCHAR(32) | YES| FK -> `routes.route_id` | Associated lane route |
| `carrier_id` | VARCHAR(32) | NO | FK -> `carriers.carrier_id` | Carrier assigned to this leg |
| `origin_facility_id` | VARCHAR(32) | NO | FK -> `facilities.facility_id` | Leg origin |
| `destination_facility_id`| VARCHAR(32)| NO | FK -> `facilities.facility_id` | Leg destination |
| `leg_status` | VARCHAR(32) | NO | None | Enum: `PENDING`, `IN_TRANSIT`, `COMPLETED`, `CANCELLED` |
| `distance_km` | NUMERIC(8,2)| NO | None | Segment road/flight distance |
| `estimated_transit_hours`| NUMERIC(6,2)| NO| None | Planned transit duration |
| `actual_transit_hours`| NUMERIC(6,2)| YES| None | Actual elapsed hours |
| `scheduled_departure`| TIMESTAMPTZ | NO | None | Planned departure |
| `actual_departure` | TIMESTAMPTZ | YES| None | Actual departure timestamp |
| `scheduled_arrival` | TIMESTAMPTZ | NO | None | Planned arrival |
| `actual_arrival` | TIMESTAMPTZ | YES| None | Actual arrival timestamp |
| `created_at` | TIMESTAMPTZ | NO | None | Record creation timestamp |

---

## 7. `tracking_events` (Audit & Telemetry Stream)
Physical or digital telemetry scans for shipments.

> [!IMPORTANT]
> **Data Leakage & Timing Rule**:
> - `event_timestamp`: Time the physical event occurred in the real world.
> - `ingestion_timestamp`: Time the event record was processed into the system.
> - **Invariant**: `ingestion_timestamp >= event_timestamp`. Predictions made at time $T$ may **only** see events where `ingestion_timestamp <= T`.

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `event_id` | VARCHAR(64) | NO | PK | Format: `EVT-SHP-2026-000001-000001` |
| `shipment_id` | VARCHAR(64) | NO | FK -> `shipments.shipment_id` | Parent shipment |
| `leg_id` | VARCHAR(64) | YES| FK -> `shipment_legs.leg_id` | Optional leg reference |
| `facility_id` | VARCHAR(32) | YES| FK -> `facilities.facility_id` | Scanned facility (if at hub/depot) |
| `event_timestamp` | TIMESTAMPTZ | NO | None | Physical scan timestamp |
| `ingestion_timestamp` | TIMESTAMPTZ | NO | None | System intake timestamp (ingestion >= event) |
| `event_type` | VARCHAR(32) | NO | None | Enum: `CREATED`, `PICKED_UP`, `ARRIVED_AT_FACILITY`, `SORTING_COMPLETED`, `DEPARTED_FACILITY`, `IN_TRANSIT_SCAN`, `OUT_FOR_DELIVERY`, `DELIVERED`, `EXCEPTION`, `WEATHER_HOLD`, `DELIVERY_ATTEMPTED` |
| `event_location` | VARCHAR(128)| NO | None | Location text (e.g. `Chicago Hub, IL`) |
| `event_sequence` | INTEGER | NO | None | 1-indexed sequential order of events for the shipment |
| `event_source` | VARCHAR(32) | NO | None | Enum: `EDI`, `GPS_TRACKER`, `MOBILE_APP`, `MANUAL_SCAN`, `WMS`, `SIMULATOR` |
| `latitude` | NUMERIC(9,6)| YES| None | GPS latitude at scan |
| `longitude` | NUMERIC(9,6)| YES| None | GPS longitude at scan |
| `notes` | TEXT | YES| None | Operational scan comments |
| `created_at` | TIMESTAMPTZ | NO | None | Table row insertion time |

---

## 8. `facility_queues` (Time Series Sensor Data)
Periodic snapshots of congestion, dock utilization, and processing backlogs at facilities.

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `queue_id` | VARCHAR(64) | NO | PK | Format: `QUE-FAC-001-20261102T080000` |
| `facility_id` | VARCHAR(32) | NO | FK -> `facilities.facility_id` | Facility reference |
| `observation_timestamp`| TIMESTAMPTZ| NO| None | Timestamp of queue reading |
| `queue_length` | INTEGER | NO | None | Number of trailers/shipments waiting. >= 0. |
| `average_wait_time_minutes`| INTEGER| NO | None | Average dock unloading wait time in minutes |
| `dock_utilization_pct` | NUMERIC(5,2)| NO | None | Percentage of active docks in use [0.00 to 100.00] |
| `processing_status` | VARCHAR(32) | NO | None | Enum: `NORMAL`, `MODERATE_CONGESTION`, `SEVERE_CONGESTION` |
| `created_at` | TIMESTAMPTZ | NO | None | Observation ingestion time |

---

## 9. `weather_events` (Disruption Windows)
Meteorological events causing transit speed reductions or facility shutdowns.

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `weather_event_id` | VARCHAR(64) | NO | PK | Format: `WTH-2026-0001` |
| `event_type` | VARCHAR(32) | NO | None | Enum: `SNOW_STORM`, `BLIZZARD`, `HEAVY_RAIN`, `FLOOD`, `FOG`, `HIGH_WINDS`, `TORNADO`, `ICE_STORM` |
| `severity` | VARCHAR(16) | NO | None | Enum: `LOW`, `MEDIUM`, `HIGH`, `SEVERE` |
| `affected_region` | VARCHAR(128)| NO | None | Region description (e.g. `Midwest Corridor - IL/IN/OH`) |
| `start_time` | TIMESTAMPTZ | NO | None | Disruption start timestamp |
| `end_time` | TIMESTAMPTZ | NO | None | Disruption end timestamp (`end_time > start_time`) |
| `visibility_miles` | NUMERIC(4,1)| YES| None | Visibility in miles (e.g. 0.5) |
| `wind_speed_mph` | NUMERIC(5,1)| YES| None | Sustained wind speed in mph |
| `precipitation_mm` | NUMERIC(6,1)| YES| None | Total precipitation in mm |
| `created_at` | TIMESTAMPTZ | NO | None | Record creation timestamp |

---

## 10. `facility_weather_events` (Bridge Table N:M)
Associates weather disruption events with affected facilities.

| Field Name | Type | Nullable | Primary/Foreign Key | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | SERIAL / INT| NO | PK | Auto-incrementing identifier |
| `facility_id` | VARCHAR(32) | NO | FK -> `facilities.facility_id` | Impacted facility |
| `weather_event_id` | VARCHAR(64) | NO | FK -> `weather_events.weather_event_id` | Weather disruption |
| `impact_level` | VARCHAR(16) | NO | None | Enum: `LOW`, `MEDIUM`, `HIGH`, `SEVERE` |
| `created_at` | TIMESTAMPTZ | NO | None | Association creation timestamp |

---

## 11. `delay_reasons` (Taxonomy Master)
Standardized delay category and reason classification codes.

| Field Name | Type | Nullable | Primary/Foreign Key | Description |
| :--- | :--- | :--- | :--- | :--- |
| `reason_id` | VARCHAR(32) | NO | PK | Format: `RZN-001` through `RZN-008` |
| `code` | VARCHAR(32) | NO | Unique | Unique code: `WEATHER_DISRUPTION`, `FACILITY_CONGESTION`, `CARRIER_PERFORMANCE`, `ROUTE_DEVIATION`, `DELAYED_SCANS`, `MISSED_FACILITY_CUTOFF`, `OPERATIONAL_HANDLING_DELAY`, `UNKNOWN` |
| `category` | VARCHAR(32) | NO | None | Enum: `ENVIRONMENTAL`, `OPERATIONAL`, `CARRIER`, `DATA_QUALITY`, `OTHER` |
| `description` | TEXT | NO | None | Formal business definition of the delay cause |
| `created_at` | TIMESTAMPTZ | NO | None | Record creation timestamp |

---

## 12. `eta_estimates` (Prediction Snapshots)
Auditable point-in-time ETA predictions generated by the ML model.

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `estimate_id` | VARCHAR(64) | NO | PK | Format: `ETA-SHP-2026-000001-20261102T120000` |
| `shipment_id` | VARCHAR(64) | NO | FK -> `shipments.shipment_id` | Target shipment |
| `prediction_timestamp` | TIMESTAMPTZ | NO | None | Time T at which inference was executed |
| `predicted_eta` | TIMESTAMPTZ | NO | None | `prediction_timestamp + predicted_remaining_transit_minutes` |
| `predicted_remaining_transit_minutes` | NUMERIC(8,2)| NO | None | ML regression prediction for remaining minutes |
| `delay_probability` | NUMERIC(4,3)| NO | None | ML classification probability of missing promised deadline [0.000 to 1.000] |
| `model_version` | VARCHAR(32) | NO | None | Model version tag (e.g. `v1.0.0-lgbm`) |
| `model_name` | VARCHAR(64) | NO | None | Algorithm name (e.g. `HistGradientBoostingRegressor`) |
| `confidence_lower_bound`| TIMESTAMPTZ| YES| None | 90% confidence interval lower bound |
| `confidence_upper_bound`| TIMESTAMPTZ| YES| None | 90% confidence interval upper bound |
| `primary_delay_reason` | VARCHAR(64) | YES| None | Machine-explained primary risk factor |
| `created_at` | TIMESTAMPTZ | NO | None | Log insertion timestamp |

---

## 13. `shipment_delay_reasons` (Bridge Table N:M)
Connects shipments to one or more delay reasons with attribution weights, separating ground-truth delay reasons from predicted delay reasons.

| Field Name | Type | Nullable | Primary/Foreign Key | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | SERIAL / INT| NO | PK | Auto-incrementing identifier |
| `shipment_id` | VARCHAR(64) | NO | FK -> `shipments.shipment_id` | Target shipment |
| `reason_id` | VARCHAR(32) | NO | FK -> `delay_reasons.reason_id` | Assigned delay reason |
| `attribution_score` | NUMERIC(4,3)| NO | None | Weight of this reason in overall delay [0.000 to 1.000] |
| `is_primary` | BOOLEAN | NO | None | Whether this is the dominant factor |
| `is_ground_truth` | BOOLEAN | NO | None | `TRUE` if actual post-delivery ground truth; `FALSE` if ML prediction |
| `created_at` | TIMESTAMPTZ | NO | None | Record creation timestamp |

---

## 14. `alerts` (Operational Exceptions)
Actionable alerts triggered for logistics control tower dispatchers.

| Field Name | Type | Nullable | Primary/Foreign Key | Description |
| :--- | :--- | :--- | :--- | :--- |
| `alert_id` | VARCHAR(64) | NO | PK | Format: `ALT-2026-000001` |
| `shipment_id` | VARCHAR(64) | NO | FK -> `shipments.shipment_id` | Target shipment |
| `prediction_timestamp` | TIMESTAMPTZ | NO | None | Prediction snapshot timestamp that triggered alert |
| `predicted_eta` | TIMESTAMPTZ | NO | None | Predicted arrival time |
| `promised_delivery_time`| TIMESTAMPTZ| NO | None | Contractual SLA delivery deadline |
| `predicted_delay_minutes`| INTEGER | NO | None | Minutes expected to breach deadline |
| `delay_probability` | NUMERIC(4,3)| NO | None | Calibrated probability of SLA failure |
| `delay_reason` | VARCHAR(64) | NO | None | Identified dominant delay cause |
| `severity` | VARCHAR(16) | NO | None | Enum: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `recommended_action` | TEXT | NO | None | Actionable SOP guidance for operations dispatch |
| `status` | VARCHAR(16) | NO | None | Enum: `ACTIVE`, `ACKNOWLEDGED`, `RESOLVED` |
| `created_at` | TIMESTAMPTZ | NO | None | Alert creation timestamp |

---

## 15. `users` (User Authentication & RBAC)
Represents application accounts with five distinct roles and enterprise credentials.

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `user_id` | VARCHAR(32) | NO | PK | Deterministic user identifier (e.g. `USR-SUPPLIER-01`) |
| `full_name` | VARCHAR(128) | NO | None | User's formal full name |
| `email` | VARCHAR(128) | NO | Unique | Corporate email address |
| `password_hash`| VARCHAR(256)| NO | None | Salted PBKDF2-HMAC-SHA256 password hash (never plain text) |
| `role` | VARCHAR(32) | NO | None | Enum: `SUPPLIER`, `LOGISTICS_PLANNER`, `CARRIER_OPERATOR`, `LOGISTICS_ANALYST`, `OPERATIONS_MANAGER` |
| `customer_id` | VARCHAR(64) | YES| None | Customer/supplier scope reference for SUPPLIER role |
| `carrier_id` | VARCHAR(32) | YES| FK -> `carriers.carrier_id` | Carrier scope reference for CARRIER_OPERATOR role |
| `facility_id` | VARCHAR(32) | YES| FK -> `facilities.facility_id`| Warehouse facility scope for warehouse operator |
| `account_status`| VARCHAR(16)| NO | None | Enum: `ACTIVE`, `INACTIVE`, `SUSPENDED` |
| `created_at` | TIMESTAMPTZ | NO | None | Account creation timestamp |
| `updated_at` | TIMESTAMPTZ | NO | None | Last update timestamp |
| `last_login_at`| TIMESTAMPTZ | YES| None | Last authenticated session timestamp |

---

## 16. `audit_records` (Immutable Audit Trail)
Maintains auditability and traceability of all state changes, planning assignments, scans, and system actions.

| Field Name | Type | Nullable | Primary/Foreign Key | Description & Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `audit_id` | VARCHAR(64) | NO | PK | Format: `AUD-2026-XXXXXX` |
| `user_id` | VARCHAR(32) | NO | FK -> `users.user_id` | User that initiated the action |
| `action_type` | VARCHAR(64) | NO | None | E.g. `CREATE_SHIPMENT`, `ASSIGN_CARRIER`, `RECORD_EVENT`, `UPDATE_QUEUE`, `RESOLVE_ALERT` |
| `entity_type` | VARCHAR(32) | NO | None | Target entity (e.g. `SHIPMENT`, `TRACKING_EVENT`, `FACILITY_QUEUE`, `ALERT`) |
| `entity_id` | VARCHAR(64) | NO | None | Primary key of target entity |
| `previous_value`| TEXT | YES| None | Pre-action state value / JSON |
| `new_value` | TEXT | YES| None | Post-action state value / JSON |
| `action_timestamp`| TIMESTAMPTZ| NO| None | Operational timestamp of action |
| `action_description`| TEXT | NO | None | Human-readable explanation of operation |

