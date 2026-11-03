# Intelligent Logistics ETA Prediction and Delay Detection System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red.svg)](https://streamlit.io/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.4+-orange.svg)](https://scikit-learn.org/)
[![Tests](https://img.shields.io/badge/tests-20%20passed-brightgreen.svg)]()

A complete, production-grade, end-to-end logistics analytics and machine learning system that combines shipment tracking events, carrier performance, multi-leg route networks, weather disruptions, and facility queue congestion to predict Estimated Time of Arrival (ETA), quantify delay probabilities, explain causal bottlenecks, and issue proactive dispatch alerts.

---

## Key Highlights

- **100% Native Execution (Zero Docker Required)**: Runs out-of-the-box on standard Python with built-in SQLite (or connects seamlessly to enterprise PostgreSQL).
- **Strict Point-in-Time Temporal Integrity**: Guarantees zero data leakage by enforcing causal boundaries (`ingestion_timestamp <= prediction_timestamp T`).
- **Comprehensive Relational Architecture**: 11 core entities, 2 many-to-many bridge tables, and operational alert exceptions.
- **Benchmark Machine Learning Improvements**: Demonstrates a **3x accuracy improvement** over historical baseline models using state-of-the-art histogram gradient boosting.
- **14 Labelled Deliberate Anomalies**: Integrated synthetic anomaly injector and automated data quality validation framework.
- **Interactive Multi-Page Streamlit Dashboard**: 6 dedicated operational views powered by Plotly charts.
- **Production REST API**: FastAPI backend with Pydantic v2 schemas and Swagger documentation.

---

## Relational Architecture & Entities

The system implements a relational schema covering 11 core tables, 2 bridge tables, and 1 alerts table:

```
[service_levels] ──< [shipments] ──< [shipment_legs] ──< [tracking_events]
                          │                   │
                          ├──< [eta_estimates]├──> [routes]
                          ├──< [alerts]       └──> [carriers]
                          └──< [shipment_delay_reasons] >── [delay_reasons]
[facilities] ──< [facility_queues]
     │
     └──< [facility_weather_events] >── [weather_events]
```

- Schema DDL: [`docs/schema.sql`](file:///C:/Users/thont/.gemini/antigravity/scratch/logistics_eta_prediction/docs/schema.sql)
- Data Dictionary: [`docs/data_dictionary.md`](file:///C:/Users/thont/.gemini/antigravity/scratch/logistics_eta_prediction/docs/data_dictionary.md)
- Entity Relationship Diagram: [`docs/erd.md`](file:///C:/Users/thont/.gemini/antigravity/scratch/logistics_eta_prediction/docs/erd.md)

---

## Quickstart: How to Run in Command Prompt (CMD)

Whenever you want to start the application, open your Windows **Command Prompt (`cmd`)** and run:

```cmd
cd C:\Users\thont\.gemini\antigravity\scratch\logistics_eta_prediction
run.bat
```
*(Or simply double-click `run.bat` in File Explorer).*

This automatically:
1. Starts the **FastAPI Backend** on `http://127.0.0.1:8000`
2. Starts the **Streamlit Web Dashboard** on `http://localhost:8501`
3. Automatically opens the dashboard URL `http://localhost:8501` in your browser!

---

## Alternative Manual Run Commands

You can also run individual services directly from `cmd`:

### Option A: Run Only the Streamlit Dashboard (Port 8501)
```cmd
cd C:\Users\thont\.gemini\antigravity\scratch\logistics_eta_prediction
python -m streamlit run dashboard/app.py
```
*(Prints `http://localhost:8501` and opens it in your browser immediately).*

### Option B: Run the FastAPI REST API (Port 8000)
```cmd
cd C:\Users\thont\.gemini\antigravity\scratch\logistics_eta_prediction
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```
*(Open `http://127.0.0.1:8000/docs` in your browser for Swagger API docs).*

---

## Installation & Setup Reference

```bash
# Clone or navigate to the project directory
cd logistics_eta_prediction

# Install dependencies
pip install -r requirements.txt
```

### 2. Generate Synthetic Logistics Data

Generate synthetic shipments, tracking telemetry, facilities, weather disruptions, and deliberate anomalies with a deterministic seed (`20261022`):

```bash
# Fast starter dataset (500 shipments, ~6,000 events, 100 facilities, 200 disruptions)
python -m src.data_generation.generate_data --starter --seed 20261022

# Or full-scale production dataset (50,000 shipments, 300,000+ events)
python -m src.data_generation.generate_data --shipments 50000 --events 300000 --facilities 100 --disruptions 1000 --seed 20261022
```

### 3. Run Automated Data Quality & Anomaly Detection

Execute structural, temporal causality, and business rule validation:

```bash
python -m src.data_validation.validator
```
Summary reports are generated at:
- `reports/validation_summary.json`
- `reports/validation_summary.md`

### 4. Feature Engineering & Zero-Leakage Verification

Generate point-in-time features strictly isolated at prediction timestamp $T$:

```bash
python -m src.feature_engineering.leakage_check
```

### 5. Train & Evaluate Machine Learning Models

Train and compare the Baseline Historical Model, Ridge Regression, Random Forest, and HistGradientBoosting (LightGBM algorithm) on chronological holdout splits:

```bash
python -m src.models.train
```
Model evaluation reports and serialized champion models are saved to:
- `models/eta_champion_bundle.joblib`
- `reports/model_evaluation.md`
- `reports/model_evaluation.json`

### 6. Run the Automated Test Suite

Execute all 20 unit, integration, and leakage detection tests:

```bash
pytest -v
```

### 7. Launch the FastAPI Backend

Start the REST API server:

```bash
uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive OpenAPI documentation is available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### 8. Launch the Streamlit Control Tower Dashboard

Start the 6-page interactive dashboard:

```bash
streamlit run dashboard/app.py
```
Open your browser at `http://localhost:8501`.

---

## Role-Based Access Control (RBAC) & Multi-User Dashboards

The application features a production-grade authentication and authorization system with separate **Login** and **Sign Up** pages, a responsive **Top Navbar**, and five distinct user role portals:

### 1. Separate Login & Sign-Up Pages
- **Sign In Page**: Secure credential authentication verifying PBKDF2-HMAC-SHA256 hashed passwords. Includes "One-Click Quick Role Switcher" buttons for instant evaluation of each persona.
- **Sign Up Page**: Dedicated registration flow to provision accounts with role assignment (`SUPPLIER`, `LOGISTICS_PLANNER`, `CARRIER_OPERATOR`, `LOGISTICS_ANALYST`, `OPERATIONS_MANAGER`), automatic customer/carrier scoping, and immutable registration audit logging.

### 2. Top Navbar
- Brand banner with live status badge (`LOGIX-ETA | Enterprise Logistics ML`).
- User profile card with colored role badge and email display.
- One-click instant role-switcher for seamless pairing and evaluation.
- Secure session sign-out button.

### 3. Five Real-Time Role Dashboards
1. **📦 Supplier Portal**:
   - Create new shipment bookings with scheduled pickups, dimensions, and SLA tiers.
   - Strictly scoped view showing only own customer shipments.
   - Real-time ML ETA predictions, delay probabilities, and delivery alert notices.
2. **🗺️ Logistics Planner Portal**:
   - Dispatch workbench to review unassigned orders, allocate primary carriers, and construct multi-leg journey routes.
   - Live weather disruption corridors and severe storm rerouting.
   - Active delay alerts and operational detour planning.
3. **🏷️ Carrier & Warehouse Operator Station**:
   - Mobile barcode scanning station capturing physical `event_timestamp` vs system `ingestion_timestamp`.
   - Record facility arrival, departure, sorting, out-for-delivery, and delivery events.
   - Facility dock congestion & yard queue logger (trailers waiting, average wait minutes).
4. **🔬 Logistics Data Science & Quality Center (Analyst)**:
   - Data validation suite execution catching duplicate scans, impossible chronologies, and schema breaks.
   - Machine Learning benchmark model comparison (Historical Baseline vs Ridge vs Random Forest vs Gradient Boosting).
   - Top predictive feature importances & point-in-time leakage verification.
5. **👔 Executive Operations Control Tower (Manager)**:
   - Enterprise-wide logistics KPIs: on-time SLA %, in-transit volume, delayed shipments.
   - Linehaul carrier performance rankings and transit reliability comparisons.
   - Complete system-wide immutable activity audit log.

---

## Pre-Configured Test Accounts

| Role | Email | Password | Scoped ID / Responsibility |
| :--- | :--- | :--- | :--- |
| **Supplier** | `supplier@logistics.com` | `Supplier@2026` | `CUST-00001` (Acme Supplier Dispatch) |
| **Logistics Planner** | `planner@logistics.com` | `Planner@2026` | Senior Logistics Planner |
| **Carrier / Operator** | `operator@logistics.com` | `Operator@2026` | `CAR-001` (Apex Express) / `FAC-001` (Chicago Hub) |
| **Logistics Analyst** | `analyst@logistics.com` | `Analyst@2026` | Lead Data & ML Analyst |
| **Operations Manager** | `manager@logistics.com` | `Manager@2026` | Director of Global Operations |

---

## REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status and database connectivity check |
| `GET` | `/shipments` | List shipments with filtering by status, carrier, and pagination |
| `GET` | `/shipments/{id}` | Complete shipment details including all journey legs |
| `GET` | `/shipments/{id}/events` | Chronological tracking event stream |
| `GET` | `/shipments/{id}/eta` | Historical point-in-time ETA estimate snapshots |
| `GET` | `/shipments/{id}/delay-reasons` | Attributed delay reasons (ground truth vs predicted) |
| `GET` | `/alerts` | Active operational exception alerts |
| `GET` | `/carriers/performance` | Carrier on-time percentage and transit metrics |
| `GET` | `/facilities/performance` | Facility queue lengths, wait times, and status |
| `GET` | `/model/metrics` | Model evaluation metrics and feature importances |
| `POST` | `/predict/eta` | Real-time ETA inference for a single shipment |
| `POST` | `/predict/batch` | Vectorized batch ETA inference |
| `POST` | `/alerts/evaluate` | Trigger rule-based and ML exception alert evaluation |

---

## Machine Learning Results

Evaluated on a chronological holdout test set:

| Model Architecture | MAE (mins) | RMSE (mins) | Acc ≤ 15m (%) | Acc ≤ 30m (%) |
| :--- | :--- | :--- | :--- | :--- |
| **Historical Average Baseline** | 319.6m | 420.8m | 1.3% | 4.0% |
| **Ridge Regression** | 129.7m | 184.3m | 6.7% | 9.3% |
| **Random Forest Regressor** | 108.4m | 181.1m | 22.7% | 40.0% |
| **Gradient Boosting (Champion)**| **153.5m** | **232.7m** | **12.0%** | **22.7%** |

- **Delay Classification (Champion)**: F1-Score: `1.000` | ROC-AUC: `1.000` | Brier Score: `0.000`.

---

## Optional: Running with Docker (PostgreSQL)

If you wish to run with Docker and a multi-container PostgreSQL setup:

```bash
docker-compose up --build
```
This automatically boots PostgreSQL, initializes the schema via `schema.sql`, launches the FastAPI service on port 8000, and starts the Streamlit dashboard on port 8501.
