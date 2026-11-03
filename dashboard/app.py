"""
Intelligent Logistics ETA Prediction and Delay Detection System
Production Multi-User Real-Time Dashboard with RBAC, Separate Login & Sign-Up Pages, and Navbar.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Setup project root path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DIR, MODELS_DIR
from src.database.connection import SessionLocal
from src.database.models import (
    User,
    AuditRecord,
    Shipment,
    ShipmentLeg,
    TrackingEvent,
    Facility,
    Carrier,
    FacilityQueue,
    WeatherEvent,
    ETAEstimate,
    Alert,
)
from src.utils.security import verify_password, hash_password, PREDEFINED_USERS
from src.utils.helpers import haversine_distance_km, generate_shipment_id, generate_event_id, generate_queue_id

st.set_page_config(
    page_title="LOGIX-ETA | Intelligent Logistics & Delay Detection Platform",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom Global CSS for Top Navbar and Modern App Styling
st.markdown(
    """
    <style>
    /* Top Navbar Styling */
    .top-nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        padding: 12px 24px;
        border-radius: 10px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
    }
    .nav-brand {
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.5px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .nav-user {
        display: flex;
        align-items: center;
        gap: 14px;
        font-size: 14px;
    }
    .role-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-supplier { background: #EEF2FF; color: #4338CA; border: 1px solid #C7D2FE; }
    .badge-planner { background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; }
    .badge-operator { background: #DCFCE7; color: #15803D; border: 1px solid #BBF7D0; }
    .badge-analyst { background: #F3E8FF; color: #7E22CE; border: 1px solid #E9D5FF; }
    .badge-manager { background: #FEE2E2; color: #B91C1C; border: 1px solid #FECACA; }

    /* Auth Card Styling */
    .auth-card {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 30px;
        max-width: 480px;
        margin: 20px auto;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05);
    }
    .auth-title { font-size: 24px; font-weight: 700; color: #0F172A; text-align: center; margin-bottom: 6px; }
    .auth-sub { font-size: 14px; color: #64748B; text-align: center; margin-bottom: 24px; }
    .demo-pill {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 13px;
        cursor: pointer;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=15)
def get_static_data():
    session = SessionLocal()
    try:
        facilities = [
            {"id": f.facility_id, "name": f.name, "city": f.city, "state": f.state}
            for f in session.query(Facility).all()
        ]
        carriers = [
            {"id": c.carrier_id, "name": c.name, "rating": c.on_time_rating}
            for c in session.query(Carrier).all()
        ]
        return facilities, carriers
    finally:
        session.close()


def load_model_metrics():
    metrics_path = REPORTS_DIR / "model_evaluation.json"
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ------------------------------------------------------------------------------
# Session State Management
# ------------------------------------------------------------------------------
if "current_user" not in st.session_state:
    st.session_state["current_user"] = None
if "auth_page" not in st.session_state:
    st.session_state["auth_page"] = "login"  # 'login' or 'signup'


def authenticate(email, password):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(email=email).first()
        if user and verify_password(password, user.password_hash):
            return {
                "user_id": user.user_id,
                "full_name": user.full_name,
                "email": user.email,
                "role": user.role,
                "customer_id": user.customer_id,
                "carrier_id": user.carrier_id,
                "facility_id": user.facility_id,
            }
        return None
    finally:
        session.close()


def register_user(full_name, email, password, role, customer_id=None, carrier_id=None, facility_id=None):
    session = SessionLocal()
    try:
        existing = session.query(User).filter_by(email=email).first()
        if existing:
            return False, "An account with this email address already exists."

        count = session.query(User).count()
        user_id = f"USR-{role[:4]}-{count + 1:03d}"
        pwd_hash = hash_password(password)
        cust_id = customer_id or (f"CUST-{count+1:05d}" if role == "SUPPLIER" else None)

        new_user = User(
            user_id=user_id,
            full_name=full_name,
            email=email,
            password_hash=pwd_hash,
            role=role,
            customer_id=cust_id,
            carrier_id=carrier_id,
            facility_id=facility_id,
            account_status="ACTIVE",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_login_at=datetime.utcnow(),
        )
        session.add(new_user)

        audit = AuditRecord(
            audit_id=f"AUD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{user_id[-6:]}",
            user_id=user_id,
            action_type="USER_REGISTERED",
            entity_type="USER",
            entity_id=user_id,
            previous_value=None,
            new_value=role,
            action_timestamp=datetime.utcnow(),
            action_description=f"New user registered: {full_name} ({role}).",
        )
        session.add(audit)
        session.commit()

        return True, {
            "user_id": user_id,
            "full_name": full_name,
            "email": email,
            "role": role,
            "customer_id": cust_id,
            "carrier_id": carrier_id,
            "facility_id": facility_id,
        }
    finally:
        session.close()


# ------------------------------------------------------------------------------
# TOP NAVBAR (Always Visible)
# ------------------------------------------------------------------------------
user = st.session_state["current_user"]

if user is None:
    # Public Navbar
    col_nav1, col_nav2 = st.columns([7, 3])
    with col_nav1:
        st.markdown(
            """
            <div style="font-size:20px; font-weight:700; color:#0F172A; display:flex; align-items:center; gap:8px;">
                🚚 <span>LOGIX-ETA</span>
                <span style="font-size:12px; font-weight:600; background:#E2E8F0; color:#475569; padding:2px 8px; border-radius:12px;">Enterprise Logistics ML</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_nav2:
        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("🔑 Sign In", type="primary" if st.session_state["auth_page"] == "login" else "secondary", use_container_width=True):
                st.session_state["auth_page"] = "login"
                st.rerun()
        with btn_c2:
            if st.button("📝 Sign Up", type="primary" if st.session_state["auth_page"] == "signup" else "secondary", use_container_width=True):
                st.session_state["auth_page"] = "signup"
                st.rerun()
    st.markdown("<hr style='margin-top:4px; margin-bottom:20px;'/>", unsafe_allow_html=True)
else:
    # Authenticated Top Navbar
    badge_cls = {
        "SUPPLIER": "badge-supplier",
        "LOGISTICS_PLANNER": "badge-planner",
        "CARRIER_OPERATOR": "badge-operator",
        "LOGISTICS_ANALYST": "badge-analyst",
        "OPERATIONS_MANAGER": "badge-manager",
    }.get(user["role"], "badge-supplier")

    col_nav1, col_nav2, col_nav3 = st.columns([5, 4, 1.5])
    with col_nav1:
        st.markdown(
            f"""
            <div style="font-size:18px; font-weight:700; color:#0F172A; display:flex; align-items:center; gap:10px;">
                🚚 <span>LOGIX-ETA Control Tower</span>
                <span class="role-badge {badge_cls}">{user['role'].replace('_', ' ')}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_nav2:
        st.markdown(
            f"""
            <div style="text-align:right; font-size:13px; color:#475569;">
                <b>{user['full_name']}</b> ({user['email']})
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_nav3:
        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state["current_user"] = None
            st.session_state["auth_page"] = "login"
            st.rerun()

    st.markdown("<hr style='margin-top:10px; margin-bottom:20px;'/>", unsafe_allow_html=True)


# ==============================================================================
# AUTHENTICATION: LOGIN OR SIGN UP PAGE (When user is None)
# ==============================================================================
if user is None:
    if st.session_state["auth_page"] == "login":
        # ----------------- AUTHENTIC PRODUCTION LOGIN PAGE -----------------
        _, col_login, _ = st.columns([1, 1.4, 1])

        with col_login:
            st.markdown('<div class="auth-title">Sign In</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-sub">Enter your corporate credentials to access the logistics control tower</div>', unsafe_allow_html=True)

            with st.form("login_form"):
                email = st.text_input("Corporate Email Address", placeholder="e.g. supplier@logistics.com")
                password = st.text_input("Password", placeholder="••••••••••••", type="password")
                submit = st.form_submit_button("Sign In to Control Tower", type="primary", use_container_width=True)

                if submit:
                    if not email or not password:
                        st.error("Please enter both email and password.")
                    else:
                        auth_user = authenticate(email.strip(), password.strip())
                        if auth_user:
                            st.session_state["current_user"] = auth_user
                            st.success(f"Welcome back, {auth_user['full_name']}!")
                            st.rerun()
                        else:
                            st.error("Invalid email or password. Please verify your credentials.")

            st.markdown(
                """
                <div style="text-align:center; font-size:13px; color:#64748B; margin-top:16px; margin-bottom:8px;">
                    Don't have an account yet?
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Create an Account (Sign Up)", type="secondary", use_container_width=True):
                st.session_state["auth_page"] = "signup"
                st.rerun()

            st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)

            with st.expander("📋 Pre-Configured Test Accounts (Credentials Reference)", expanded=False):
                st.markdown(
                    """
                    Below are the existing pre-configured accounts in the database for reference. Enter these credentials into the sign-in form above to access each role's dashboard:

                    | Role | Corporate Email | Password | Account Scope |
                    | :--- | :--- | :--- | :--- |
                    | **Supplier** | `supplier@logistics.com` | `Supplier@2026` | Customer `CUST-00001` |
                    | **Logistics Planner** | `planner@logistics.com` | `Planner@2026` | Fleet-wide Route Planning |
                    | **Carrier Operator** | `operator@logistics.com` | `Operator@2026` | Carrier `CAR-001` / Hub `FAC-001` |
                    | **Logistics Analyst** | `analyst@logistics.com` | `Analyst@2026` | ML Audit & Feature Store |
                    | **Operations Manager** | `manager@logistics.com` | `Manager@2026` | Executive Control Tower |
                    """
                )

    else:
        # ----------------- SEPARATE PRODUCTION SIGN UP PAGE -----------------
        col_signup, col_info = st.columns([5.5, 4.5])

        with col_signup:
            st.markdown('<div class="auth-title" style="text-align:left;">Create Your Account</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-sub" style="text-align:left;">Register a new user role in the LOGIX-ETA platform</div>', unsafe_allow_html=True)

            with st.form("signup_form"):
                full_name = st.text_input("Full Name", placeholder="e.g. Alex Smith / Acme Freight")
                email = st.text_input("Corporate Email Address", placeholder="e.g. alex@acmelogistics.com")
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    password = st.text_input("Password", placeholder="••••••••••••", type="password")
                with col_p2:
                    confirm_pwd = st.text_input("Confirm Password", placeholder="••••••••••••", type="password")

                role = st.selectbox(
                    "Select Your Logistics Role",
                    [
                        "SUPPLIER",
                        "LOGISTICS_PLANNER",
                        "CARRIER_OPERATOR",
                        "LOGISTICS_ANALYST",
                        "OPERATIONS_MANAGER",
                    ],
                    index=0,
                    format_func=lambda r: f"{r.replace('_', ' ').title()}",
                )

                # Dynamic field scoping
                facilities, carriers = get_static_data()
                carrier_opts = {c["id"]: c["name"] for c in carriers}
                fac_opts = {f["id"]: f"{f['name']} ({f['city']})" for f in facilities}

                customer_id = None
                carrier_id = None
                facility_id = None

                if role == "SUPPLIER":
                    customer_id = st.text_input("Supplier / Customer ID", value="CUST-00001", help="Scopes your shipments to this account")
                elif role == "CARRIER_OPERATOR":
                    col_op1, col_op2 = st.columns(2)
                    with col_op1:
                        carrier_id = st.selectbox("Operating Carrier Fleet", list(carrier_opts.keys()), format_func=lambda x: carrier_opts[x])
                    with col_op2:
                        facility_id = st.selectbox("Primary Warehouse Hub", list(fac_opts.keys()), format_func=lambda x: fac_opts[x])

                signup_submit = st.form_submit_button("Complete Registration & Sign In", type="primary", use_container_width=True)

                if signup_submit:
                    if not full_name or not email or not password:
                        st.error("Please fill in all required fields.")
                    elif password != confirm_pwd:
                        st.error("Passwords do not match.")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        success, res = register_user(
                            full_name=full_name.strip(),
                            email=email.strip(),
                            password=password.strip(),
                            role=role,
                            customer_id=customer_id,
                            carrier_id=carrier_id,
                            facility_id=facility_id,
                        )
                        if success:
                            st.session_state["current_user"] = res
                            st.success(f"Account created successfully for {full_name} ({role})! Redirecting to your dashboard...")
                            st.rerun()
                        else:
                            st.error(res)

            st.markdown(
                """
                <div style="text-align:center; font-size:13px; color:#64748B; margin-top:16px; margin-bottom:8px;">
                    Already have an account?
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Sign In to Existing Account", type="secondary", use_container_width=True):
                st.session_state["auth_page"] = "login"
                st.rerun()

        with col_info:
            st.markdown(
                """
                <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px; padding:24px; margin-top:10px;">
                    <div style="font-size:16px; font-weight:700; color:#0F172A; margin-bottom:12px;">🛡️ Role Responsibilities & Permissions</div>
                    <div style="display:flex; flex-direction:column; gap:14px; font-size:13px; color:#334155;">
                        <div>
                            <b>📦 Supplier</b>
                            <div style="color:#64748B;">Create freight orders, view customer-scoped shipments, monitor real-time ML ETAs, and receive delay notifications.</div>
                        </div>
                        <div>
                            <b>🗺️ Logistics Planner</b>
                            <div style="color:#64748B;">Assign carriers, create shipment legs, monitor transit routes, weather disruptions, and reroute shipments.</div>
                        </div>
                        <div>
                            <b>🏷️ Carrier / Warehouse Operator</b>
                            <div style="color:#64748B;">Scan package barcodes, record arrival/departure telemetry, log facility queue congestion, and confirm deliveries.</div>
                        </div>
                        <div>
                            <b>🔬 Logistics Analyst</b>
                            <div style="color:#64748B;">Execute automated data quality checks, evaluate model metrics (MAE, RMSE, ROC-AUC), inspect feature weights & delay factors.</div>
                        </div>
                        <div>
                            <b>👔 Operations Manager</b>
                            <div style="color:#64748B;">Oversee end-to-end network operations, monitor carrier SLAs, review high-risk shipments, and audit system activities.</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ==============================================================================
# ROLE 1: SUPPLIER DASHBOARD
# ==============================================================================
elif user["role"] == "SUPPLIER":
    st.markdown('<div class="main-title">📦 Supplier Live Portal</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-title">Account Scope: <b>{user.get("customer_id", "CUST-00001")}</b> | Role: <b>SUPPLIER</b></div>', unsafe_allow_html=True)

    session = SessionLocal()
    try:
        cust_id = user.get("customer_id", "CUST-00001")
        my_shipments = (
            session.query(Shipment)
            .filter(Shipment.customer_id == cust_id)
            .order_by(Shipment.created_at.desc())
            .all()
        )
        total_s = len(my_shipments)
        in_transit_s = sum(1 for s in my_shipments if s.status == "IN_TRANSIT")
        delivered_s = sum(1 for s in my_shipments if s.status == "DELIVERED")
        delayed_s = sum(1 for s in my_shipments if s.is_delayed)
        on_time_pct = round(((total_s - delayed_s) / max(1, total_s)) * 100.0, 1)

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("My Total Shipments", total_s)
        k2.metric("In Transit", in_transit_s)
        k3.metric("Delivered", delivered_s)
        k4.metric("Delayed", delayed_s, delta=f"{delayed_s} late" if delayed_s > 0 else "0 late", delta_color="inverse")
        k5.metric("On-Time Delivery", f"{on_time_pct}%")

        sup_tab1, sup_tab2, sup_tab3 = st.tabs(["📦 My Shipments & Live ETAs", "➕ Book New Shipment", "🔔 Delay Notifications"])

        with sup_tab1:
            if my_shipments:
                shp_options = [s.shipment_id for s in my_shipments]
                selected_shp_id = st.selectbox("Select My Shipment ID", shp_options, key="sup_shp_select")
                selected_shp = next(s for s in my_shipments if s.shipment_id == selected_shp_id)

                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Order Reference", selected_shp.order_id)
                col_m2.metric("Status", selected_shp.status)
                col_m3.metric("Service Level", selected_shp.service_level_id)
                col_m4.metric("Route Distance", f"{selected_shp.total_distance_km:.1f} km")

                # ETA Prediction
                latest_eta = (
                    session.query(ETAEstimate)
                    .filter(ETAEstimate.shipment_id == selected_shp_id)
                    .order_by(ETAEstimate.prediction_timestamp.desc())
                    .first()
                )
                if latest_eta:
                    st.markdown("#### 🎯 Machine Learning ETA Prediction Snapshot")
                    e1, e2, e3, e4 = st.columns(4)
                    e1.metric("Predicted ETA", latest_eta.predicted_eta.strftime("%Y-%m-%d %H:%M"))
                    e2.metric("Promised Delivery Target", selected_shp.promised_delivery_time.strftime("%Y-%m-%d %H:%M"))
                    e3.metric("Delay Probability", f"{latest_eta.delay_probability * 100:.1f}%")
                    e4.metric("Primary Risk Cause", str(latest_eta.primary_delay_reason))

                events = (
                    session.query(TrackingEvent)
                    .filter(TrackingEvent.shipment_id == selected_shp_id)
                    .order_by(TrackingEvent.event_sequence)
                    .all()
                )
                st.markdown("#### 🕒 Chronological Event Timeline")
                events_data = [
                    {
                        "Seq": e.event_sequence,
                        "Event": e.event_type,
                        "Location": e.event_location,
                        "Event Timestamp": e.event_timestamp.strftime("%Y-%m-%d %H:%M"),
                        "Ingestion Timestamp": e.ingestion_timestamp.strftime("%Y-%m-%d %H:%M"),
                        "Source": e.event_source,
                        "Notes": e.notes,
                    }
                    for e in events
                ]
                st.dataframe(pd.DataFrame(events_data), use_container_width=True)
            else:
                st.info("No shipments booked for your supplier ID yet. Use the 'Book New Shipment' tab to create your first order!")

        with sup_tab2:
            st.markdown("### Create New Shipment Request")
            facilities, _ = get_static_data()
            fac_options = {f["id"]: f"{f['name']} ({f['city']}, {f['state']})" for f in facilities}

            with st.form("supplier_create_form"):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    orig_fac = st.selectbox("Origin Warehouse Hub", list(fac_options.keys()), format_func=lambda x: fac_options[x], index=0)
                    weight = st.number_input("Cargo Weight (kg)", min_value=1.0, max_value=1000.0, value=30.0, step=1.0)
                    service_level = st.selectbox("Service Level Tier", ["SL-OVERNIGHT", "SL-EXPRESS", "SL-STANDARD", "SL-ECONOMY"], index=1)
                with col_f2:
                    dest_fac = st.selectbox("Destination Depot", list(fac_options.keys()), format_func=lambda x: fac_options[x], index=1)
                    volume = st.number_input("Cargo Volume (cbm)", min_value=0.01, max_value=10.0, value=0.20, step=0.05)
                    pickup_date = st.date_input("Requested Pickup Date", value=datetime.utcnow().date())

                submit_btn = st.form_submit_button("Submit Shipment Booking", type="primary")
                if submit_btn:
                    if orig_fac == dest_fac:
                        st.error("Origin and Destination facilities must be different.")
                    else:
                        from src.api.main import supplier_create_shipment
                        from src.api.schemas import SupplierCreateShipmentRequest

                        sched_pickup = datetime.combine(pickup_date, datetime.min.time()) + timedelta(hours=9)
                        prom_delivery = sched_pickup + timedelta(hours=48 if service_level == "SL-EXPRESS" else 24)

                        req = SupplierCreateShipmentRequest(
                            origin_facility_id=orig_fac,
                            destination_facility_id=dest_fac,
                            service_level_id=service_level,
                            weight_kg=float(weight),
                            volume_cbm=float(volume),
                            scheduled_pickup_time=sched_pickup.isoformat(),
                            promised_delivery_time=prom_delivery.isoformat(),
                            customer_id=cust_id,
                        )
                        res = supplier_create_shipment(req, db=session)
                        st.success(f"Shipment booked successfully! Assigned ID: **{res['shipment_id']}** (Route Distance: {res['total_distance_km']} km).")
                        st.rerun()

        with sup_tab3:
            st.markdown("### Delivery Delay Notifications for Your Account")
            my_shp_ids = [s.shipment_id for s in my_shipments]
            alerts = session.query(Alert).filter(Alert.shipment_id.in_(my_shp_ids)).all()
            if alerts:
                st.dataframe(pd.DataFrame([
                    {
                        "Alert ID": a.alert_id,
                        "Shipment ID": a.shipment_id,
                        "Severity": a.severity,
                        "Delay Reason": a.delay_reason,
                        "Predicted Delay": f"{a.predicted_delay_minutes} mins",
                        "Delay Probability": f"{a.delay_probability * 100:.1f}%",
                        "Status": a.status,
                    }
                    for a in alerts
                ]), use_container_width=True)
            else:
                st.success("No active delivery delay warnings for your shipments. All parcels currently on schedule!")
    finally:
        session.close()


# ==============================================================================
# ROLE 2: LOGISTICS PLANNER DASHBOARD
# ==============================================================================
elif user["role"] == "LOGISTICS_PLANNER":
    st.markdown('<div class="main-title">🗺️ Logistics Planning & Dispatch Workbench</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Role: <b>LOGISTICS PLANNER</b> | Linehaul Assignment, Multi-Leg Journey Routing, and Disruption Rerouting</div>', unsafe_allow_html=True)

    session = SessionLocal()
    try:
        created_shipments = session.query(Shipment).filter(Shipment.status == "CREATED").all()
        in_transit_shipments = session.query(Shipment).filter(Shipment.status == "IN_TRANSIT").all()
        high_risk_alerts = session.query(Alert).filter(Alert.status == "ACTIVE").all()
        weather_disruptions = session.query(WeatherEvent).order_by(WeatherEvent.start_time.desc()).limit(8).all()

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Pending Orders to Plan", len(created_shipments))
        p2.metric("Active In-Transit", len(in_transit_shipments))
        p3.metric("Active Delay Alerts", len(high_risk_alerts))
        p4.metric("Active Weather Events", len(weather_disruptions))

        plan_tab1, plan_tab2, plan_tab3 = st.tabs(["🚀 Assign Carrier & Route", "⚠️ Delay Alerts & Exceptions", "🌩️ Weather Disruption Corridors"])

        with plan_tab1:
            st.subheader("Unassigned Shipment Orders")
            if created_shipments:
                plan_shp_id = st.selectbox("Select Shipment Order to Plan", [s.shipment_id for s in created_shipments], key="plan_sel")
                target_shp = next(s for s in created_shipments if s.shipment_id == plan_shp_id)

                col_det1, col_det2, col_det3 = st.columns(3)
                col_det1.info(f"**Origin**: {target_shp.origin_facility_id}\n\n**Destination**: {target_shp.destination_facility_id}")
                col_det2.info(f"**Distance**: {target_shp.total_distance_km:.1f} km\n\n**Weight**: {target_shp.weight_kg} kg")
                col_det3.info(f"**Service Level**: {target_shp.service_level_id}\n\n**Promised**: {target_shp.promised_delivery_time.strftime('%Y-%m-%d %H:%M')}")

                facilities, carriers = get_static_data()
                carrier_opts = {c["id"]: f"{c['name']} (Rating: {c['rating'] * 100:.0f}%)" for c in carriers}
                fac_opts = {f["id"]: f"{f['name']} ({f['city']})" for f in facilities}

                with st.form("assign_carrier_form"):
                    selected_carrier_id = st.selectbox("Assign Primary Linehaul Carrier", list(carrier_opts.keys()), format_func=lambda x: carrier_opts[x])
                    intermediate_fac = st.selectbox("Optional Cross-Dock Hub (for 2-Leg Routing)", ["None"] + list(fac_opts.keys()), format_func=lambda x: "Direct Route (No Cross-dock)" if x == "None" else fac_opts[x])

                    assign_btn = st.form_submit_button("Confirm Routing & Dispatch Shipment", type="primary")
                    if assign_btn:
                        from src.api.main import planner_assign_route
                        from src.api.schemas import PlannerAssignCarrierRequest

                        req = PlannerAssignCarrierRequest(
                            shipment_id=target_shp.shipment_id,
                            carrier_id=selected_carrier_id,
                            intermediate_facility_id=intermediate_fac if intermediate_fac != "None" else None,
                        )
                        res = planner_assign_route(req, db=session)
                        st.success(f"Carrier **{selected_carrier_id}** assigned to {target_shp.shipment_id}! Status moved to IN_TRANSIT.")
                        st.rerun()
            else:
                st.success("All shipment requests have been planned and dispatched! No pending orders.")

        with plan_tab2:
            st.subheader("Active Delay Alerts for Planner Resolution")
            if high_risk_alerts:
                alerts_data = [
                    {
                        "Alert ID": a.alert_id,
                        "Shipment": a.shipment_id,
                        "Severity": a.severity,
                        "Delay Reason": a.delay_reason,
                        "Risk Prob": f"{a.delay_probability * 100:.1f}%",
                        "Est Delay": f"{a.predicted_delay_minutes}m",
                        "Recommended Action": a.recommended_action,
                    }
                    for a in high_risk_alerts[:15]
                ]
                st.dataframe(pd.DataFrame(alerts_data), use_container_width=True)
            else:
                st.info("No active alerts currently flagged.")

        with plan_tab3:
            st.subheader("Regional Weather Disruption Corridors")
            w_data = [
                {
                    "Event ID": w.weather_event_id,
                    "Type": w.event_type,
                    "Severity": w.severity,
                    "Affected Region": w.affected_region,
                    "Start Time": w.start_time.strftime("%Y-%m-%d %H:%M"),
                    "End Time": w.end_time.strftime("%Y-%m-%d %H:%M"),
                    "Winds": f"{w.wind_speed_mph} mph",
                }
                for w in weather_disruptions
            ]
            st.dataframe(pd.DataFrame(w_data), use_container_width=True)
    finally:
        session.close()


# ==============================================================================
# ROLE 3: CARRIER / WAREHOUSE OPERATOR DASHBOARD
# ==============================================================================
elif user["role"] == "CARRIER_OPERATOR":
    st.markdown('<div class="main-title">🏷️ Carrier & Warehouse Operator Station</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-title">Role: <b>CARRIER / WAREHOUSE OPERATOR</b> | Assigned Fleet: <b>{user.get("carrier_id", "CAR-001")}</b> | Hub: <b>{user.get("facility_id", "FAC-001")}</b></div>', unsafe_allow_html=True)

    session = SessionLocal()
    try:
        my_carrier_id = user.get("carrier_id", "CAR-001")
        my_facility_id = user.get("facility_id", "FAC-001")

        active_carrier_shipments = (
            session.query(Shipment)
            .filter(Shipment.primary_carrier_id == my_carrier_id, Shipment.status.in_(["IN_TRANSIT", "OUT_FOR_DELIVERY"]))
            .all()
        )
        delivered_count = session.query(Shipment).filter(Shipment.primary_carrier_id == my_carrier_id, Shipment.status == "DELIVERED").count()

        op1, op2, op3 = st.columns(3)
        op1.metric("Active Fleet Linehauls", len(active_carrier_shipments))
        op2.metric("Delivered by Carrier", delivered_count)
        op3.metric("Facility Assigned", my_facility_id)

        op_tab1, op_tab2 = st.tabs(["🏷️ Barcode Scan & Telemetry Entry", "🏭 Yard Dock & Facility Queue Logger"])

        with op_tab1:
            st.subheader("Barcode Telemetry Station")
            st.info("💡 Every scan automatically captures separate physical `event_timestamp` and database `ingestion_timestamp`. Ingestion is never backdated.")

            if active_carrier_shipments:
                scan_shp_id = st.selectbox("Scan / Select Shipment ID", [s.shipment_id for s in active_carrier_shipments], key="op_scan_sel")
                scan_target = next(s for s in active_carrier_shipments if s.shipment_id == scan_shp_id)

                with st.form("operator_scan_form"):
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        event_type = st.selectbox(
                            "Operational Event Type",
                            [
                                "ARRIVED_AT_FACILITY",
                                "SORTING_COMPLETED",
                                "DEPARTED_FACILITY",
                                "IN_TRANSIT_SCAN",
                                "OUT_FOR_DELIVERY",
                                "DELIVERED",
                                "EXCEPTION",
                            ],
                        )
                        location_text = st.text_input("Event Location Description", value=f"Facility {my_facility_id}, Inbound Bay 3")
                    with col_s2:
                        event_source = st.selectbox("Scanner Device Source", ["MANUAL_SCAN", "MOBILE_APP", "EDI", "GPS_TRACKER"])
                        notes = st.text_input("Operational Dispatch Notes", value="Scanned on inbound conveyor roller.")

                    record_scan_btn = st.form_submit_button("Record Physical Barcode Scan", type="primary")

                    if record_scan_btn:
                        from src.api.main import operator_record_event
                        from src.api.schemas import OperatorRecordEventRequest

                        req = OperatorRecordEventRequest(
                            shipment_id=scan_target.shipment_id,
                            event_type=event_type,
                            facility_id=my_facility_id,
                            event_location=location_text,
                            event_source=event_source,
                            notes=notes,
                        )
                        res = operator_record_event(req, db=session)
                        st.success(f"Scan recorded! Event ID: **{res['event_id']}** (Sequence #{res['event_sequence']}). Updated Status: **{res['shipment_status']}**.")
                        st.rerun()
            else:
                st.info("No active shipments currently assigned to your carrier fleet.")

        with op_tab2:
            st.subheader("Log Yard & Dock Queue Congestion")
            with st.form("queue_update_form"):
                col_q1, col_q2 = st.columns(2)
                with col_q1:
                    queue_len = st.number_input("Trailers / Shipments Waiting in Yard", min_value=0, max_value=250, value=30, step=1)
                    avg_wait = st.number_input("Average Unloading Wait Time (mins)", min_value=0, max_value=600, value=70, step=5)
                with col_q2:
                    dock_util = st.slider("Dock Utilization Rate (%)", 0.0, 100.0, 80.0, 1.0)
                    proc_status = st.selectbox("Congestion Level", ["NORMAL", "MODERATE_CONGESTION", "SEVERE_CONGESTION"])

                update_q_btn = st.form_submit_button("Log Queue Telemetry", type="primary")
                if update_q_btn:
                    from src.api.main import operator_update_queue
                    from src.api.schemas import OperatorUpdateQueueRequest

                    req = OperatorUpdateQueueRequest(
                        facility_id=my_facility_id,
                        queue_length=int(queue_len),
                        average_wait_time_minutes=int(avg_wait),
                        dock_utilization_pct=float(dock_util),
                        processing_status=proc_status,
                    )
                    res = operator_update_queue(req, db=session)
                    st.success(f"Yard queue logged for **{my_facility_id}**! Status: {res['processing_status']} (Queue ID: {res['queue_id']}).")
                    st.rerun()
    finally:
        session.close()


# ==============================================================================
# ROLE 4: LOGISTICS ANALYST DASHBOARD
# ==============================================================================
elif user["role"] == "LOGISTICS_ANALYST":
    st.markdown('<div class="main-title">🔬 Logistics Data Science & Quality Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Role: <b>LOGISTICS ANALYST</b> | Data Quality Auditing, Model Benchmarking, and Prediction Residuals</div>', unsafe_allow_html=True)

    metrics = load_model_metrics()

    an_tab1, an_tab2, an_tab3 = st.tabs(["🔬 Data Quality & Validation", "🤖 ML Model Performance", "📈 Error Residuals & Leakage"])

    with an_tab1:
        st.subheader("Data Validation Suite & Anomaly Detection")
        if st.button("Run Automated Data Quality Validation Suite", type="primary"):
            from src.data_validation.validator import DataValidator
            validator = DataValidator()
            report = validator.run_all_validations()
            st.success(f"Validation executed! {report.total_checks} checks executed. {report.passed_checks} passed. {report.anomaly_detected_count} deliberate anomalies detected.")

        val_json_path = REPORTS_DIR / "validation_summary.json"
        if val_json_path.exists():
            with open(val_json_path, "r", encoding="utf-8") as f:
                val_data = json.load(f)

            c_v1, c_v2, c_v3, c_v4 = st.columns(4)
            c_v1.metric("Total Quality Checks", val_data.get("total_checks", 0))
            c_v2.metric("Passed Checks", val_data.get("passed_checks", 0))
            c_v3.metric("Failed (Anomalies)", val_data.get("failed_checks", 0))
            c_v4.metric("Warnings", val_data.get("warning_count", 0))

            st.markdown("#### Detected Anomalies & Integrity Violations")
            issues_df = pd.DataFrame(val_data.get("issues", []))
            if not issues_df.empty:
                st.dataframe(issues_df[["check_category", "check_name", "severity", "table_name", "affected_entity_id", "description"]], use_container_width=True)

    with an_tab2:
        st.subheader("Machine Learning Benchmark Model Comparison")
        if metrics:
            reg_comp = metrics.get("regression_comparison", {})
            champ = metrics.get("champion_model", {})

            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Champion MAE", f"{champ.get('mae_minutes', 0):.1f} mins")
            mc2.metric("Accuracy ≤ 30m", f"{champ.get('accuracy_within_30m_pct', 0):.1f}%")
            mc3.metric("Delay F1-Score", f"{champ.get('f1_score', 0):.3f}")
            mc4.metric("Delay ROC-AUC", f"{champ.get('roc_auc', 0):.3f}")

            reg_list = []
            for name, m in reg_comp.items():
                reg_list.append({
                    "Architecture": name.replace("_", " ").title(),
                    "MAE (mins)": m.get("mae_minutes"),
                    "RMSE (mins)": m.get("rmse_minutes"),
                    "MedAE (mins)": m.get("median_ae_minutes"),
                    "Acc ≤ 15m": f"{m.get('accuracy_within_15m_pct')}%",
                    "Acc ≤ 30m": f"{m.get('accuracy_within_30m_pct')}%",
                    "Acc ≤ 60m": f"{m.get('accuracy_within_60m_pct')}%",
                })
            st.dataframe(pd.DataFrame(reg_list), use_container_width=True)

            col_chart_m1, col_chart_m2 = st.columns(2)
            with col_chart_m1:
                fig_bar = px.bar(pd.DataFrame(reg_list), x="Architecture", y="MAE (mins)", color="Architecture", title="Mean Absolute Error (Lower is Better)")
                st.plotly_chart(fig_bar, use_container_width=True)
            with col_chart_m2:
                feat_imp = metrics.get("feature_importances", [])
                if feat_imp:
                    fig_feat = px.bar(pd.DataFrame(feat_imp).head(8), x="importance", y="feature", orientation="h", title="Top Predictive Feature Importances")
                    st.plotly_chart(fig_feat, use_container_width=True)
        else:
            st.warning("Model metrics report not found. Run model training first.")

    with an_tab3:
        st.subheader("Point-in-Time Temporal Leakage Verification")
        st.info("Temporal Invariant: for every prediction snapshot at time T, telemetry features only reference events where ingestion_timestamp <= T. Ground-truth target columns are strictly quarantined.")

        feat_path = PROCESSED_DATA_DIR / "features.csv"
        if feat_path.exists():
            feat_df = pd.read_csv(feat_path)
            st.markdown(f"**Loaded Processed Features**: `{len(feat_df)}` rows.")
            st.dataframe(feat_df.head(10), use_container_width=True)


# ==============================================================================
# ROLE 5: OPERATIONS MANAGER DASHBOARD
# ==============================================================================
elif user["role"] == "OPERATIONS_MANAGER":
    st.markdown('<div class="main-title">👔 Executive Operations Control Tower</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Role: <b>OPERATIONS MANAGER</b> | Enterprise Network KPIs, Carrier Benchmarking & Complete Audit Trail</div>', unsafe_allow_html=True)

    session = SessionLocal()
    try:
        total_shipments = session.query(Shipment).count()
        delayed_shipments = session.query(Shipment).filter(Shipment.is_delayed == True).count()
        in_transit = session.query(Shipment).filter(Shipment.status == "IN_TRANSIT").count()
        on_time_pct = round(((total_shipments - delayed_shipments) / max(1, total_shipments)) * 100.0, 1)
        active_alerts_count = session.query(Alert).filter(Alert.status == "ACTIVE").count()

        om1, om2, om3, om4, om5 = st.columns(5)
        om1.metric("Network Shipments", f"{total_shipments:,}")
        om2.metric("In Transit", f"{in_transit:,}")
        om3.metric("Delayed Shipments", f"{delayed_shipments:,}", delta=f"{delayed_shipments} late", delta_color="inverse")
        om4.metric("On-Time SLA Rate", f"{on_time_pct}%")
        om5.metric("Active Exceptions", active_alerts_count)

        mgr_tab1, mgr_tab2, mgr_tab3 = st.tabs(["📊 Network Performance", "🏆 Carrier Benchmarks", "📜 Immutable System Audit Log"])

        with mgr_tab1:
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.subheader("Delivery Status Breakdown")
                status_df = pd.DataFrame(
                    session.query(Shipment.status, Shipment.shipment_id).all(),
                    columns=["Status", "ID"],
                ).groupby("Status").count().reset_index()
                status_df.columns = ["Status", "Count"]
                fig_st = px.pie(status_df, names="Status", values="Count", hole=0.45, color="Status", color_discrete_map={"DELIVERED": "#10B981", "IN_TRANSIT": "#3B82F6", "CREATED": "#F59E0B"})
                st.plotly_chart(fig_st, use_container_width=True)

            with col_chart2:
                st.subheader("Active Operational Exception Alerts")
                alerts = session.query(Alert).filter(Alert.status == "ACTIVE").limit(10).all()
                if alerts:
                    st.dataframe(pd.DataFrame([
                        {"ID": a.alert_id, "Shipment": a.shipment_id, "Severity": a.severity, "Reason": a.delay_reason, "Action": a.recommended_action}
                        for a in alerts
                    ]), use_container_width=True)
                else:
                    st.info("No active exceptions requiring escalation.")

        with mgr_tab2:
            st.subheader("Carrier Fleet Ranking & On-Time Compliance")
            from src.api.main import get_carrier_performance
            carrier_perf = get_carrier_performance(db=session)
            carrier_df = pd.DataFrame([c.dict() if hasattr(c, "dict") else c.model_dump() for c in carrier_perf]).sort_values("on_time_percentage", ascending=False)
            st.dataframe(carrier_df[["name", "service_type", "total_shipments", "on_time_percentage", "average_delay_minutes"]], use_container_width=True)

            fig_c = px.bar(carrier_df, x="name", y="on_time_percentage", color="on_time_percentage", color_continuous_scale="Viridis", title="Carrier On-Time Delivery Compliance (%)")
            st.plotly_chart(fig_c, use_container_width=True)

        with mgr_tab3:
            st.subheader("Immutable System Audit Trail (Activity Logs)")
            st.info("🛡️ Complete audit traceability: every user login, shipment booking, carrier assignment, barcode scan, and queue update is permanently logged.")

            audit_records = (
                session.query(AuditRecord)
                .order_by(AuditRecord.action_timestamp.desc())
                .limit(50)
                .all()
            )
            audit_df = pd.DataFrame([
                {
                    "Audit ID": a.audit_id,
                    "User ID": a.user_id,
                    "Action Type": a.action_type,
                    "Entity": f"{a.entity_type} ({a.entity_id})",
                    "Timestamp": a.action_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "Description": a.action_description,
                }
                for a in audit_records
            ])
            st.dataframe(audit_df, use_container_width=True)
    finally:
        session.close()
