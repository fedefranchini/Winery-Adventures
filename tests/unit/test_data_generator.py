import random
from datetime import datetime

import polars as pl
import pytest

import data_generator
from data_generator import (
    ADJECTIVES,
    GRAPE_VARIETIES,
    generate_sensor_data,
    generate_tank_info,
    generate_variety_pool,
)

SENSOR_COLUMNS = ["tank_id", "time", "pH", "temp", "quantity_liters"]
TANK_INFO_COLUMNS = ["tank_id", "grape_variety", "capacity_liters"]


def test_generate_variety_pool_is_sorted_and_unique():
    random.seed(7)

    pool = generate_variety_pool(num_varieties=50)

    assert len(pool) == 50
    assert len(set(pool)) == len(pool)
    assert pool == sorted(pool)


def test_generate_variety_pool_labels_combine_grape_and_adjective():
    # Each label must remain expressible as grape variety + adjective.
    random.seed(7)

    for label in generate_variety_pool(num_varieties=30):
        matches = [
            (grape, adjective)
            for grape in GRAPE_VARIETIES
            for adjective in ADJECTIVES
            if label == f"{grape}{adjective}"
        ]
        assert matches, f"Label cannot be decomposed: {label}"


def test_generate_variety_pool_stops_at_available_combinations():
    # The attempt limit prevents infinite loops when the requested combinations
    # exceed those actually available.
    random.seed(7)
    limited_pool = generate_variety_pool(num_varieties=len(ADJECTIVES) * len(GRAPE_VARIETIES) + 100)

    assert 0 < len(limited_pool) <= len(ADJECTIVES) * len(GRAPE_VARIETIES)


def test_generate_tank_info_respects_contract():
    random.seed(11)
    variety_pool = generate_variety_pool(num_varieties=50)

    rows = generate_tank_info(num_tanks=6, variety_list=variety_pool)

    assert [row["tank_id"] for row in rows] == [1, 2, 3, 4, 5, 6]
    for row in rows:
        assert set(row) == set(TANK_INFO_COLUMNS)
        varieties = row["grape_variety"].split(",")
        # Each tank receives three distinct varieties, without extra spaces.
        assert len(varieties) == 3
        assert len(set(varieties)) == 3
        assert all(variety in variety_pool for variety in varieties)
        assert all(variety == variety.strip() for variety in varieties)
        assert 1000 <= row["capacity_liters"] <= 1800


def test_generate_tank_info_builds_its_own_pool_when_omitted():
    random.seed(11)

    rows = generate_tank_info(num_tanks=2)

    assert len(rows) == 2
    assert all(len(row["grape_variety"].split(",")) == 3 for row in rows)


def test_generate_sensor_data_respects_contract():
    random.seed(3)

    rows = generate_sensor_data(num_tanks=4, num_readings=200, start_date="2025-03-01")

    assert len(rows) == 200
    for row in rows:
        assert set(row) == set(SENSOR_COLUMNS)
        assert 1 <= row["tank_id"] <= 4
        assert 3.0 <= row["pH"] <= 4.0
        assert 22.0 <= row["temp"] <= 28.0
        assert row["quantity_liters"] is None or 200 <= row["quantity_liters"] <= 1000
        # The time format matches the one declared in the data contracts.
        moment = datetime.strptime(row["time"], "%Y-%m-%d %H:%M:%S")
        assert datetime(2025, 3, 1) <= moment <= datetime(2025, 3, 11, 23)


def test_generate_sensor_data_produces_optional_missing_quantities():
    # The optional column must remain nullable: this is the case handled by HPC.
    random.seed(3)

    rows = generate_sensor_data(num_tanks=4, num_readings=500)

    assert any(row["quantity_liters"] is None for row in rows)
    assert any(row["quantity_liters"] is not None for row in rows)


def test_same_seed_reproduces_identical_datasets():
    def build():
        random.seed(2024)
        pool = generate_variety_pool(num_varieties=40)
        return generate_tank_info(num_tanks=3, variety_list=pool), generate_sensor_data(num_tanks=3, num_readings=60)

    first_tank_info, first_sensors = build()
    second_tank_info, second_sensors = build()

    assert first_tank_info == second_tank_info
    assert first_sensors == second_sensors


def test_different_seeds_produce_different_readings():
    random.seed(1)
    first = generate_sensor_data(num_tanks=3, num_readings=60)
    random.seed(2)
    second = generate_sensor_data(num_tanks=3, num_readings=60)

    assert first != second


def test_generated_datasets_satisfy_the_pipeline_contracts():
    # The generator must produce inputs accepted by application validation.
    from winery_adventures.validation import validate_sensors, validate_tank_info

    random.seed(5)
    pool = generate_variety_pool(num_varieties=40)
    tank_info = pl.DataFrame(generate_tank_info(num_tanks=5, variety_list=pool), schema=TANK_INFO_COLUMNS)
    sensors = pl.DataFrame(generate_sensor_data(num_tanks=5, num_readings=120), schema=SENSOR_COLUMNS)

    validate_tank_info(tank_info)
    validate_sensors(sensors)


@pytest.mark.parametrize("argument", ["--seed", "--num-tanks", "--num-readings", "--start-date"])
def test_parse_args_exposes_documented_options(monkeypatch, argument):
    monkeypatch.setattr("sys.argv", ["data_generator.py"])

    args = data_generator.parse_args()

    assert hasattr(args, argument.removeprefix("--").replace("-", "_"))


def test_main_writes_both_tsv_files_in_the_data_directory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["data_generator.py", "--seed", "42", "--num-tanks", "3", "--num-readings", "30"],
    )

    data_generator.main()

    sensors_path = tmp_path / "data" / "full_sensors.tsv"
    tank_info_path = tmp_path / "data" / "full_tank_info.tsv"
    assert sensors_path.is_file() and tank_info_path.is_file()

    sensors = pl.read_csv(sensors_path, separator="\t")
    tank_info = pl.read_csv(tank_info_path, separator="\t")
    assert sensors.columns == SENSOR_COLUMNS
    assert tank_info.columns == TANK_INFO_COLUMNS
    assert sensors.height == 30
    assert tank_info.height == 3

    # The final message must specify the paths actually written.
    output = capsys.readouterr().out
    assert "data/full_tank_info.tsv" in output
    assert "data/full_sensors.tsv" in output


def test_main_is_reproducible_across_runs(tmp_path, monkeypatch):
    def run(target_dir):
        monkeypatch.chdir(target_dir)
        monkeypatch.setattr(
            "sys.argv",
            ["data_generator.py", "--seed", "99", "--num-tanks", "3", "--num-readings", "40"],
        )
        data_generator.main()
        return (
            (target_dir / "data" / "full_sensors.tsv").read_bytes(),
            (target_dir / "data" / "full_tank_info.tsv").read_bytes(),
        )

    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()

    # The same seed must produce byte-for-byte identical files.
    assert run(first_dir) == run(second_dir)
