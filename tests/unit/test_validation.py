import polars as pl
import pytest

from winery_adventures.validation import (
    DataValidationError,
    validate_sensors,
    validate_tank_info,
)


def test_validate_sensors_accepts_contract(sensors_df):
    validate_sensors(sensors_df)


def test_validate_sensors_rejects_missing_columns(sensors_df):
    invalid_df = sensors_df.drop("temp")

    with pytest.raises(DataValidationError, match="missing required columns: temp"):
        validate_sensors(invalid_df)


def test_validate_sensors_rejects_empty_data():
    empty_df = pl.DataFrame(schema={"tank_id": pl.Int64, "time": pl.String, "pH": pl.Float64, "temp": pl.Float64})

    with pytest.raises(DataValidationError, match="at least one row"):
        validate_sensors(empty_df)


def test_validate_sensors_rejects_null_required_values(sensors_df):
    invalid_df = sensors_df.with_columns(pl.lit(None, dtype=pl.Float64).alias("temp"))

    with pytest.raises(DataValidationError, match="null values in required columns: temp"):
        validate_sensors(invalid_df)


@pytest.mark.parametrize("invalid_ph", [float("nan"), -0.1, 14.1])
def test_validate_sensors_rejects_invalid_ph(sensors_df, invalid_ph):
    invalid_df = sensors_df.with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(pl.lit(invalid_ph)).otherwise(pl.col("pH")).alias("pH")
    )

    with pytest.raises(DataValidationError, match="invalid pH"):
        validate_sensors(invalid_df)


def test_validate_sensors_allows_null_optional_quantity(sensors_df):
    validate_sensors(sensors_df)


def test_validate_sensors_rejects_non_positive_quantity(sensors_df):
    invalid_df = sensors_df.with_columns(pl.lit(0).alias("quantity_liters"))

    with pytest.raises(DataValidationError, match="invalid quantity_liters"):
        validate_sensors(invalid_df)


def test_validate_tank_info_rejects_duplicate_tanks(tank_info_df):
    invalid_df = pl.concat([tank_info_df, tank_info_df.head(1)])

    with pytest.raises(DataValidationError, match="duplicate tank_id"):
        validate_tank_info(invalid_df)
