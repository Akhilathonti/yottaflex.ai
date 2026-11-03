"""
Point-in-Time Feature Engineering Pipeline for ETA Prediction
Guarantees zero data leakage by enforcing ingestion_timestamp <= prediction_timestamp T.
"""
import logging
from datetime import datetime
from typing import Tuple, List, Optional
import numpy as np
import pandas as pd

from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, RANDOM_SEED

logger = logging.getLogger(__name__)


class PointInTimeFeatureEngineer:
    """Extracts features strictly known at prediction timestamp T without lookahead leakage."""

    def __init__(self, data_dir=RAW_DATA_DIR):
        self.data_dir = data_dir

    def build_feature_dataset(
        self,
        filter_valid_only: bool = True,
        simulate_leakage: bool = False,
    ) -> pd.DataFrame:
        """
        Build feature table where each row represents a shipment snapshot at prediction time T.
        If simulate_leakage=True, deliberately includes future events past T to test leakage detection.
        """
        logger.info("Loading relational raw tables for feature extraction...")
        shipments = pd.read_csv(self.data_dir / "shipments.csv")
        legs = pd.read_csv(self.data_dir / "shipment_legs.csv")
        events = pd.read_csv(self.data_dir / "tracking_events.csv")
        facilities = pd.read_csv(self.data_dir / "facilities.csv")
        carriers = pd.read_csv(self.data_dir / "carriers.csv")
        queues = pd.read_csv(self.data_dir / "facility_queues.csv")
        weather = pd.read_csv(self.data_dir / "weather_events.csv")
        service_levels = pd.read_csv(self.data_dir / "service_levels.csv")

        # Convert timestamps
        events["event_timestamp_dt"] = pd.to_datetime(events["event_timestamp"])
        events["ingestion_timestamp_dt"] = pd.to_datetime(events["ingestion_timestamp"])
        queues["observation_timestamp_dt"] = pd.to_datetime(queues["observation_timestamp"])
        weather["start_time_dt"] = pd.to_datetime(weather["start_time"])
        weather["end_time_dt"] = pd.to_datetime(weather["end_time"])

        # Filter out bad records for ML training if filter_valid_only
        if filter_valid_only:
            # Exclude deliberate corrupted IDs
            valid_carriers = set(carriers["carrier_id"])
            shipments = shipments[shipments["primary_carrier_id"].isin(valid_carriers)].copy()
            shipments = shipments[shipments["status"].isin(["DELIVERED", "IN_TRANSIT"])].copy()

        # Join carrier and service level static master data
        shipments = shipments.merge(
            carriers[["carrier_id", "on_time_rating", "service_type"]],
            left_on="primary_carrier_id",
            right_on="carrier_id",
            how="left",
        )
        shipments = shipments.merge(
            service_levels[["service_level_id", "target_delivery_hours", "delay_tolerance_minutes"]],
            on="service_level_id",
            how="left",
        )

        # Pre-index events and queues for high performance
        events_by_shipment = {k: v for k, v in events.groupby("shipment_id")}
        queues_by_facility = {k: v for k, v in queues.groupby("facility_id")}

        rows = []
        logger.info("Computing point-in-time features for %d shipments...", len(shipments))

        for _, shp in shipments.iterrows():
            shp_id = shp["shipment_id"]
            if pd.isna(shp["actual_pickup_time"]) or pd.isna(shp["actual_delivery_time"]):
                continue

            pickup_dt = pd.to_datetime(shp["actual_pickup_time"])
            actual_delivery_dt = pd.to_datetime(shp["actual_delivery_time"])
            promised_delivery_dt = pd.to_datetime(shp["promised_delivery_time"])

            # Define prediction timestamp T (e.g. at pickup or midway)
            pred_time_dt = pickup_dt

            # LEAKAGE BARRIER:
            # Only consider events whose ingestion_timestamp <= T
            shp_events = events_by_shipment.get(shp_id, pd.DataFrame())
            if simulate_leakage:
                known_events = shp_events
            else:
                if not shp_events.empty:
                    known_events = shp_events[shp_events["ingestion_timestamp_dt"] <= pred_time_dt]
                else:
                    known_events = pd.DataFrame()

            if known_events.empty:
                # If no scan yet ingested by T, we only know pre-dispatch plan
                last_event_type = "ORDER_CREATED"
                last_event_time = pickup_dt
                time_since_last_event_hrs = 0.0
                delayed_scans_count = 0
            else:
                sorted_events = known_events.sort_values("event_sequence")
                last_event = sorted_events.iloc[-1]
                last_event_type = last_event["event_type"]
                last_event_time = last_event["event_timestamp_dt"]
                time_since_last_event_hrs = max(0.0, (pred_time_dt - last_event_time).total_seconds() / 3600.0)
                # Count delayed scans
                scan_delays = (known_events["ingestion_timestamp_dt"] - known_events["event_timestamp_dt"]).dt.total_seconds() / 3600.0
                delayed_scans_count = int((scan_delays > 1.0).sum())

            # Current facility queue observed at or before T
            orig_fac_id = shp["origin_facility_id"]
            fac_q_all = queues_by_facility.get(orig_fac_id, pd.DataFrame())
            if not fac_q_all.empty:
                fac_q = fac_q_all[fac_q_all["observation_timestamp_dt"] <= pred_time_dt]
                if not fac_q.empty:
                    latest_q = fac_q.sort_values("observation_timestamp_dt").iloc[-1]
                    queue_length = int(latest_q["queue_length"])
                    queue_wait_time = int(latest_q["average_wait_time_minutes"])
                else:
                    queue_length = 20
                    queue_wait_time = 45
            else:
                queue_length = 20
                queue_wait_time = 45

            # Weather active at or before T
            active_w = weather[
                (weather["start_time_dt"] <= pred_time_dt)
                & (weather["end_time_dt"] >= pred_time_dt)
            ]
            weather_active = int(not active_w.empty)
            weather_severity_val = 0
            if weather_active:
                sev = active_w.iloc[0]["severity"]
                weather_severity_val = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "SEVERE": 4}.get(sev, 2)

            # Route progress
            total_dist = float(shp["total_distance_km"])
            elapsed_transit_hrs = max(0.0, (pred_time_dt - pickup_dt).total_seconds() / 3600.0)
            promised_remaining_hrs = max(-24.0, (promised_delivery_dt - pred_time_dt).total_seconds() / 3600.0)

            # Actual Ground Truth Targets (Separated from features)
            actual_remaining_minutes = max(0.0, (actual_delivery_dt - pred_time_dt).total_seconds() / 60.0)
            target_is_delayed = 1 if actual_delivery_dt > promised_delivery_dt else 0

            feature_dict = {
                "shipment_id": shp_id,
                "prediction_timestamp": pred_time_dt.isoformat(),
                # Features:
                "total_distance_km": total_dist,
                "remaining_route_distance_km": total_dist,  # At start, remaining = total
                "weight_kg": float(shp["weight_kg"]),
                "volume_cbm": float(shp["volume_cbm"]),
                "carrier_on_time_rating": float(shp["on_time_rating"]),
                "target_delivery_hours": int(shp["target_delivery_hours"]),
                "promised_remaining_hours": round(promised_remaining_hrs, 2),
                "elapsed_transit_hours": round(elapsed_transit_hrs, 2),
                "facility_queue_length": queue_length,
                "facility_queue_wait_minutes": queue_wait_time,
                "weather_active_flag": weather_active,
                "weather_severity_score": weather_severity_val,
                "delayed_scans_count": delayed_scans_count,
                "time_since_last_event_hours": round(time_since_last_event_hrs, 2),
                "hour_of_day": pred_time_dt.hour,
                "day_of_week": pred_time_dt.weekday(),
                "is_weekend": 1 if pred_time_dt.weekday() >= 5 else 0,
                # Targets (Never used as input to models!):
                "target_remaining_transit_minutes": round(actual_remaining_minutes, 2),
                "target_is_delayed": target_is_delayed,
                "actual_delivery_time": actual_delivery_dt.isoformat(),
            }
            rows.append(feature_dict)

        feat_df = pd.DataFrame(rows)
        # Chronological sorting for train/val/test splits
        feat_df = feat_df.sort_values("prediction_timestamp").reset_index(drop=True)

        out_path = PROCESSED_DATA_DIR / "features.csv"
        feat_df.to_csv(out_path, index=False)
        logger.info("Saved %d feature rows -> %s", len(feat_df), out_path)
        return feat_df
