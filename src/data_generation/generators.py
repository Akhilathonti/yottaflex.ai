"""
Synthetic Data Generation Engine for Intelligent Logistics ETA Prediction System
Generates relational master and transactional data with strict chronological consistency.
"""
import math
import random
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd
from faker import Faker

from src.config import (
    RANDOM_SEED,
    SERVICE_LEVELS_CONFIG,
    DELAY_REASONS_CONFIG,
    DEFAULT_DELAY_TOLERANCE_MINUTES,
)
from src.utils.helpers import (
    haversine_distance_km,
    generate_shipment_id,
    generate_leg_id,
    generate_event_id,
    generate_eta_id,
    generate_alert_id,
    generate_queue_id,
    generate_weather_id,
)

# Benchmark US Logistics Hub Coordinates
KEY_HUB_LOCATIONS = [
    {"city": "Chicago", "state": "IL", "lat": 41.8781, "lon": -87.6298, "type": "SORTATION_CENTER"},
    {"city": "Dallas", "state": "TX", "lat": 32.7767, "lon": -96.7970, "type": "DISTRIBUTION_CENTER"},
    {"city": "Atlanta", "state": "GA", "lat": 33.7490, "lon": -84.3880, "type": "ORIGIN_HUB"},
    {"city": "Memphis", "state": "TN", "lat": 35.1495, "lon": -90.0490, "type": "ORIGIN_HUB"},
    {"city": "Louisville", "state": "KY", "lat": 38.2527, "lon": -85.7585, "type": "SORTATION_CENTER"},
    {"city": "Los Angeles", "state": "CA", "lat": 34.0522, "lon": -118.2437, "type": "CROSS_DOCK"},
    {"city": "Newark", "state": "NJ", "lat": 40.7357, "lon": -74.1724, "type": "DESTINATION_DEPOT"},
    {"city": "Indianapolis", "state": "IN", "lat": 39.7684, "lon": -86.1581, "type": "SORTATION_CENTER"},
    {"city": "Columbus", "state": "OH", "lat": 39.9612, "lon": -82.9988, "type": "DISTRIBUTION_CENTER"},
    {"city": "Denver", "state": "CO", "lat": 39.7392, "lon": -104.9903, "type": "CROSS_DOCK"},
    {"city": "Seattle", "state": "WA", "lat": 47.6062, "lon": -122.3321, "type": "DESTINATION_DEPOT"},
    {"city": "Kansas City", "state": "MO", "lat": 39.0997, "lon": -94.5786, "type": "SORTATION_CENTER"},
    {"city": "Phoenix", "state": "AZ", "lat": 33.4484, "lon": -112.0740, "type": "DESTINATION_DEPOT"},
    {"city": "Philadelphia", "state": "PA", "lat": 39.9526, "lon": -75.1652, "type": "CROSS_DOCK"},
    {"city": "Charlotte", "state": "NC", "lat": 35.2271, "lon": -80.8431, "type": "DISTRIBUTION_CENTER"},
    {"city": "Detroit", "state": "MI", "lat": 42.3314, "lon": -83.0458, "type": "DISTRIBUTION_CENTER"},
    {"city": "Minneapolis", "state": "MN", "lat": 44.9778, "lon": -93.2650, "type": "DESTINATION_DEPOT"},
    {"city": "Salt Lake City", "state": "UT", "lat": 40.7608, "lon": -111.8910, "type": "CROSS_DOCK"},
    {"city": "Miami", "state": "FL", "lat": 25.7617, "lon": -80.1918, "type": "DESTINATION_DEPOT"},
    {"city": "Nashville", "state": "TN", "lat": 36.1627, "lon": -86.7816, "type": "SORTATION_CENTER"},
]

CARRIER_PROFILES = [
    {"carrier_id": "CAR-001", "name": "Apex Express Linehaul", "code": "APEX", "service_type": "AIR_EXPRESS", "on_time_rating": 0.95, "fleet": 450},
    {"carrier_id": "CAR-002", "name": "SwiftLog Logistics", "code": "SWFT", "service_type": "GROUND", "on_time_rating": 0.91, "fleet": 820},
    {"carrier_id": "CAR-003", "name": "Blaze National Freight", "code": "BLAZ", "service_type": "FREIGHT", "on_time_rating": 0.86, "fleet": 600},
    {"carrier_id": "CAR-004", "name": "Horizon Parcel Systems", "code": "HRZN", "service_type": "HYBRID", "on_time_rating": 0.93, "fleet": 520},
    {"carrier_id": "CAR-005", "name": "Titan Heavy Transit", "code": "TITN", "service_type": "FREIGHT", "on_time_rating": 0.84, "fleet": 380},
    {"carrier_id": "CAR-006", "name": "Polar Air Cargo", "code": "POLR", "service_type": "AIR_EXPRESS", "on_time_rating": 0.96, "fleet": 210},
    {"carrier_id": "CAR-007", "name": "Vanguard Intermodal", "code": "VNGD", "service_type": "GROUND", "on_time_rating": 0.89, "fleet": 740},
    {"carrier_id": "CAR-008", "name": "OmniRoute Solutions", "code": "OMNI", "service_type": "HYBRID", "on_time_rating": 0.92, "fleet": 490},
]


class LogisticsDataGenerator:
    """End-to-end generator for master data, shipments, multi-leg routes, events, and ground-truth outcomes."""

    def __init__(self, seed: int = RANDOM_SEED):
        self.seed = seed
        self.fake = Faker()
        Faker.seed(seed)
        random.seed(seed)
        np.random.seed(seed)

        # Baseline dates in 2026
        self.start_date = datetime(2026, 6, 1, 0, 0, 0)
        self.end_date = datetime(2026, 10, 31, 23, 59, 59)

    def generate_service_levels(self) -> pd.DataFrame:
        """Service levels dataframe."""
        df = pd.DataFrame(SERVICE_LEVELS_CONFIG)
        df["created_at"] = self.start_date.isoformat()
        return df

    def generate_delay_reasons(self) -> pd.DataFrame:
        """Delay reason taxonomy dataframe."""
        df = pd.DataFrame(DELAY_REASONS_CONFIG)
        df["created_at"] = self.start_date.isoformat()
        return df

    def generate_carriers(self) -> pd.DataFrame:
        """Carrier master dataframe."""
        records = []
        for c in CARRIER_PROFILES:
            records.append({
                "carrier_id": c["carrier_id"],
                "name": c["name"],
                "code": c["code"],
                "service_type": c["service_type"],
                "contact_email": f"dispatch@{c['code'].lower()}logistics.com",
                "on_time_rating": float(c["on_time_rating"]),
                "active_fleet_size": int(c["fleet"]),
                "operating_status": "ACTIVE",
                "created_at": self.start_date.isoformat(),
            })
        return pd.DataFrame(records)

    def generate_facilities(self, num_facilities: int = 100) -> pd.DataFrame:
        """Generate network facilities with geographical coordinates and capacity limits."""
        records = []
        facility_types = ["ORIGIN_HUB", "SORTATION_CENTER", "DISTRIBUTION_CENTER", "CROSS_DOCK", "DESTINATION_DEPOT"]

        for i in range(num_facilities):
            fid = f"FAC-{i+1:03d}"
            # Pick from anchor cities or synthesize realistic nearby coordinates
            anchor = KEY_HUB_LOCATIONS[i % len(KEY_HUB_LOCATIONS)]
            # Add small deterministic offset
            jitter_lat = ((i * 17) % 100 - 50) * 0.02
            jitter_lon = ((i * 23) % 100 - 50) * 0.02

            lat = round(anchor["lat"] + jitter_lat, 6)
            lon = round(anchor["lon"] + jitter_lon, 6)
            ftype = anchor["type"] if i < len(KEY_HUB_LOCATIONS) else facility_types[i % len(facility_types)]

            records.append({
                "facility_id": fid,
                "name": f"{anchor['city']} Logistics Facility #{i+1}",
                "facility_type": ftype,
                "city": anchor["city"],
                "state": anchor["state"],
                "country": "USA",
                "latitude": lat,
                "longitude": lon,
                "capacity_daily_shipments": int(5000 + (i % 10) * 1500),
                "current_utilization_rate": round(float(0.60 + (i % 7) * 0.05), 3),
                "operating_hours_start": "06:00:00",
                "operating_hours_end": "22:00:00",
                "cutoff_time": "18:00:00",
                "is_active": True,
                "created_at": self.start_date.isoformat(),
            })
        return pd.DataFrame(records)

    def generate_routes(self, facilities_df: pd.DataFrame) -> pd.DataFrame:
        """Generate direct routes between pairs of active facilities."""
        records = []
        fac_list = facilities_df[["facility_id", "latitude", "longitude"]].to_dict("records")
        corridors = ["I-80", "I-95", "I-40", "I-10", "I-70", "I-35", "I-75", "I-90"]

        route_id_counter = 1
        num_facilities = len(fac_list)

        # Generate dense routes for hub connectivity
        for i in range(num_facilities):
            orig = fac_list[i]
            # Connect each facility to 4-8 other facilities
            for k in range(1, min(7, num_facilities)):
                dest_idx = (i + k * 3) % num_facilities
                if dest_idx == i:
                    continue
                dest = fac_list[dest_idx]

                dist = haversine_distance_km(orig["latitude"], orig["longitude"], dest["latitude"], dest["longitude"])
                if dist < 30.0:
                    dist = 45.0
                # Average speed: 75 km/h for highway transit + 1.5h handling
                duration_hours = round(dist / 75.0 + 1.5, 2)
                corridor = corridors[route_id_counter % len(corridors)]
                risk_factor = round(1.0 + (route_id_counter % 5) * 0.15, 2)

                records.append({
                    "route_id": f"RT-{route_id_counter:04d}",
                    "origin_facility_id": orig["facility_id"],
                    "destination_facility_id": dest["facility_id"],
                    "distance_km": dist,
                    "standard_duration_hours": duration_hours,
                    "highway_corridor": corridor,
                    "risk_factor": risk_factor,
                    "is_active": True,
                    "created_at": self.start_date.isoformat(),
                })
                route_id_counter += 1

        return pd.DataFrame(records)

    def generate_weather_events(self, num_events: int = 1000) -> pd.DataFrame:
        """Generate weather disruption windows."""
        records = []
        weather_types = ["SNOW_STORM", "BLIZZARD", "HEAVY_RAIN", "FLOOD", "FOG", "HIGH_WINDS", "TORNADO", "ICE_STORM"]
        severities = ["LOW", "MEDIUM", "HIGH", "SEVERE"]
        regions = [
            "Midwest Corridor - IL/IN/OH", "Northeast Highway - NY/NJ/PA", "Great Lakes - MI/WI",
            "Texas Gulf - TX/LA", "Southeast Hub - GA/TN/NC", "Central Plains - MO/KS/NE",
            "Mountain Pass - CO/WY/UT", "Pacific Northwest - WA/OR", "Southwest Corridor - AZ/NM"
        ]

        total_days = (self.end_date - self.start_date).days
        for i in range(num_events):
            wid = generate_weather_id(i + 1, 2026)
            day_offset = (i * 7) % total_days
            start_hour = (i * 3) % 24
            duration_hours = 6 + (i % 36)

            start = self.start_date + timedelta(days=day_offset, hours=start_hour)
            end = start + timedelta(hours=duration_hours)
            w_type = weather_types[i % len(weather_types)]
            severity = severities[(i // 3) % len(severities)]
            region = regions[i % len(regions)]

            records.append({
                "weather_event_id": wid,
                "event_type": w_type,
                "severity": severity,
                "affected_region": region,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "visibility_miles": round(max(0.2, 10.0 - (i % 9)), 1),
                "wind_speed_mph": round(15.0 + (i % 55), 1),
                "precipitation_mm": round(5.0 + (i % 60), 1),
                "created_at": self.start_date.isoformat(),
            })
        return pd.DataFrame(records)

    def generate_facility_queues(self, facilities_df: pd.DataFrame, num_samples: int = 2000) -> pd.DataFrame:
        """Generate queue observation time series for facilities."""
        records = []
        fac_ids = facilities_df["facility_id"].tolist()
        total_hours = int((self.end_date - self.start_date).total_seconds() // 3600)

        for i in range(num_samples):
            fac_id = fac_ids[i % len(fac_ids)]
            hour_offset = (i * 13) % total_hours
            obs_time = self.start_date + timedelta(hours=hour_offset)

            # Diurnal congestion factor
            hour = obs_time.hour
            is_peak = (8 <= hour <= 12) or (17 <= hour <= 21)
            base_queue = 35 if is_peak else 15
            queue_len = int(base_queue + (i % 25) + np.random.poisson(5))
            avg_wait = int(queue_len * 2.8 + (i % 15))
            dock_util = round(min(100.0, float(queue_len * 1.5 + 20.0)), 2)

            status = "NORMAL"
            if queue_len > 45:
                status = "MODERATE_CONGESTION"
            if queue_len > 65:
                status = "SEVERE_CONGESTION"

            records.append({
                "queue_id": generate_queue_id(fac_id, obs_time),
                "facility_id": fac_id,
                "observation_timestamp": obs_time.isoformat(),
                "queue_length": queue_len,
                "average_wait_time_minutes": avg_wait,
                "dock_utilization_pct": dock_util,
                "processing_status": status,
                "created_at": obs_time.isoformat(),
            })
        return pd.DataFrame(records)

    def generate_facility_weather_bridge(
        self, facilities_df: pd.DataFrame, weather_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Link weather disruptions to facilities."""
        records = []
        fac_ids = facilities_df["facility_id"].tolist()
        w_events = weather_df[["weather_event_id", "severity"]].to_dict("records")

        for idx, w in enumerate(w_events[: min(len(w_events), 500)]):
            # Each weather event affects 2 to 4 facilities
            num_facs = 2 + (idx % 3)
            for k in range(num_facs):
                fac_id = fac_ids[(idx * 3 + k) % len(fac_ids)]
                records.append({
                    "facility_id": fac_id,
                    "weather_event_id": w["weather_event_id"],
                    "impact_level": w["severity"],
                    "created_at": self.start_date.isoformat(),
                })
        return pd.DataFrame(records).drop_duplicates(subset=["facility_id", "weather_event_id"])

    def generate_shipments_and_telemetry(
        self,
        num_shipments: int,
        facilities_df: pd.DataFrame,
        carriers_df: pd.DataFrame,
        service_levels_df: pd.DataFrame,
        weather_df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Generate complete parent shipments, multi-leg journeys, tracking events,
        point-in-time ETA snapshots, and ground-truth delay reasons.
        """
        fac_lookup = {row["facility_id"]: row for row in facilities_df.to_dict("records")}
        carrier_lookup = {row["carrier_id"]: row for row in carriers_df.to_dict("records")}
        sl_lookup = {row["service_level_id"]: row for row in service_levels_df.to_dict("records")}

        fac_ids = list(fac_lookup.keys())
        carrier_ids = list(carrier_lookup.keys())
        sl_ids = list(sl_lookup.keys())

        shipment_records = []
        leg_records = []
        event_records = []
        eta_records = []
        shipment_delay_records = []

        total_sim_hours = int((self.end_date - self.start_date).total_seconds() // 3600) - 240

        for s_idx in range(num_shipments):
            shipment_id = generate_shipment_id(s_idx + 1, 2026)
            order_id = f"ORD-2026-{s_idx + 1:06d}"
            customer_id = f"CUST-{(s_idx * 13) % 5000 + 1:05d}"

            # Select distinct origin and destination
            orig_idx = (s_idx * 7) % len(fac_ids)
            dest_idx = (s_idx * 11 + 3) % len(fac_ids)
            if orig_idx == dest_idx:
                dest_idx = (dest_idx + 1) % len(fac_ids)

            origin_fid = fac_ids[orig_idx]
            destination_fid = fac_ids[dest_idx]
            orig_fac = fac_lookup[origin_fid]
            dest_fac = fac_lookup[destination_fid]

            # Service level and carrier
            sl_id = sl_ids[s_idx % len(sl_ids)]
            sl_info = sl_lookup[sl_id]
            carrier_id = carrier_ids[s_idx % len(carrier_ids)]
            carrier_info = carrier_lookup[carrier_id]

            # Weights and volume
            weight_kg = round(float(2.0 + (s_idx % 48) * 1.5 + (s_idx % 5)), 2)
            volume_cbm = round(float(0.01 + weight_kg * 0.005), 3)

            # Scheduled pickup time
            pickup_hour_offset = (s_idx * 5) % total_sim_hours
            scheduled_pickup = self.start_date + timedelta(hours=pickup_hour_offset, minutes=(s_idx % 60))
            # Promoted delivery target based on SLA
            target_hours = sl_info["target_delivery_hours"]
            promised_delivery = scheduled_pickup + timedelta(hours=target_hours)

            # Determine journey topology: 1, 2, or 3 legs
            # If distance is large (>1200km) or multi-hop: 2-3 legs
            total_crow_dist = haversine_distance_km(
                orig_fac["latitude"], orig_fac["longitude"],
                dest_fac["latitude"], dest_fac["longitude"]
            )
            num_legs = 1
            if total_crow_dist > 800:
                num_legs = 2
            if total_crow_dist > 1800:
                num_legs = 3

            # Plan legs
            legs_for_shipment = []
            current_fac_id = origin_fid
            leg_facilities = [origin_fid]

            if num_legs == 2:
                # Intermediate sort hub
                hub_idx = (orig_idx + dest_idx + 2) % len(fac_ids)
                if hub_idx in (orig_idx, dest_idx):
                    hub_idx = (hub_idx + 5) % len(fac_ids)
                leg_facilities.append(fac_ids[hub_idx])
            elif num_legs == 3:
                hub1_idx = (orig_idx + 2) % len(fac_ids)
                hub2_idx = (dest_idx - 2) % len(fac_ids)
                leg_facilities.extend([fac_ids[hub1_idx], fac_ids[hub2_idx]])
            leg_facilities.append(destination_fid)

            # Calculate total distance and generate legs
            cum_dist = 0.0
            planned_departure = scheduled_pickup + timedelta(hours=1)
            actual_leg_durations = []
            accumulated_delay_mins = 0
            primary_delay_cause = None

            # Simulation factors
            carrier_on_time = carrier_info["on_time_rating"]
            is_carrier_slow = (s_idx % 100) > int(carrier_on_time * 100)
            is_weather_impacted = (s_idx % 13 == 0)
            is_congestion_impacted = (s_idx % 17 == 0)

            actual_pickup = scheduled_pickup + timedelta(minutes=int(random.randint(5, 45)))
            current_time = actual_pickup

            event_seq = 1

            # Event 1: CREATED
            created_evt_time = scheduled_pickup - timedelta(hours=2)
            created_ingestion_time = created_evt_time + timedelta(minutes=2)
            event_records.append({
                "event_id": generate_event_id(shipment_id, event_seq),
                "shipment_id": shipment_id,
                "leg_id": None,
                "facility_id": origin_fid,
                "event_timestamp": created_evt_time.isoformat(),
                "ingestion_timestamp": created_ingestion_time.isoformat(),
                "event_type": "CREATED",
                "event_location": f"{orig_fac['city']}, {orig_fac['state']}",
                "event_sequence": event_seq,
                "event_source": "WMS",
                "latitude": orig_fac["latitude"],
                "longitude": orig_fac["longitude"],
                "notes": "Shipment order booked and manifest generated.",
                "created_at": created_ingestion_time.isoformat(),
            })
            event_seq += 1

            # Event 2: PICKED_UP
            pickup_ingestion_time = actual_pickup + timedelta(minutes=5)
            event_records.append({
                "event_id": generate_event_id(shipment_id, event_seq),
                "shipment_id": shipment_id,
                "leg_id": None,
                "facility_id": origin_fid,
                "event_timestamp": actual_pickup.isoformat(),
                "ingestion_timestamp": pickup_ingestion_time.isoformat(),
                "event_type": "PICKED_UP",
                "event_location": f"{orig_fac['city']}, {orig_fac['state']}",
                "event_sequence": event_seq,
                "event_source": "MOBILE_APP",
                "latitude": orig_fac["latitude"],
                "longitude": orig_fac["longitude"],
                "notes": f"Driver picked up freight at {orig_fac['name']}.",
                "created_at": pickup_ingestion_time.isoformat(),
            })
            event_seq += 1

            # Build each leg
            total_shipment_dist = 0.0
            for leg_num in range(1, len(leg_facilities)):
                l_orig_id = leg_facilities[leg_num - 1]
                l_dest_id = leg_facilities[leg_num]
                l_orig = fac_lookup[l_orig_id]
                l_dest = fac_lookup[l_dest_id]

                leg_id = generate_leg_id(shipment_id, leg_num)
                leg_dist = haversine_distance_km(l_orig["latitude"], l_orig["longitude"], l_dest["latitude"], l_dest["longitude"])
                if leg_dist < 20.0:
                    leg_dist = 40.0
                total_shipment_dist += leg_dist

                planned_transit_hrs = round(leg_dist / 75.0 + 1.0, 2)
                leg_sched_dep = planned_departure
                leg_sched_arr = leg_sched_dep + timedelta(hours=planned_transit_hrs)

                # Simulated transit execution with potential real-world delays
                leg_delay_mins = 0
                if is_weather_impacted and leg_num == 1:
                    leg_delay_mins += random.randint(180, 540)
                    primary_delay_cause = "WEATHER_DISRUPTION"
                if is_congestion_impacted and leg_num > 1:
                    leg_delay_mins += random.randint(120, 360)
                    if not primary_delay_cause:
                        primary_delay_cause = "FACILITY_CONGESTION"
                if is_carrier_slow:
                    leg_delay_mins += random.randint(45, 180)
                    if not primary_delay_cause:
                        primary_delay_cause = "CARRIER_PERFORMANCE"

                accumulated_delay_mins += leg_delay_mins

                leg_actual_dep = current_time + timedelta(minutes=15)
                actual_duration_hrs = planned_transit_hrs + (leg_delay_mins / 60.0)
                leg_actual_arr = leg_actual_dep + timedelta(hours=actual_duration_hrs)

                leg_records.append({
                    "leg_id": leg_id,
                    "shipment_id": shipment_id,
                    "leg_sequence": leg_num,
                    "route_id": None,
                    "carrier_id": carrier_id,
                    "origin_facility_id": l_orig_id,
                    "destination_facility_id": l_dest_id,
                    "leg_status": "COMPLETED",
                    "distance_km": leg_dist,
                    "estimated_transit_hours": planned_transit_hrs,
                    "actual_transit_hours": round(actual_duration_hrs, 2),
                    "scheduled_departure": leg_sched_dep.isoformat(),
                    "actual_departure": leg_actual_dep.isoformat(),
                    "scheduled_arrival": leg_sched_arr.isoformat(),
                    "actual_arrival": leg_actual_arr.isoformat(),
                    "created_at": leg_sched_dep.isoformat(),
                })

                # Leg Events: DEPARTED
                dep_ingestion = leg_actual_dep + timedelta(minutes=4)
                event_records.append({
                    "event_id": generate_event_id(shipment_id, event_seq),
                    "shipment_id": shipment_id,
                    "leg_id": leg_id,
                    "facility_id": l_orig_id,
                    "event_timestamp": leg_actual_dep.isoformat(),
                    "ingestion_timestamp": dep_ingestion.isoformat(),
                    "event_type": "DEPARTED_FACILITY",
                    "event_location": f"{l_orig['city']}, {l_orig['state']}",
                    "event_sequence": event_seq,
                    "event_source": "EDI",
                    "latitude": l_orig["latitude"],
                    "longitude": l_orig["longitude"],
                    "notes": f"Departed facility on leg {leg_num}.",
                    "created_at": dep_ingestion.isoformat(),
                })
                event_seq += 1

                # Midway IN_TRANSIT_SCAN
                mid_time = leg_actual_dep + timedelta(hours=actual_duration_hrs / 2.0)
                mid_lat = round((l_orig["latitude"] + l_dest["latitude"]) / 2.0, 6)
                mid_lon = round((l_orig["longitude"] + l_dest["longitude"]) / 2.0, 6)
                mid_ingestion = mid_time + timedelta(minutes=7)
                event_records.append({
                    "event_id": generate_event_id(shipment_id, event_seq),
                    "shipment_id": shipment_id,
                    "leg_id": leg_id,
                    "facility_id": None,
                    "event_timestamp": mid_time.isoformat(),
                    "ingestion_timestamp": mid_ingestion.isoformat(),
                    "event_type": "IN_TRANSIT_SCAN",
                    "event_location": f"Highway Corridor en route to {l_dest['city']}",
                    "event_sequence": event_seq,
                    "event_source": "GPS_TRACKER",
                    "latitude": mid_lat,
                    "longitude": mid_lon,
                    "notes": "GPS ping in transit.",
                    "created_at": mid_ingestion.isoformat(),
                })
                event_seq += 1

                # ARRIVED_AT_FACILITY
                arr_ingestion = leg_actual_arr + timedelta(minutes=6)
                event_records.append({
                    "event_id": generate_event_id(shipment_id, event_seq),
                    "shipment_id": shipment_id,
                    "leg_id": leg_id,
                    "facility_id": l_dest_id,
                    "event_timestamp": leg_actual_arr.isoformat(),
                    "ingestion_timestamp": arr_ingestion.isoformat(),
                    "event_type": "ARRIVED_AT_FACILITY",
                    "event_location": f"{l_dest['city']}, {l_dest['state']}",
                    "event_sequence": event_seq,
                    "event_source": "WMS",
                    "latitude": l_dest["latitude"],
                    "longitude": l_dest["longitude"],
                    "notes": f"Arrived at facility {l_dest['name']}.",
                    "created_at": arr_ingestion.isoformat(),
                })
                event_seq += 1

                # Sort completed if intermediate leg
                if leg_num < len(leg_facilities) - 1:
                    sort_time = leg_actual_arr + timedelta(hours=1.5)
                    sort_ingestion = sort_time + timedelta(minutes=8)
                    event_records.append({
                        "event_id": generate_event_id(shipment_id, event_seq),
                        "shipment_id": shipment_id,
                        "leg_id": leg_id,
                        "facility_id": l_dest_id,
                        "event_timestamp": sort_time.isoformat(),
                        "ingestion_timestamp": sort_ingestion.isoformat(),
                        "event_type": "SORTING_COMPLETED",
                        "event_location": f"{l_dest['city']}, {l_dest['state']}",
                        "event_sequence": event_seq,
                        "event_source": "WMS",
                        "latitude": l_dest["latitude"],
                        "longitude": l_dest["longitude"],
                        "notes": "Cross-dock sorting completed for next leg.",
                        "created_at": sort_ingestion.isoformat(),
                    })
                    event_seq += 1
                    current_time = sort_time
                    planned_departure = leg_sched_arr + timedelta(hours=2.0)
                else:
                    current_time = leg_actual_arr

            # Final delivery leg: OUT_FOR_DELIVERY and DELIVERED
            ofd_time = current_time + timedelta(hours=1.0)
            ofd_ingestion = ofd_time + timedelta(minutes=5)
            event_records.append({
                "event_id": generate_event_id(shipment_id, event_seq),
                "shipment_id": shipment_id,
                "leg_id": None,
                "facility_id": destination_fid,
                "event_timestamp": ofd_time.isoformat(),
                "ingestion_timestamp": ofd_ingestion.isoformat(),
                "event_type": "OUT_FOR_DELIVERY",
                "event_location": f"{dest_fac['city']}, {dest_fac['state']}",
                "event_sequence": event_seq,
                "event_source": "MOBILE_APP",
                "latitude": dest_fac["latitude"],
                "longitude": dest_fac["longitude"],
                "notes": "Loaded onto local courier van out for delivery.",
                "created_at": ofd_ingestion.isoformat(),
            })
            event_seq += 1

            # Final DELIVERY outcome
            actual_delivery = ofd_time + timedelta(hours=2.5)
            deliv_ingestion = actual_delivery + timedelta(minutes=3)
            event_records.append({
                "event_id": generate_event_id(shipment_id, event_seq),
                "shipment_id": shipment_id,
                "leg_id": None,
                "facility_id": destination_fid,
                "event_timestamp": actual_delivery.isoformat(),
                "ingestion_timestamp": deliv_ingestion.isoformat(),
                "event_type": "DELIVERED",
                "event_location": f"{dest_fac['city']}, {dest_fac['state']}",
                "event_sequence": event_seq,
                "event_source": "MOBILE_APP",
                "latitude": dest_fac["latitude"],
                "longitude": dest_fac["longitude"],
                "notes": "Delivered to recipient customer front door. Signature captured.",
                "created_at": deliv_ingestion.isoformat(),
            })

            # Ground Truth Calculation
            actual_delay_minutes = int((actual_delivery - promised_delivery).total_seconds() / 60)
            is_delayed = actual_delay_minutes > 0

            # Assign ground-truth delay reasons
            if is_delayed:
                if not primary_delay_cause:
                    primary_delay_cause = "OPERATIONAL_HANDLING_DELAY" if actual_delay_minutes < 90 else "CARRIER_PERFORMANCE"

                reason_code_map = {
                    "WEATHER_DISRUPTION": "RZN-001",
                    "FACILITY_CONGESTION": "RZN-002",
                    "CARRIER_PERFORMANCE": "RZN-003",
                    "OPERATIONAL_HANDLING_DELAY": "RZN-007",
                }
                r_id = reason_code_map.get(primary_delay_cause, "RZN-008")
                shipment_delay_records.append({
                    "shipment_id": shipment_id,
                    "reason_id": r_id,
                    "attribution_score": 0.85,
                    "is_primary": True,
                    "is_ground_truth": True,
                    "created_at": actual_delivery.isoformat(),
                })

            # ETA Prediction Snapshot (evaluated at pickup time T)
            # T is point-in-time when package was picked up
            pred_time = actual_pickup
            remaining_transit_est_hrs = total_shipment_dist / 75.0 + (num_legs * 1.5)
            # Simulated model prediction
            noise_mins = ((s_idx * 19) % 51 - 25)
            pred_remaining_minutes = round(max(30.0, remaining_transit_est_hrs * 60.0 + noise_mins), 2)
            predicted_eta = pred_time + timedelta(minutes=pred_remaining_minutes)

            # Delay probability calculation based on buffer
            buffer_minutes = (promised_delivery - predicted_eta).total_seconds() / 60.0
            # Sigmoid probability
            delay_prob = round(1.0 / (1.0 + math.exp(min(10.0, max(-10.0, buffer_minutes / 60.0)))), 3)

            eta_records.append({
                "estimate_id": generate_eta_id(shipment_id, pred_time),
                "shipment_id": shipment_id,
                "prediction_timestamp": pred_time.isoformat(),
                "predicted_eta": predicted_eta.isoformat(),
                "predicted_remaining_transit_minutes": pred_remaining_minutes,
                "delay_probability": delay_prob,
                "model_version": "v1.0.0-gradient_boost",
                "model_name": "HistGradientBoostingRegressor",
                "confidence_lower_bound": (predicted_eta - timedelta(minutes=45)).isoformat(),
                "confidence_upper_bound": (predicted_eta + timedelta(minutes=45)).isoformat(),
                "primary_delay_reason": primary_delay_cause if delay_prob > 0.50 else "NONE",
                "created_at": pred_time.isoformat(),
            })

            # Shipment parent row
            shipment_records.append({
                "shipment_id": shipment_id,
                "order_id": order_id,
                "customer_id": customer_id,
                "origin_facility_id": origin_fid,
                "destination_facility_id": destination_fid,
                "service_level_id": sl_id,
                "primary_carrier_id": carrier_id,
                "status": "DELIVERED",
                "weight_kg": weight_kg,
                "volume_cbm": volume_cbm,
                "total_distance_km": round(total_shipment_dist, 2),
                "scheduled_pickup_time": scheduled_pickup.isoformat(),
                "actual_pickup_time": actual_pickup.isoformat(),
                "promised_delivery_time": promised_delivery.isoformat(),
                "actual_delivery_time": actual_delivery.isoformat(),
                "actual_delay_minutes": actual_delay_minutes,
                "is_delayed": is_delayed,
                "created_at": created_ingestion_time.isoformat(),
                "updated_at": deliv_ingestion.isoformat(),
            })

        return (
            pd.DataFrame(shipment_records),
            pd.DataFrame(leg_records),
            pd.DataFrame(event_records),
            pd.DataFrame(eta_records),
            pd.DataFrame(shipment_delay_records),
        )
