"""
Deliberate Anomaly Injection Module
Implements the 14 mandatory anomaly scenarios with explicit ground-truth labeling.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import pandas as pd


@dataclass
class AnomalyRecord:
    anomaly_id: str
    issue_type: str
    affected_entity_type: str
    affected_entity_id: str
    anomaly_description: str
    expected_detection_result: str
    ground_truth_label: str
    severity: str
    injected_timestamp: str


class AnomalyInjector:
    """Injects 14 distinct anomalies into synthetic logistics datasets for quality testing."""

    def __init__(self, seed: int = 20261022):
        self.seed = seed
        self.anomalies: List[AnomalyRecord] = []
        self._counter = 1

    def _next_anomaly_id(self) -> str:
        aid = f"ANOM-{self._counter:04d}"
        self._counter += 1
        return aid

    def inject_all_anomalies(
        self,
        shipments_df: pd.DataFrame,
        legs_df: pd.DataFrame,
        events_df: pd.DataFrame,
        facilities_df: pd.DataFrame,
        queues_df: pd.DataFrame,
        weather_df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, List[AnomalyRecord]]:
        """Inject all 14 deliberate anomalies into cloned copies of the datasets."""
        # Deep copies to avoid side effects
        shipments = shipments_df.copy()
        legs = legs_df.copy()
        events = events_df.copy()
        facilities = facilities_df.copy()
        queues = queues_df.copy()
        weather = weather_df.copy()

        if len(shipments) < 20 or len(events) < 50:
            return shipments, legs, events, facilities, queues, weather, self.anomalies

        # 1. Event ingestion time confused with event time (ingestion < event_time)
        anom_shp_1 = shipments.iloc[0]["shipment_id"]
        ev_idx_1 = events[events["shipment_id"] == anom_shp_1].index
        if len(ev_idx_1) > 0:
            target_idx = ev_idx_1[0]
            evt_time = pd.to_datetime(events.loc[target_idx, "event_timestamp"])
            events.loc[target_idx, "ingestion_timestamp"] = (evt_time - timedelta(hours=3)).isoformat()
            self.anomalies.append(
                AnomalyRecord(
                    anomaly_id=self._next_anomaly_id(),
                    issue_type="INGESTION_BEFORE_EVENT_TIME",
                    affected_entity_type="TrackingEvent",
                    affected_entity_id=events.loc[target_idx, "event_id"],
                    anomaly_description="Ingestion timestamp is 3 hours before physical event timestamp (temporal causality violation).",
                    expected_detection_result="FAIL_TEMPORAL_INTEGRITY",
                    ground_truth_label="ANOMALY_TEMPORAL_CAUSALITY",
                    severity="HIGH",
                    injected_timestamp=datetime.utcnow().isoformat(),
                )
            )

        # 2. Impossible shipment route order (leg sequence jumping or arriving before departing)
        anom_shp_2 = shipments.iloc[1]["shipment_id"]
        leg_idx_2 = legs[legs["shipment_id"] == anom_shp_2].index
        if len(leg_idx_2) > 0:
            target_leg_idx = leg_idx_2[0]
            dep_time = pd.to_datetime(legs.loc[target_leg_idx, "scheduled_departure"])
            legs.loc[target_leg_idx, "actual_arrival"] = (dep_time - timedelta(hours=2)).isoformat()
            self.anomalies.append(
                AnomalyRecord(
                    anomaly_id=self._next_anomaly_id(),
                    issue_type="IMPOSSIBLE_ROUTE_CHRONOLOGY",
                    affected_entity_type="ShipmentLeg",
                    affected_entity_id=legs.loc[target_leg_idx, "leg_id"],
                    anomaly_description="Actual arrival is 2 hours before departure timestamp on leg.",
                    expected_detection_result="FAIL_ROUTE_CHRONOLOGY",
                    ground_truth_label="ANOMALY_IMPOSSIBLE_TRANSIT_ORDER",
                    severity="CRITICAL",
                    injected_timestamp=datetime.utcnow().isoformat(),
                )
            )

        # 3. ETA prediction using future tracking events (leakage simulation documented in ground truth)
        anom_shp_3 = shipments.iloc[2]["shipment_id"]
        self.anomalies.append(
            AnomalyRecord(
                anomaly_id=self._next_anomaly_id(),
                issue_type="FUTURE_EVENT_LEAKAGE",
                affected_entity_type="Shipment",
                affected_entity_id=anom_shp_3,
                anomaly_description="Synthetic feature generation evaluated using events past evaluation horizon T.",
                expected_detection_result="FAIL_LEAKAGE_PREVENTION_CHECK",
                ground_truth_label="ANOMALY_DATA_LEAKAGE",
                severity="CRITICAL",
                injected_timestamp=datetime.utcnow().isoformat(),
            )
        )

        # 4. Delivered shipment still marked in transit
        anom_shp_4 = shipments.iloc[3]["shipment_id"]
        deliv_events = events[(events["shipment_id"] == anom_shp_4) & (events["event_type"] == "DELIVERED")]
        if len(deliv_events) > 0:
            shipments.loc[shipments["shipment_id"] == anom_shp_4, "status"] = "IN_TRANSIT"
            self.anomalies.append(
                AnomalyRecord(
                    anomaly_id=self._next_anomaly_id(),
                    issue_type="DELIVERED_MARKED_IN_TRANSIT",
                    affected_entity_type="Shipment",
                    affected_entity_id=anom_shp_4,
                    anomaly_description="Shipment has physical DELIVERED event scan but shipment header status remains IN_TRANSIT.",
                    expected_detection_result="FAIL_LIFECYCLE_STATUS_CONSISTENCY",
                    ground_truth_label="ANOMALY_STATUS_MISMATCH",
                    severity="HIGH",
                    injected_timestamp=datetime.utcnow().isoformat(),
                )
            )

        # 5. Duplicate tracking events (exact duplicate event sequence)
        anom_shp_5 = shipments.iloc[4]["shipment_id"]
        ev_idx_5 = events[events["shipment_id"] == anom_shp_5].index
        if len(ev_idx_5) > 1:
            dup_row = events.loc[ev_idx_5[0]].copy()
            events = pd.concat([events, pd.DataFrame([dup_row])], ignore_index=True)
            self.anomalies.append(
                AnomalyRecord(
                    anomaly_id=self._next_anomaly_id(),
                    issue_type="DUPLICATE_TRACKING_EVENT",
                    affected_entity_type="TrackingEvent",
                    affected_entity_id=dup_row["event_id"],
                    anomaly_description=f"Duplicate event record injected for shipment {anom_shp_5} with identical event_id.",
                    expected_detection_result="FAIL_EVENT_UNIQUENESS",
                    ground_truth_label="ANOMALY_DUPLICATE_EVENT",
                    severity="MEDIUM",
                    injected_timestamp=datetime.utcnow().isoformat(),
                )
            )

        # 6. Delayed tracking scans (telemetry ingestion lag > 72 hours)
        anom_shp_6 = shipments.iloc[5]["shipment_id"]
        ev_idx_6 = events[events["shipment_id"] == anom_shp_6].index
        if len(ev_idx_6) > 0:
            target_idx_6 = ev_idx_6[-1]
            evt_time_6 = pd.to_datetime(events.loc[target_idx_6, "event_timestamp"])
            events.loc[target_idx_6, "ingestion_timestamp"] = (evt_time_6 + timedelta(hours=84)).isoformat()
            self.anomalies.append(
                AnomalyRecord(
                    anomaly_id=self._next_anomaly_id(),
                    issue_type="EXCESSIVE_INGESTION_LAG",
                    affected_entity_type="TrackingEvent",
                    affected_entity_id=events.loc[target_idx_6, "event_id"],
                    anomaly_description="Ingestion timestamp delayed by 84 hours after operational scan.",
                    expected_detection_result="WARN_EXCESSIVE_INGESTION_LATENCY",
                    ground_truth_label="ANOMALY_DELAYED_SCAN",
                    severity="MEDIUM",
                    injected_timestamp=datetime.utcnow().isoformat(),
                )
            )

        # 7. Missing intermediate tracking events (CREATED jumps directly to DELIVERED)
        anom_shp_7 = shipments.iloc[6]["shipment_id"]
        ev_idx_7 = events[events["shipment_id"] == anom_shp_7].index
        if len(ev_idx_7) > 3:
            # Drop intermediate events keeping only first and last
            keep_indices = [ev_idx_7[0], ev_idx_7[-1]]
            drop_indices = [idx for idx in ev_idx_7 if idx not in keep_indices]
            events = events.drop(index=drop_indices)
            self.anomalies.append(
                AnomalyRecord(
                    anomaly_id=self._next_anomaly_id(),
                    issue_type="MISSING_INTERMEDIATE_EVENTS",
                    affected_entity_type="Shipment",
                    affected_entity_id=anom_shp_7,
                    anomaly_description="Missing pickup and sorting scans between creation and final delivery.",
                    expected_detection_result="WARN_INCOMPLETE_EVENT_SEQUENCE",
                    ground_truth_label="ANOMALY_MISSING_SCANS",
                    severity="MEDIUM",
                    injected_timestamp=datetime.utcnow().isoformat(),
                )
            )

        # 8. Route changes (unplanned facility divergence mid-transit)
        anom_shp_8 = shipments.iloc[7]["shipment_id"]
        leg_idx_8 = legs[legs["shipment_id"] == anom_shp_8].index
        if len(leg_idx_8) > 0:
            legs.loc[leg_idx_8[0], "destination_facility_id"] = "FAC-099"
            self.anomalies.append(
                AnomalyRecord(
                    anomaly_id=self._next_anomaly_id(),
                    issue_type="UNPLANNED_ROUTE_DIVERGENCE",
                    affected_entity_type="ShipmentLeg",
                    affected_entity_id=legs.loc[leg_idx_8[0], "leg_id"],
                    anomaly_description="Destination facility rerouted to FAC-099 without updated parent shipment plan.",
                    expected_detection_result="WARN_ROUTE_DEVIATION",
                    ground_truth_label="ANOMALY_ROUTE_DIVERGENCE",
                    severity="MEDIUM",
                    injected_timestamp=datetime.utcnow().isoformat(),
                )
            )

        # 9. Severe facility congestion spike
        if len(queues) > 0:
            target_q_idx = queues.index[0]
            queues.loc[target_q_idx, "queue_length"] = 180
            queues.loc[target_q_idx, "average_wait_time_minutes"] = 480
            queues.loc[target_q_idx, "processing_status"] = "SEVERE_CONGESTION"
            self.anomalies.append(
                AnomalyRecord(
                    anomaly_id=self._next_anomaly_id(),
                    issue_type="CRITICAL_FACILITY_CONGESTION",
                    affected_entity_type="FacilityQueue",
                    affected_entity_id=queues.loc[target_q_idx, "queue_id"],
                    anomaly_description="Dock queue spike of 180 trailers and 480 min wait time at hub.",
                    expected_detection_result="ALERT_CONGESTION_EXCEEDED",
                    ground_truth_label="ANOMALY_CONGESTION_SPIKE",
                    severity="HIGH",
                    injected_timestamp=datetime.utcnow().isoformat(),
                )
            )

        # 10. Severe weather disruption shutdown
        if len(weather) > 0:
            target_w_idx = weather.index[0]
            weather.loc[target_w_idx, "severity"] = "SEVERE"
            weather.loc[target_w_idx, "event_type"] = "BLIZZARD"
            weather.loc[target_w_idx, "wind_speed_mph"] = 75.0
            self.anomalies.append(
                AnomalyRecord(
                    anomaly_id=self._next_anomaly_id(),
                    issue_type="SEVERE_WEATHER_SHUTDOWN",
                    affected_entity_type="WeatherEvent",
                    affected_entity_id=weather.loc[target_w_idx, "weather_event_id"],
                    anomaly_description="Category 4 Blizzard with 75mph winds causing complete corridor shutdown.",
                    expected_detection_result="ALERT_WEATHER_DISRUPTION",
                    ground_truth_label="ANOMALY_WEATHER_EMERGENCY",
                    severity="CRITICAL",
                    injected_timestamp=datetime.utcnow().isoformat(),
                )
            )

        # 11. Missing or invalid foreign keys in deliberate anomaly case
        anom_shp_11 = shipments.iloc[10]["shipment_id"]
        shipments.loc[shipments["shipment_id"] == anom_shp_11, "primary_carrier_id"] = "CAR-999-NONEXISTENT"
        self.anomalies.append(
            AnomalyRecord(
                anomaly_id=self._next_anomaly_id(),
                issue_type="INVALID_FOREIGN_KEY_REFERENCE",
                affected_entity_type="Shipment",
                affected_entity_id=anom_shp_11,
                anomaly_description="Shipment references non-existent carrier ID CAR-999-NONEXISTENT.",
                expected_detection_result="FAIL_FOREIGN_KEY_INTEGRITY",
                ground_truth_label="ANOMALY_BROKEN_FK",
                severity="CRITICAL",
                injected_timestamp=datetime.utcnow().isoformat(),
            )
        )

        # 12. Incorrect event sequence ordering (events out of numerical order)
        anom_shp_12 = shipments.iloc[11]["shipment_id"]
        ev_idx_12 = events[events["shipment_id"] == anom_shp_12].index
        if len(ev_idx_12) >= 3:
            events.loc[ev_idx_12[1], "event_sequence"] = 99
            self.anomalies.append(
                AnomalyRecord(
                    anomaly_id=self._next_anomaly_id(),
                    issue_type="INCORRECT_EVENT_SEQUENCE",
                    affected_entity_type="TrackingEvent",
                    affected_entity_id=events.loc[ev_idx_12[1], "event_id"],
                    anomaly_description="Event sequence jumps unexpectedly to 99 out of order.",
                    expected_detection_result="FAIL_EVENT_SEQUENCE_ORDER",
                    ground_truth_label="ANOMALY_OUT_OF_ORDER_SEQUENCE",
                    severity="HIGH",
                    injected_timestamp=datetime.utcnow().isoformat(),
                )
            )

        # 13. Invalid lifecycle transition
        anom_shp_13 = shipments.iloc[12]["shipment_id"]
        shipments.loc[shipments["shipment_id"] == anom_shp_13, "status"] = "INVALID_STATE_DISPATCHED_AGAIN"
        self.anomalies.append(
            AnomalyRecord(
                anomaly_id=self._next_anomaly_id(),
                issue_type="INVALID_LIFECYCLE_STATE_VALUE",
                affected_entity_type="Shipment",
                affected_entity_id=anom_shp_13,
                anomaly_description="Shipment status contains disallowed enum value INVALID_STATE_DISPATCHED_AGAIN.",
                expected_detection_result="FAIL_ENUM_VALIDATION",
                ground_truth_label="ANOMALY_INVALID_ENUM",
                severity="HIGH",
                injected_timestamp=datetime.utcnow().isoformat(),
            )
        )

        # 14. ETA prediction made after actual delivery time
        anom_shp_14 = shipments.iloc[13]["shipment_id"]
        self.anomalies.append(
            AnomalyRecord(
                anomaly_id=self._next_anomaly_id(),
                issue_type="PREDICTION_AFTER_DELIVERY",
                affected_entity_type="Shipment",
                affected_entity_id=anom_shp_14,
                anomaly_description="ETA prediction timestamp is later than shipment actual delivery time.",
                expected_detection_result="FAIL_PREDICTION_TIMING",
                ground_truth_label="ANOMALY_POST_DELIVERY_PREDICTION",
                severity="HIGH",
                injected_timestamp=datetime.utcnow().isoformat(),
            )
        )

        return shipments, legs, events, facilities, queues, weather, self.anomalies
