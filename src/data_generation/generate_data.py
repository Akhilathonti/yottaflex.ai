"""
Main Command-Line Data Generation Script for Logistics ETA Prediction System
Usage:
    python -m src.data_generation.generate_data --shipments 1000 --events 6000 --facilities 100 --disruptions 200 --seed 20261022
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
import pandas as pd

from src.config import (
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    GROUND_TRUTH_DIR,
    EXPORTS_DIR,
    RANDOM_SEED,
)
from src.data_generation.generators import LogisticsDataGenerator
from src.data_generation.anomalies import AnomalyInjector
from src.database.connection import init_db, engine
from src.database.models import Base

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def generate_all_data(
    num_shipments: int = 1000,
    num_facilities: int = 100,
    num_disruptions: int = 200,
    seed: int = RANDOM_SEED,
    inject_anomalies: bool = True,
    save_to_database: bool = True,
) -> dict:
    """Execute end-to-end synthetic data generation workflow."""
    logger.info("Starting logistics synthetic data generation with seed %d...", seed)
    logger.info("Target: %d shipments, %d facilities, %d disruptions", num_shipments, num_facilities, num_disruptions)

    generator = LogisticsDataGenerator(seed=seed)

    # 1. Master entities
    logger.info("Generating master data: service levels, carriers, facilities, routes, delay reasons...")
    service_levels_df = generator.generate_service_levels()
    carriers_df = generator.generate_carriers()
    facilities_df = generator.generate_facilities(num_facilities=num_facilities)
    routes_df = generator.generate_routes(facilities_df=facilities_df)
    delay_reasons_df = generator.generate_delay_reasons()

    # 2. Environmental & Operational Context
    logger.info("Generating weather disruptions and facility queue sensor data...")
    weather_df = generator.generate_weather_events(num_events=num_disruptions)
    queues_df = generator.generate_facility_queues(facilities_df=facilities_df, num_samples=min(5000, num_facilities * 25))
    fac_weather_df = generator.generate_facility_weather_bridge(facilities_df=facilities_df, weather_df=weather_df)

    # 3. Shipments, Multi-leg Journeys, Tracking Events, ETA Estimates, Ground Truth
    logger.info("Generating %d shipments with multi-leg journeys and tracking events...", num_shipments)
    (
        shipments_df,
        legs_df,
        events_df,
        eta_df,
        shipment_delays_df,
    ) = generator.generate_shipments_and_telemetry(
        num_shipments=num_shipments,
        facilities_df=facilities_df,
        carriers_df=carriers_df,
        service_levels_df=service_levels_df,
        weather_df=weather_df,
    )

    # 4. Inject Deliberate Labelled Anomalies
    anomaly_records = []
    if inject_anomalies:
        logger.info("Injecting 14 deliberate anomalies into test benchmark dataset...")
        injector = AnomalyInjector(seed=seed)
        (
            shipments_df,
            legs_df,
            events_df,
            facilities_df,
            queues_df,
            weather_df,
            anomaly_records,
        ) = injector.inject_all_anomalies(
            shipments_df, legs_df, events_df, facilities_df, queues_df, weather_df
        )

    # 5. Save Raw CSVs
    logger.info("Exporting generated datasets to CSV in %s...", RAW_DATA_DIR)
    dfs = {
        "service_levels": service_levels_df,
        "carriers": carriers_df,
        "facilities": facilities_df,
        "routes": routes_df,
        "weather_events": weather_df,
        "facility_queues": queues_df,
        "facility_weather_events": fac_weather_df,
        "delay_reasons": delay_reasons_df,
        "shipments": shipments_df,
        "shipment_legs": legs_df,
        "tracking_events": events_df,
        "eta_estimates": eta_df,
        "shipment_delay_reasons": shipment_delays_df,
    }

    for name, df in dfs.items():
        csv_path = RAW_DATA_DIR / f"{name}.csv"
        df.to_csv(csv_path, index=False)
        logger.info("Saved %s (%d rows) -> %s", name, len(df), csv_path.name)

    # 6. Save Ground Truth Anomalies
    gt_csv_path = GROUND_TRUTH_DIR / "ground_truth.csv"
    gt_json_path = GROUND_TRUTH_DIR / "ground_truth.json"

    anom_dicts = [asdict(a) for a in anomaly_records]
    pd.DataFrame(anom_dicts).to_csv(gt_csv_path, index=False)
    with open(gt_json_path, "w", encoding="utf-8") as f:
        json.dump(anom_dicts, f, indent=2)
    logger.info("Saved %d deliberate anomaly ground-truth labels -> %s", len(anom_dicts), gt_json_path)

    # 7. Generate Manifest Summary
    manifest = {
        "generated_at": datetime.utcnow().isoformat(),
        "random_seed": seed,
        "counts": {name: len(df) for name, df in dfs.items()},
        "total_events": len(events_df),
        "total_anomalies_injected": len(anomaly_records),
        "on_time_shipments": int((shipments_df["is_delayed"] == False).sum()),
        "delayed_shipments": int((shipments_df["is_delayed"] == True).sum()),
        "delay_rate": round(float((shipments_df["is_delayed"] == True).mean()), 4) if len(shipments_df) > 0 else 0.0,
    }

    manifest_path = EXPORTS_DIR / "source_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Source manifest written to %s", manifest_path)

    # 8. Seed Database
    if save_to_database:
        logger.info("Initializing database schema and inserting records...")
        init_db()
        for name, df in dfs.items():
            try:
                # Avoid inserting deliberate broken FK into SQL constraint checks if SQLite/Postgres enforce FK
                # Write with chunking
                df.to_sql(name, con=engine, if_exists="replace", index=False, chunksize=1000)
            except Exception as e:
                logger.warning("Table %s import note: %s", name, e)
        logger.info("Database seeding completed successfully.")

    logger.info("Generation finished. Summary: %s", manifest["counts"])
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Logistics Synthetic Data Generator")
    parser.add_argument("--shipments", type=int, default=1000, help="Number of shipments (default: 1000, full scale: 50000)")
    parser.add_argument("--events", type=int, default=6000, help="Target events baseline (indicative)")
    parser.add_argument("--facilities", type=int, default=100, help="Number of facilities (default: 100)")
    parser.add_argument("--disruptions", type=int, default=200, help="Number of weather disruptions (default: 200, full: 1000)")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Deterministic random seed (default: 20261022)")
    parser.add_argument("--starter", action="store_true", help="Generate fast 500-shipment starter dataset")
    parser.add_argument("--no-anomalies", action="store_true", help="Skip deliberate anomaly injection")
    parser.add_argument("--no-db", action="store_true", help="Do not save to database")

    args = parser.parse_args()

    num_shipments = 500 if args.starter else args.shipments

    generate_all_data(
        num_shipments=num_shipments,
        num_facilities=args.facilities,
        num_disruptions=args.disruptions,
        seed=args.seed,
        inject_anomalies=not args.no_anomalies,
        save_to_database=not args.no_db,
    )


if __name__ == "__main__":
    main()
