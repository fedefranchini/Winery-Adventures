"""Validation of the data contracts used by Winery Adventures."""

import polars as pl


class DataValidationError(ValueError):
    """Indicate that a dataset does not satisfy the application contract."""


SENSOR_REQUIRED_COLUMNS = {"tank_id", "time", "pH", "temp"}
TANK_INFO_REQUIRED_COLUMNS = {"tank_id", "grape_variety", "capacity_liters"}


def _require_columns(df: pl.DataFrame, required: set[str], dataset_name: str) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise DataValidationError(f"{dataset_name} is missing required columns: {', '.join(missing)}")


def _require_rows(df: pl.DataFrame, dataset_name: str) -> None:
    # A dataset with no rows cannot be processed by the pipeline.
    if df.is_empty():
        raise DataValidationError(f"{dataset_name} must contain at least one row")


def _require_no_nulls(df: pl.DataFrame, columns: set[str], dataset_name: str) -> None:
    # Collect all required columns that contain at least one null value.
    columns_with_nulls = sorted(column for column in columns if df.get_column(column).null_count() > 0)
    if columns_with_nulls:
        raise DataValidationError(
            f"{dataset_name} contains null values in required columns: " f"{', '.join(columns_with_nulls)}"
        )


def _require_numeric(df: pl.DataFrame, columns: set[str], dataset_name: str) -> None:
    # Check types using the Polars schema without silently converting the data.
    invalid = sorted(column for column in columns if not df.schema[column].is_numeric())
    if invalid:
        raise DataValidationError(f"{dataset_name} requires numeric columns: {', '.join(invalid)}")


def _require_integer(df: pl.DataFrame, column: str, dataset_name: str) -> None:
    # Identifiers and capacities must retain an integer type.
    if not df.schema[column].is_integer():
        raise DataValidationError(f"{dataset_name} requires {column} to be an integer column")


def validate_sensors(df: pl.DataFrame) -> None:
    """Check the schema and essential values of sensor readings.

    Check required columns, the presence of rows and values, types, the pH
    range, finite temperatures, and positive optional quantities.

    Args:
        df: sensor dataset to validate.

    Raises:
        DataValidationError: if the dataset violates any constraint.
    """
    # First apply the structural checks common to all readings.
    _require_columns(df, SENSOR_REQUIRED_COLUMNS, "Sensor data")
    _require_rows(df, "Sensor data")
    _require_no_nulls(df, SENSOR_REQUIRED_COLUMNS, "Sensor data")
    _require_numeric(df, {"tank_id", "pH", "temp"}, "Sensor data")
    _require_integer(df, "tank_id", "Sensor data")

    # Time remains textual because its format is preserved in the output.
    if df.schema["time"] != pl.String:
        raise DataValidationError("Sensor data requires time to be a string column")

    if df.get_column("time").str.strip_chars().eq("").any():
        raise DataValidationError("Sensor data contains an empty time value")

    # The pH must be finite and within the physical range of 0-14.
    ph_values = df.get_column("pH").cast(pl.Float64)
    if not ph_values.is_finite().all() or (ph_values < 0).any() or (ph_values > 14).any():
        raise DataValidationError("Sensor data contains an invalid pH value")

    # Reject NaN and infinite values that would make computations unreliable.
    temperature_values = df.get_column("temp").cast(pl.Float64)
    if not temperature_values.is_finite().all():
        raise DataValidationError("Sensor data contains a non-finite temperature value")

    # Quantity is optional and may contain nulls, but any present values must be positive.
    if "quantity_liters" in df.columns:
        if df.get_column("quantity_liters").null_count() != df.height:
            _require_numeric(df, {"quantity_liters"}, "Sensor data")
        quantities = df.get_column("quantity_liters").drop_nulls().cast(pl.Float64)
        if not quantities.is_finite().all() or (quantities <= 0).any():
            raise DataValidationError("Sensor data contains an invalid quantity_liters value")


def validate_tank_info(df: pl.DataFrame) -> None:
    """Check the schema and essential values of tank information.

    Check required columns, types, non-empty grape varieties, positive
    capacities, and unique identifiers.

    Args:
        df: tank information to validate.

    Raises:
        DataValidationError: if the dataset violates any constraint.
    """
    # Check the structure before splitting the grape_variety column.
    _require_columns(df, TANK_INFO_REQUIRED_COLUMNS, "Tank information")
    _require_rows(df, "Tank information")
    _require_no_nulls(df, TANK_INFO_REQUIRED_COLUMNS, "Tank information")
    _require_numeric(df, {"tank_id", "capacity_liters"}, "Tank information")
    _require_integer(df, "tank_id", "Tank information")
    _require_integer(df, "capacity_liters", "Tank information")

    if df.schema["grape_variety"] != pl.String:
        raise DataValidationError("Tank information requires grape_variety to be a string column")

    if df.get_column("grape_variety").str.strip_chars().eq("").any():
        raise DataValidationError("Tank information contains an empty grape_variety value")

    # Each comma-separated item must identify a variety; surrounding spaces
    # are allowed because they are normalized during reading.
    variety_values = df.get_column("grape_variety").to_list()
    if any(not token.strip() for value in variety_values for token in value.split(",")):
        raise DataValidationError("Tank information contains an empty grape_variety item")

    # A null, infinite, or non-positive capacity does not describe a valid tank.
    capacities = df.get_column("capacity_liters").cast(pl.Float64)
    if not capacities.is_finite().all() or (capacities <= 0).any():
        raise DataValidationError("Tank information contains an invalid capacity_liters value")

    if df.get_column("tank_id").n_unique() != df.height:
        raise DataValidationError("Tank information contains duplicate tank_id values")
