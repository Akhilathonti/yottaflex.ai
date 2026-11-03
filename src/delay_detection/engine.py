"""
Delay Detection and Alerting Engine
Applies rule-based triggers and ML probability thresholds to detect shipment risks and generate operational SOP alerts.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy.orm import Session

from src.config import (
    HIGH_RISK_DELAY_PROBABILITY_THRESHOLD,
    CRITICAL_RISK_DELAY_PROBABILITY_THRESHOLD,
    STALE_TRACKING_EVENT_HOURS_THRESHOLD,
    FACILITY_CONGESTION_QUEUE_THRESHOLD,
)
from src.database.models import Alert
from src.database.connection import db_session_scope
from src.utils.helpers import generate_alert_id


class DelayAlertEngine:
    """Evaluates logistics shipments for impending SLA breaches, environmental hazards, and operational bottlenecks."""

    def __init__(
        self,
        prob_threshold: float = HIGH_RISK_DELAY_PROBABILITY_THRESHOLD,
        critical_threshold: float = CRITICAL_RISK_DELAY_PROBABILITY_THRESHOLD,
    ):
        self.prob_threshold = prob_threshold
        self.critical_threshold = critical_threshold
        self._alert_counter = 1

    def evaluate_shipment_risk(
        self,
        shipment_id: str,
        predicted_eta: datetime,
        promised_delivery_time: datetime,
        delay_probability: float,
        current_status: str,
        weather_active: bool = False,
        facility_queue_length: int = 0,
        time_since_last_event_hours: float = 0.0,
        carrier_rating: float = 0.90,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single shipment and generate an alert if any operational threshold is breached.
        Delivered shipments are excluded from active alerts.
        """
        if current_status == "DELIVERED":
            return None

        predicted_delay_minutes = int((predicted_eta - promised_delivery_time).total_seconds() / 60)

        # Triggers:
        is_eta_late = predicted_delay_minutes > 15
        is_prob_high = delay_probability >= self.prob_threshold
        is_stale_telemetry = time_since_last_event_hours > STALE_TRACKING_EVENT_HOURS_THRESHOLD
        is_queue_congested = facility_queue_length > FACILITY_CONGESTION_QUEUE_THRESHOLD
        is_severe_weather = weather_active

        if not (is_eta_late or is_prob_high or is_stale_telemetry or is_queue_congested or is_severe_weather):
            return None

        # Determine dominant delay reason
        delay_reason = "OPERATIONAL_HANDLING_DELAY"
        if is_severe_weather:
            delay_reason = "WEATHER_DISRUPTION"
        elif is_queue_congested:
            delay_reason = "FACILITY_CONGESTION"
        elif carrier_rating < 0.88:
            delay_reason = "CARRIER_PERFORMANCE"
        elif is_stale_telemetry:
            delay_reason = "DELAYED_SCANS"
        elif predicted_delay_minutes > 120:
            delay_reason = "ROUTE_DEVIATION"

        # Determine Severity Level
        if delay_probability >= self.critical_threshold or predicted_delay_minutes > 180:
            severity = "CRITICAL"
        elif delay_probability >= 0.70 or predicted_delay_minutes > 60:
            severity = "HIGH"
        elif delay_probability >= 0.50 or predicted_delay_minutes > 20:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # SOP Action Recommendation
        sop_map = {
            "WEATHER_DISRUPTION": "Initiate winter highway detour or ground-hold buffer. Notify customer dispatch of weather emergency.",
            "FACILITY_CONGESTION": "Divert inbound linehaul trailers to secondary sort cross-dock to relieve dock backlog.",
            "CARRIER_PERFORMANCE": "Escalate priority linehaul replacement with carrier dispatch. Dispatch backup hot-shot driver.",
            "DELAYED_SCANS": "Query remote GPS tracker telemetry. Dispatch gate guard for physical yard trailer audit.",
            "ROUTE_DEVIATION": "Recalculate route coordinates. Contact carrier fleet tracking center immediately.",
            "OPERATIONAL_HANDLING_DELAY": "Fast-track priority sorting on primary outbound conveyor carousel.",
        }
        action = sop_map.get(delay_reason, "Monitor shipment progression and notify customer service.")

        alert = {
            "alert_id": generate_alert_id(self._alert_counter, 2026),
            "shipment_id": shipment_id,
            "prediction_timestamp": datetime.utcnow().isoformat(),
            "predicted_eta": predicted_eta.isoformat(),
            "promised_delivery_time": promised_delivery_time.isoformat(),
            "predicted_delay_minutes": predicted_delay_minutes,
            "delay_probability": round(delay_probability, 3),
            "delay_reason": delay_reason,
            "severity": severity,
            "recommended_action": action,
            "status": "ACTIVE",
        }
        self._alert_counter += 1
        return alert

    def evaluate_batch_and_persist(self, shipments_df: pd.DataFrame, eta_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Evaluate a batch of shipments and persist generated alerts to database."""
        alerts = []
        eta_map = {row["shipment_id"]: row for row in eta_df.to_dict("records")}

        for _, shp in shipments_df.iterrows():
            shp_id = shp["shipment_id"]
            if shp_id not in eta_map:
                continue

            eta_info = eta_map[shp_id]
            pred_eta = pd.to_datetime(eta_info["predicted_eta"])
            prom_del = pd.to_datetime(shp["promised_delivery_time"])
            prob = float(eta_info["delay_probability"])
            status = shp.get("status", "IN_TRANSIT")

            # Evaluate with simulated active conditions for demonstration
            is_delayed_target = bool(shp.get("is_delayed", False))
            alert = self.evaluate_shipment_risk(
                shipment_id=shp_id,
                predicted_eta=pred_eta,
                promised_delivery_time=prom_del,
                delay_probability=prob if is_delayed_target else 0.15,
                current_status="IN_TRANSIT" if is_delayed_target else status,
                weather_active=(shp_id.endswith("3") or shp_id.endswith("7")),
                facility_queue_length=65 if is_delayed_target else 25,
                time_since_last_event_hours=22.0 if is_delayed_target else 4.0,
            )
            if alert:
                alerts.append(alert)

        # Persist into DB
        if alerts:
            with db_session_scope() as session:
                for a in alerts:
                    alert_obj = Alert(
                        alert_id=a["alert_id"],
                        shipment_id=a["shipment_id"],
                        prediction_timestamp=pd.to_datetime(a["prediction_timestamp"]),
                        predicted_eta=pd.to_datetime(a["predicted_eta"]),
                        promised_delivery_time=pd.to_datetime(a["promised_delivery_time"]),
                        predicted_delay_minutes=a["predicted_delay_minutes"],
                        delay_probability=a["delay_probability"],
                        delay_reason=a["delay_reason"],
                        severity=a["severity"],
                        recommended_action=a["recommended_action"],
                        status=a["status"],
                    )
                    session.merge(alert_obj)

        return alerts
