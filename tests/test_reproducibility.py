"""
Reproducibility and Determinism Verification Test
"""
import pytest
from src.data_generation.generators import LogisticsDataGenerator


def test_deterministic_generation_with_fixed_seed():
    seed = 20261022
    gen1 = LogisticsDataGenerator(seed=seed)
    gen2 = LogisticsDataGenerator(seed=seed)

    fac1 = gen1.generate_facilities(num_facilities=20)
    fac2 = gen2.generate_facilities(num_facilities=20)

    # Identical row counts
    assert len(fac1) == len(fac2)

    # Identical IDs and latitudes
    assert fac1["facility_id"].tolist() == fac2["facility_id"].tolist()
    assert fac1["latitude"].tolist() == fac2["latitude"].tolist()
    assert fac1["longitude"].tolist() == fac2["longitude"].tolist()

    # Identical Carriers
    car1 = gen1.generate_carriers()
    car2 = gen2.generate_carriers()
    assert car1["carrier_id"].tolist() == car2["carrier_id"].tolist()
    assert car1["on_time_rating"].tolist() == car2["on_time_rating"].tolist()
