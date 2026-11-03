"""
Central Configuration for Intelligent Logistics ETA Prediction System
"""
import os
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
GROUND_TRUTH_DIR = DATA_DIR / "ground_truth"
EXPORTS_DIR = DATA_DIR / "exports"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"
DOCS_DIR = PROJECT_ROOT / "docs"

# Ensure all primary runtime directories exist
for directory in [
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    GROUND_TRUTH_DIR,
    EXPORTS_DIR,
    MODELS_DIR,
    REPORTS_DIR,
    DOCS_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

# Deterministic Reproducibility
RANDOM_SEED = int(os.getenv("RANDOM_SEED", 20261022))

# Database Configuration
# Defaults to local SQLite file for immediate zero-config execution; seamlessly works with PostgreSQL
DEFAULT_SQLITE_PATH = DATA_DIR / "logistics.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}")

# Business Logic Parameters
DEFAULT_DELAY_TOLERANCE_MINUTES = 30
HIGH_RISK_DELAY_PROBABILITY_THRESHOLD = 0.60
CRITICAL_RISK_DELAY_PROBABILITY_THRESHOLD = 0.85
STALE_TRACKING_EVENT_HOURS_THRESHOLD = 18.0
FACILITY_CONGESTION_QUEUE_THRESHOLD = 45

# Service Level Definitions
SERVICE_LEVELS_CONFIG = [
    {
        "service_level_id": "SL-OVERNIGHT",
        "name": "Priority Overnight Air",
        "code": "OVERNIGHT",
        "target_delivery_hours": 24,
        "guaranteed": True,
        "delay_tolerance_minutes": 15,
        "description": "Next business day delivery by 10:30 AM",
    },
    {
        "service_level_id": "SL-EXPRESS",
        "name": "Expedited 2-Day Air/Ground",
        "code": "EXPRESS",
        "target_delivery_hours": 48,
        "guaranteed": True,
        "delay_tolerance_minutes": 30,
        "description": "Two business day delivery by end of day",
    },
    {
        "service_level_id": "SL-STANDARD",
        "name": "Standard Regional Ground",
        "code": "STANDARD",
        "target_delivery_hours": 72,
        "guaranteed": False,
        "delay_tolerance_minutes": 60,
        "description": "Three to four business day standard ground delivery",
    },
    {
        "service_level_id": "SL-ECONOMY",
        "name": "Economy Freight & Parcel",
        "code": "ECONOMY",
        "target_delivery_hours": 120,
        "guaranteed": False,
        "delay_tolerance_minutes": 120,
        "description": "Five business day deferred economy freight transit",
    },
]

# Standard Delay Reasons Taxonomy
DELAY_REASONS_CONFIG = [
    {
        "reason_id": "RZN-001",
        "code": "WEATHER_DISRUPTION",
        "category": "ENVIRONMENTAL",
        "description": "Severe weather conditions (snowstorm, blizzard, heavy flooding, high winds) slowing transit or grounding flights.",
    },
    {
        "reason_id": "RZN-002",
        "code": "FACILITY_CONGESTION",
        "category": "OPERATIONAL",
        "description": "Inbound dock queue backlog or sorting facility capacity overload exceeding operational threshold.",
    },
    {
        "reason_id": "RZN-003",
        "code": "CARRIER_PERFORMANCE",
        "category": "CARRIER",
        "description": "Carrier mechanical breakdown, linehaul driver shortage, or transit lane underperformance.",
    },
    {
        "reason_id": "RZN-004",
        "code": "ROUTE_DEVIATION",
        "category": "OPERATIONAL",
        "description": "Detour or misdirection resulting in increased transit distance and elapsed leg duration.",
    },
    {
        "reason_id": "RZN-005",
        "code": "DELAYED_SCANS",
        "category": "DATA_QUALITY",
        "description": "Telemetry scan batching or delayed EDI transmission causing stale visibility in transit status.",
    },
    {
        "reason_id": "RZN-006",
        "code": "MISSED_FACILITY_CUTOFF",
        "category": "OPERATIONAL",
        "description": "Shipment arrived at facility after daily outbound sorting cutoff time, holding package until next cycle.",
    },
    {
        "reason_id": "RZN-007",
        "code": "OPERATIONAL_HANDLING_DELAY",
        "category": "OPERATIONAL",
        "description": "Damaged barcode re-labeling, hazmat inspection, or custom manual audit requirement.",
    },
    {
        "reason_id": "RZN-008",
        "code": "UNKNOWN",
        "category": "OTHER",
        "description": "Unclassified anomaly or missing sensor telemetry explanation.",
    },
]
