"""
Export raw CSV tables to SQL INSERT seed statements
"""
from pathlib import Path
import pandas as pd
from src.config import RAW_DATA_DIR, EXPORTS_DIR


def export_seed_sql():
    sql_file = EXPORTS_DIR / "seed.sql"
    tables = [
        "service_levels",
        "carriers",
        "facilities",
        "routes",
        "delay_reasons",
        "weather_events",
        "facility_queues",
        "shipments",
        "shipment_legs",
    ]

    with open(sql_file, "w", encoding="utf-8") as f:
        f.write("-- ====================================================================\n")
        f.write("-- SQL Seed Export for Logistics ETA Prediction System\n")
        f.write("-- ====================================================================\n\n")

        for table in tables:
            csv_path = RAW_DATA_DIR / f"{table}.csv"
            if not csv_path.exists():
                continue
            df = pd.read_csv(csv_path)
            # Export up to 200 rows per table for the seed file
            subset = df.head(200)
            f.write(f"-- Table: {table} ({len(subset)} seed rows)\n")
            for _, row in subset.iterrows():
                cols = ", ".join(df.columns)
                val_strs = []
                for v in row.values:
                    if pd.isna(v):
                        val_strs.append("NULL")
                    elif isinstance(v, (int, float, bool)):
                        val_strs.append(str(v))
                    else:
                        clean_v = str(v).replace("'", "''")
                        val_strs.append(f"'{clean_v}'")
                vals = ", ".join(val_strs)
                f.write(f"INSERT INTO {table} ({cols}) VALUES ({vals});\n")
            f.write("\n")

    print(f"Exported seed SQL -> {sql_file}")


if __name__ == "__main__":
    export_seed_sql()
