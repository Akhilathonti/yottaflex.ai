# Logistics Data Quality Validation Summary

**Execution Timestamp**: 2026-11-02T14:32:30.905530  
**Total Checks Executed**: 20  
**Checks Passed**: 11  
**Checks Failed (Errors)**: 12  
**Warnings Flagged**: 1  
**Deliberate Anomalies Detected**: 13  

## Detected Anomalies & Integrity Violations

| Category | Check Name | Severity | Table | Affected Entity | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| STRUCTURAL | `PRIMARY_KEY_UNIQUENESS` | **ERROR** | `tracking_events` | `EVT-SHP-2026-000005-000001` | Duplicate primary key EVT-SHP-2026-000005-000001 detected in table tracking_events. |
| STRUCTURAL | `PRIMARY_KEY_UNIQUENESS` | **ERROR** | `tracking_events` | `EVT-SHP-2026-000005-000001` | Duplicate primary key EVT-SHP-2026-000005-000001 detected in table tracking_events. |
| STRUCTURAL | `FOREIGN_KEY_INTEGRITY` | **ERROR** | `shipments` | `SHP-2026-000011` | Orphan record: primary_carrier_id 'CAR-999-NONEXISTENT' not found in carriers.carrier_id. |
| STRUCTURAL | `ALLOWED_ENUM_VALIDATION` | **ERROR** | `shipments` | `SHP-2026-000013` | Invalid enum value 'INVALID_STATE_DISPATCHED_AGAIN' in column status. Allowed: {'CREATED', 'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'IN_TRANSIT', 'EXCEPTION'}. |
| TEMPORAL | `INGESTION_AFTER_EVENT_TIME` | **ERROR** | `tracking_events` | `EVT-SHP-2026-000001-000001` | Temporal causality breach: ingestion (2026-05-31T19:00:00) < event (2026-05-31T22:00:00). |
| TEMPORAL | `LEG_TRANSIT_CHRONOLOGY` | **ERROR** | `shipment_legs` | `LEG-SHP-2026-000002-01` | Chronology violation: arrival (2026-06-01T04:01:00) is before departure (2026-06-01T05:39:00). |
| TEMPORAL | `EVENT_SEQUENCE_ORDER` | **ERROR** | `tracking_events` | `SHP-2026-000005` | Non-sequential jump in event sequence: 1 -> 1 |
| TEMPORAL | `EVENT_SEQUENCE_ORDER` | **ERROR** | `tracking_events` | `SHP-2026-000007` | Non-sequential jump in event sequence: 1 -> 15 |
| TEMPORAL | `EVENT_SEQUENCE_ORDER` | **ERROR** | `tracking_events` | `SHP-2026-000012` | Non-sequential jump in event sequence: 1 -> 3 |
| TEMPORAL | `EXCESSIVE_INGESTION_LATENCY` | **WARNING** | `tracking_events` | `EVT-SHP-2026-000006-000015` | Delayed tracking scan: ingestion lag is 84.0 hours. |
| BUSINESS | `STATUS_DELIVERED_CONSISTENCY` | **ERROR** | `shipments` | `SHP-2026-000004` | Shipment has DELIVERED tracking event but header status remains IN_TRANSIT. |
| BUSINESS | `DUPLICATE_EVENT_SEQUENCE` | **ERROR** | `tracking_events` | `EVT-SHP-2026-000005-000001` | Duplicate event sequence 1 on shipment SHP-2026-000005. |
| BUSINESS | `DUPLICATE_EVENT_SEQUENCE` | **ERROR** | `tracking_events` | `EVT-SHP-2026-000005-000001` | Duplicate event sequence 1 on shipment SHP-2026-000005. |
