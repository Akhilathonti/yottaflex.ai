"""
Utility Helpers: Haversine distance calculation, deterministic ID generators, serialization.
"""
import math
from datetime import datetime
from typing import Union


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in kilometers."""
    r = 6371.0  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


def generate_shipment_id(index: int, year: int = 2026) -> str:
    """Format: SHP-2026-000001"""
    return f"SHP-{year}-{index:06d}"


def generate_leg_id(shipment_id: str, leg_seq: int) -> str:
    """Format: LEG-SHP-2026-000001-01"""
    return f"LEG-{shipment_id}-{leg_seq:02d}"


def generate_event_id(shipment_id: str, event_seq: int) -> str:
    """Format: EVT-SHP-2026-000001-000001"""
    return f"EVT-{shipment_id}-{event_seq:06d}"


def generate_eta_id(shipment_id: str, timestamp: datetime) -> str:
    """Format: ETA-SHP-2026-000001-20261102T120000"""
    ts_str = timestamp.strftime("%Y%m%dT%H%M%S")
    return f"ETA-{shipment_id}-{ts_str}"


def generate_alert_id(index: int, year: int = 2026) -> str:
    """Format: ALT-2026-000001"""
    return f"ALT-{year}-{index:06d}"


def generate_queue_id(facility_id: str, timestamp: datetime) -> str:
    """Format: QUE-FAC-001-20261102T080000"""
    ts_str = timestamp.strftime("%Y%m%dT%H%M%S")
    return f"QUE-{facility_id}-{ts_str}"


def generate_weather_id(index: int, year: int = 2026) -> str:
    """Format: WTH-2026-0001"""
    return f"WTH-{year}-{index:04d}"


def format_iso(dt: Union[datetime, str, None]) -> str:
    """Return ISO format string."""
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.isoformat()
