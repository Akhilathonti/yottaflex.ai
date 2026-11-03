"""
Seed Predefined Users and Initial Audit Records
Creates the 5 distinct roles with hashed credentials and audit logs.
"""
from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session

from src.database.connection import db_session_scope, init_db
from src.database.models import User, AuditRecord
from src.utils.security import PREDEFINED_USERS, hash_password
from src.utils.helpers import generate_alert_id

logger = logging.getLogger(__name__)


def seed_rbac_users():
    """Ensure all 5 role accounts exist in the database with secure hashed passwords."""
    init_db()
    with db_session_scope() as session:
        for u in PREDEFINED_USERS:
            existing = session.query(User).filter_by(email=u["email"]).first()
            if not existing:
                pwd_hash = hash_password(u["password"])
                user = User(
                    user_id=u["user_id"],
                    full_name=u["full_name"],
                    email=u["email"],
                    password_hash=pwd_hash,
                    role=u["role"],
                    customer_id=u.get("customer_id"),
                    carrier_id=u.get("carrier_id"),
                    facility_id=u.get("facility_id"),
                    account_status="ACTIVE",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(user)
                logger.info("Created user %s (%s)", u["email"], u["role"])

                # Log account creation audit record
                audit = AuditRecord(
                    audit_id=f"AUD-INIT-{u['user_id']}",
                    user_id=u["user_id"],
                    action_type="ACCOUNT_PROVISIONED",
                    entity_type="USER",
                    entity_id=u["user_id"],
                    previous_value=None,
                    new_value=u["role"],
                    action_timestamp=datetime.utcnow(),
                    action_description=f"System provisioned {u['role']} account for {u['full_name']}.",
                )
                session.add(audit)
            else:
                logger.info("User %s already exists.", u["email"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_rbac_users()
