"""
Security and Authentication Utilities for RBAC
Provides PBKDF2-SHA256 password hashing, token validation, and predefined role configurations.
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# Salt length and iterations
SALT_BYTES = 16
PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """Generate a secure PBKDF2-HMAC-SHA256 hash formatted as salt$hash."""
    salt = secrets.token_bytes(SALT_BYTES)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against salt$hash string."""
    try:
        salt_hex, key_hex = hashed_password.split("$")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            PBKDF2_ITERATIONS,
        )
        return hmac.compare_digest(expected_key, actual_key)
    except Exception:
        return False


# Predefined Users for all 5 Roles
PREDEFINED_USERS = [
    {
        "user_id": "USR-SUPPLIER-01",
        "full_name": "Acme Global Supplier Dispatch",
        "email": "supplier@logistics.com",
        "password": "Supplier@2026",
        "role": "SUPPLIER",
        "customer_id": "CUST-00001",
        "carrier_id": None,
        "facility_id": None,
        "description": "Supplier user creating shipments and tracking customer order ETAs.",
    },
    {
        "user_id": "USR-PLANNER-01",
        "full_name": "Jordan Vance (Senior Logistics Planner)",
        "email": "planner@logistics.com",
        "password": "Planner@2026",
        "role": "LOGISTICS_PLANNER",
        "customer_id": None,
        "carrier_id": None,
        "facility_id": None,
        "description": "Logistics planner assigning linehaul carriers, multi-leg routes, and resolving exceptions.",
    },
    {
        "user_id": "USR-OPERATOR-01",
        "full_name": "Marcus Diaz (Chicago Central Hub Operator)",
        "email": "operator@logistics.com",
        "password": "Operator@2026",
        "role": "CARRIER_OPERATOR",
        "customer_id": None,
        "carrier_id": "CAR-001",
        "facility_id": "FAC-001",
        "description": "Warehouse & carrier operator executing barcode scans and logging yard dock queues.",
    },
    {
        "user_id": "USR-ANALYST-01",
        "full_name": "Dr. Elena Chen (Lead Data & ML Analyst)",
        "email": "analyst@logistics.com",
        "password": "Analyst@2026",
        "role": "LOGISTICS_ANALYST",
        "customer_id": None,
        "carrier_id": None,
        "facility_id": None,
        "description": "Data analyst monitoring data quality, validating schemas, and auditing model predictions.",
    },
    {
        "user_id": "USR-MANAGER-01",
        "full_name": "Sarah Jenkins (Director of Global Logistics Operations)",
        "email": "manager@logistics.com",
        "password": "Manager@2026",
        "role": "OPERATIONS_MANAGER",
        "customer_id": None,
        "carrier_id": None,
        "facility_id": None,
        "description": "Operations manager tracking executive network KPIs, critical alerts, and operational audit trail.",
    },
]
