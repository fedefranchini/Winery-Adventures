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


def test_validate_sensors_allows_missing_optional_quantity(sensors_df_without_quantities):
    # quantity_liters può mancare completamente secondo il contratto dei sensori.
    validate_sensors(sensors_df_without_quantities)


def test_validate_sensors_rejects_non_positive_quantity(sensors_df):
    invalid_df = sensors_df.with_columns(pl.lit(0).alias("quantity_liters"))

    with pytest.raises(DataValidationError, match="invalid quantity_liters"):
        validate_sensors(invalid_df)


@pytest.mark.parametrize(
    ("expression", "error_message"),
    [
        (pl.col("pH").cast(pl.String), "requires numeric columns: pH"),
        (pl.col("tank_id").cast(pl.Float64), "requires tank_id to be an integer"),
        (pl.lit(123).alias("time"), "requires time to be a string"),
        (pl.lit("").alias("time"), "empty time value"),
        (pl.lit(float("inf")).alias("temp"), "non-finite temperature"),
        (pl.lit("500").alias("quantity_liters"), "requires numeric columns: quantity_liters"),
        (pl.lit(float("inf")).alias("quantity_liters"), "invalid quantity_liters"),
    ],
)
def test_validate_sensors_rejects_invalid_types_and_values(sensors_df, expression, error_message):
    # Ogni espressione altera un solo campo per isolare la causa dell'errore.
    invalid_df = sensors_df.with_columns(expression)

    with pytest.raises(DataValidationError, match=error_message):
        validate_sensors(invalid_df)


def test_validate_tank_info_accepts_contract(tank_info_df):
    validate_tank_info(tank_info_df)


def test_validate_tank_info_rejects_missing_columns(tank_info_df):
    invalid_df = tank_info_df.drop("capacity_liters")

    with pytest.raises(DataValidationError, match="missing required columns: capacity_liters"):
        validate_tank_info(invalid_df)


def test_validate_tank_info_rejects_empty_data(tank_info_df):
    # clear conserva lo schema originale ma rimuove tutte le righe.
    with pytest.raises(DataValidationError, match="at least one row"):
        validate_tank_info(tank_info_df.clear())


def test_validate_tank_info_rejects_null_required_values(tank_info_df):
    invalid_df = tank_info_df.with_columns(pl.lit(None, dtype=pl.String).alias("grape_variety"))

    with pytest.raises(DataValidationError, match="null values in required columns: grape_variety"):
        validate_tank_info(invalid_df)


@pytest.mark.parametrize(
    ("expression", "error_message"),
    [
        (pl.col("tank_id").cast(pl.Float64), "requires tank_id to be an integer"),
        (pl.col("capacity_liters").cast(pl.Float64), "requires capacity_liters to be an integer"),
        (pl.lit(123).alias("grape_variety"), "requires grape_variety to be a string"),
        (pl.lit("").alias("grape_variety"), "empty grape_variety value"),
        (pl.lit(0).alias("capacity_liters"), "invalid capacity_liters"),
    ],
)
def test_validate_tank_info_rejects_invalid_types_and_values(tank_info_df, expression, error_message):
    # Controlla separatamente tipi, stringhe vuote e capacità non valide.
    invalid_df = tank_info_df.with_columns(expression)

    with pytest.raises(DataValidationError, match=error_message):
        validate_tank_info(invalid_df)


def test_validate_tank_info_rejects_duplicate_tanks(tank_info_df):
    invalid_df = pl.concat([tank_info_df, tank_info_df.head(1)])

    with pytest.raises(DataValidationError, match="duplicate tank_id"):
        validate_tank_info(invalid_df)
