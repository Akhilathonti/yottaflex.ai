"""
Comprehensive Data Validation Framework
Executes Structural, Temporal, and Business integrity checks across raw and relational datasets.
Identifies deliberate anomalies and produces structured validation summaries.
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

from src.config import RAW_DATA_DIR, REPORTS_DIR, GROUND_TRUTH_DIR

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    check_category: str  # STRUCTURAL, TEMPORAL, BUSINESS
    check_name: str
    severity: str  # ERROR, WARNING, INFO
    table_name: str
    affected_entity_id: Optional[str]
    description: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    timestamp: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    warning_count: int
    anomaly_detected_count: int
    issues: List[ValidationIssue] = field(default_factory=list)


class DataValidator:
    """Automated validator ensuring data quality, temporal causality, and business rule conformance."""

    def __init__(self, data_dir=RAW_DATA_DIR):
        self.data_dir = data_dir
        self.issues: List[ValidationIssue] = []
        self.total_checks = 0
        self.passed_checks = 0

    def _record_issue(
        self,
        category: str,
        check_name: str,
        severity: str,
        table: str,
        entity_id: Optional[str],
        description: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        issue = ValidationIssue(
            check_category=category,
            check_name=check_name,
            severity=severity,
            table_name=table,
            affected_entity_id=entity_id,
            description=description,
            details=details or {},
        )
        self.issues.append(issue)

    def run_all_validations(self) -> ValidationReport:
        """Execute full validation suite across all tables."""
        logger.info("Executing comprehensive data validation suite...")
        self.issues = []
        self.total_checks = 0
        self.passed_checks = 0

        # Load datasets
        shipments = pd.read_csv(self.data_dir / "shipments.csv")
        legs = pd.read_csv(self.data_dir / "shipment_legs.csv")
        events = pd.read_csv(self.data_dir / "tracking_events.csv")
        facilities = pd.read_csv(self.data_dir / "facilities.csv")
        carriers = pd.read_csv(self.data_dir / "carriers.csv")
        queues = pd.read_csv(self.data_dir / "facility_queues.csv")

        # 1. Structural Checks
        self._check_primary_keys(shipments, "shipments", "shipment_id")
        self._check_primary_keys(legs, "shipment_legs", "leg_id")
        self._check_primary_keys(events, "tracking_events", "event_id")
        self._check_primary_keys(facilities, "facilities", "facility_id")
        self._check_primary_keys(carriers, "carriers", "carrier_id")

        self._check_foreign_keys(legs, "shipment_legs", "shipment_id", shipments, "shipments", "shipment_id")
        self._check_foreign_keys(legs, "shipment_legs", "carrier_id", carriers, "carriers", "carrier_id")
        self._check_foreign_keys(legs, "shipment_legs", "origin_facility_id", facilities, "facilities", "facility_id")
        self._check_foreign_keys(legs, "shipment_legs", "destination_facility_id", facilities, "facilities", "facility_id")
        self._check_foreign_keys(events, "tracking_events", "shipment_id", shipments, "shipments", "shipment_id")
        self._check_foreign_keys(shipments, "shipments", "primary_carrier_id", carriers, "carriers", "carrier_id")

        self._check_allowed_enums(
            shipments,
            "shipments",
            "status",
            {"CREATED", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION", "CANCELLED"},
            "shipment_id",
        )
        self._check_allowed_enums(
            events,
            "tracking_events",
            "event_type",
            {
                "CREATED", "PICKED_UP", "ARRIVED_AT_FACILITY", "SORTING_COMPLETED",
                "DEPARTED_FACILITY", "IN_TRANSIT_SCAN", "OUT_FOR_DELIVERY",
                "DELIVERED", "EXCEPTION", "WEATHER_HOLD", "DELIVERY_ATTEMPTED"
            },
            "event_id",
        )

        # 2. Temporal Causality Checks
        self._check_ingestion_after_event_time(events)
        self._check_leg_chronology(legs)
        self._check_event_sequence_order(events)
        self._check_ingestion_latency(events)

        # 3. Business Rule Checks
        self._check_delivered_status_consistency(shipments, events)
        self._check_actual_delay_formula(shipments)
        self._check_duplicate_tracking_events(events)

        failed_count = len([i for i in self.issues if i.severity == "ERROR"])
        warning_count = len([i for i in self.issues if i.severity == "WARNING"])
        anomaly_count = len(self.issues)

        report = ValidationReport(
            timestamp=datetime.utcnow().isoformat(),
            total_checks=self.total_checks,
            passed_checks=self.passed_checks,
            failed_checks=failed_count,
            warning_count=warning_count,
            anomaly_detected_count=anomaly_count,
            issues=self.issues,
        )

        self._save_report(report)
        return report

    def _check_primary_keys(self, df: pd.DataFrame, table: str, pk_col: str):
        self.total_checks += 1
        duplicates = df[df.duplicated(subset=[pk_col], keep=False)]
        if not duplicates.empty:
            for _, row in duplicates.iterrows():
                self._record_issue(
                    "STRUCTURAL",
                    "PRIMARY_KEY_UNIQUENESS",
                    "ERROR",
                    table,
                    str(row[pk_col]),
                    f"Duplicate primary key {row[pk_col]} detected in table {table}.",
                )
        else:
            self.passed_checks += 1

    def _check_foreign_keys(
        self,
        child_df: pd.DataFrame,
        child_table: str,
        child_col: str,
        parent_df: pd.DataFrame,
        parent_table: str,
        parent_col: str,
    ):
        self.total_checks += 1
        valid_parents = set(parent_df[parent_col].dropna())
        invalid_mask = (~child_df[child_col].isna()) & (~child_df[child_col].isin(valid_parents))
        invalid_rows = child_df[invalid_mask]

        if not invalid_rows.empty:
            for _, row in invalid_rows.iterrows():
                self._record_issue(
                    "STRUCTURAL",
                    "FOREIGN_KEY_INTEGRITY",
                    "ERROR",
                    child_table,
                    str(row.get("shipment_id", row.get(child_col))),
                    f"Orphan record: {child_col} '{row[child_col]}' not found in {parent_table}.{parent_col}.",
                )
        else:
            self.passed_checks += 1

    def _check_allowed_enums(
        self, df: pd.DataFrame, table: str, col: str, allowed: set, id_col: str
    ):
        self.total_checks += 1
        invalid = df[~df[col].isin(allowed)]
        if not invalid.empty:
            for _, row in invalid.iterrows():
                self._record_issue(
                    "STRUCTURAL",
                    "ALLOWED_ENUM_VALIDATION",
                    "ERROR",
                    table,
                    str(row[id_col]),
                    f"Invalid enum value '{row[col]}' in column {col}. Allowed: {allowed}.",
                )
        else:
            self.passed_checks += 1

    def _check_ingestion_after_event_time(self, events: pd.DataFrame):
        """Temporal Invariant: ingestion_timestamp >= event_timestamp."""
        self.total_checks += 1
        ev_time = pd.to_datetime(events["event_timestamp"])
        ing_time = pd.to_datetime(events["ingestion_timestamp"])
        violations = events[ing_time < ev_time]

        if not violations.empty:
            for _, row in violations.iterrows():
                self._record_issue(
                    "TEMPORAL",
                    "INGESTION_AFTER_EVENT_TIME",
                    "ERROR",
                    "tracking_events",
                    str(row["event_id"]),
                    f"Temporal causality breach: ingestion ({row['ingestion_timestamp']}) < event ({row['event_timestamp']}).",
                )
        else:
            self.passed_checks += 1

    def _check_leg_chronology(self, legs: pd.DataFrame):
        """Temporal Invariant: actual_arrival >= actual_departure."""
        self.total_checks += 1
        sub = legs.dropna(subset=["actual_departure", "actual_arrival"])
        dep = pd.to_datetime(sub["actual_departure"])
        arr = pd.to_datetime(sub["actual_arrival"])
        violations = sub[arr < dep]

        if not violations.empty:
            for _, row in violations.iterrows():
                self._record_issue(
                    "TEMPORAL",
                    "LEG_TRANSIT_CHRONOLOGY",
                    "ERROR",
                    "shipment_legs",
                    str(row["leg_id"]),
                    f"Chronology violation: arrival ({row['actual_arrival']}) is before departure ({row['actual_departure']}).",
                )
        else:
            self.passed_checks += 1

    def _check_event_sequence_order(self, events: pd.DataFrame):
        """Check monotonic sequence ordering per shipment."""
        self.total_checks += 1
        sorted_events = events.sort_values(["shipment_id", "event_sequence"])
        grouped = sorted_events.groupby("shipment_id")
        has_issue = False

        for shp_id, group in grouped:
            seqs = group["event_sequence"].tolist()
            # Check for non-consecutive jumps or duplicates
            for idx in range(len(seqs) - 1):
                if seqs[idx + 1] != seqs[idx] + 1:
                    has_issue = True
                    self._record_issue(
                        "TEMPORAL",
                        "EVENT_SEQUENCE_ORDER",
                        "ERROR",
                        "tracking_events",
                        str(shp_id),
                        f"Non-sequential jump in event sequence: {seqs[idx]} -> {seqs[idx+1]}",
                    )
                    break
        if not has_issue:
            self.passed_checks += 1

    def _check_ingestion_latency(self, events: pd.DataFrame):
        """Warning if ingestion latency exceeds 72 hours."""
        self.total_checks += 1
        ev_time = pd.to_datetime(events["event_timestamp"])
        ing_time = pd.to_datetime(events["ingestion_timestamp"])
        diff_hours = (ing_time - ev_time).dt.total_seconds() / 3600.0
        lagged = events[diff_hours > 72.0]

        if not lagged.empty:
            for _, row in lagged.iterrows():
                self._record_issue(
                    "TEMPORAL",
                    "EXCESSIVE_INGESTION_LATENCY",
                    "WARNING",
                    "tracking_events",
                    str(row["event_id"]),
                    f"Delayed tracking scan: ingestion lag is {(pd.to_datetime(row['ingestion_timestamp']) - pd.to_datetime(row['event_timestamp'])).total_seconds() / 3600:.1f} hours.",
                )
        else:
            self.passed_checks += 1

    def _check_delivered_status_consistency(self, shipments: pd.DataFrame, events: pd.DataFrame):
        """Business rule: If a valid DELIVERED event exists, shipment header must not be IN_TRANSIT."""
        self.total_checks += 1
        deliv_events = set(events[events["event_type"] == "DELIVERED"]["shipment_id"])
        inconsistent = shipments[(shipments["shipment_id"].isin(deliv_events)) & (shipments["status"] == "IN_TRANSIT")]

        if not inconsistent.empty:
            for _, row in inconsistent.iterrows():
                self._record_issue(
                    "BUSINESS",
                    "STATUS_DELIVERED_CONSISTENCY",
                    "ERROR",
                    "shipments",
                    str(row["shipment_id"]),
                    "Shipment has DELIVERED tracking event but header status remains IN_TRANSIT.",
                )
        else:
            self.passed_checks += 1

    def _check_actual_delay_formula(self, shipments: pd.DataFrame):
        """Business rule: actual_delay_minutes = (actual_delivery_time - promised_delivery_time)."""
        self.total_checks += 1
        deliv = shipments.dropna(subset=["actual_delivery_time", "promised_delivery_time", "actual_delay_minutes"])
        act_del = pd.to_datetime(deliv["actual_delivery_time"])
        prom_del = pd.to_datetime(deliv["promised_delivery_time"])
        calc_diff = ((act_del - prom_del).dt.total_seconds() / 60.0).astype(int)
        recorded_diff = deliv["actual_delay_minutes"].astype(int)

        mismatches = deliv[(calc_diff - recorded_diff).abs() > 1]
        if not mismatches.empty:
            for _, row in mismatches.iterrows():
                self._record_issue(
                    "BUSINESS",
                    "DELAY_CALCULATION_FORMULA",
                    "ERROR",
                    "shipments",
                    str(row["shipment_id"]),
                    f"Calculated delay {calc_diff.loc[row.name]}m does not match recorded delay {row['actual_delay_minutes']}m.",
                )
        else:
            self.passed_checks += 1

    def _check_duplicate_tracking_events(self, events: pd.DataFrame):
        """Business rule: tracking event IDs and (shipment_id, event_sequence) must be unique."""
        self.total_checks += 1
        dup_seq = events[events.duplicated(subset=["shipment_id", "event_sequence"], keep=False)]
        if not dup_seq.empty:
            for _, row in dup_seq.iterrows():
                self._record_issue(
                    "BUSINESS",
                    "DUPLICATE_EVENT_SEQUENCE",
                    "ERROR",
                    "tracking_events",
                    str(row["event_id"]),
                    f"Duplicate event sequence {row['event_sequence']} on shipment {row['shipment_id']}.",
                )
        else:
            self.passed_checks += 1

    def _save_report(self, report: ValidationReport):
        """Persist validation report to disk as JSON and Markdown."""
        json_path = REPORTS_DIR / "validation_summary.json"
        md_path = REPORTS_DIR / "validation_summary.md"

        data = asdict(report)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        md_content = f"""# Logistics Data Quality Validation Summary

**Execution Timestamp**: {report.timestamp}  
**Total Checks Executed**: {report.total_checks}  
**Checks Passed**: {report.passed_checks}  
**Checks Failed (Errors)**: {report.failed_checks}  
**Warnings Flagged**: {report.warning_count}  
**Deliberate Anomalies Detected**: {report.anomaly_detected_count}  

## Detected Anomalies & Integrity Violations

| Category | Check Name | Severity | Table | Affected Entity | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
        for issue in report.issues:
            md_content += f"| {issue.check_category} | `{issue.check_name}` | **{issue.severity}** | `{issue.table_name}` | `{issue.affected_entity_id}` | {issue.description} |\n"

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info("Saved validation summary -> %s and %s", json_path.name, md_path.name)


def main():
    validator = DataValidator()
    report = validator.run_all_validations()
    print(f"\n================ VALIDATION SUMMARY ================")
    print(f"Total Checks:   {report.total_checks}")
    print(f"Passed Checks:  {report.passed_checks}")
    print(f"Failed Checks:  {report.failed_checks}")
    print(f"Warnings:       {report.warning_count}")
    print(f"Anomalies Found:{report.anomaly_detected_count}")
    print(f"====================================================\n")


if __name__ == "__main__":
    main()
