"""I/O functions for the Winery Adventures pipeline.

Read the input TSV files (sensors and, optionally, tank information) and
write the final processed result. Normalize the type of all-null quantities
and grape variety labels. Aggregations and computations are handled by
``WineryTransformer`` and ``WineryHPCComputations``.
"""

import logging
from pathlib import Path

import polars as pl

from winery_adventures.validation import (
    DataValidationError,
    validate_sensors,
    validate_tank_info,
)

logger = logging.getLogger(__name__)


def _read_tsv(path: str, dataset_name: str) -> pl.DataFrame:
    # Check the path before delegating file reading to Polars.
    input_path = Path(path)
    if not input_path.is_file():
        logger.error("%s file was not found", dataset_name)
        raise FileNotFoundError(f"{dataset_name} file not found: {path}")

    # Convert parser errors into a more understandable application error.
    try:
        # Scan the whole TSV: quantities and decimals may appear after the first rows.
        return pl.read_csv(input_path, separator="\t", infer_schema_length=None)
    except pl.exceptions.PolarsError as exc:
        logger.error("Unable to read %s as a valid TSV file", dataset_name)
        raise DataValidationError(f"Unable to read {dataset_name} as a valid TSV file") from exc


def read_sensors(path: str) -> pl.DataFrame:
    """Read the sensor readings TSV file.

    The file is required and tab-separated, with columns
    ``tank_id``, ``time``, ``pH``, ``temp``, and optionally
    ``quantity_liters``.

    Args:
        path: path to the TSV file to read.

    Returns:
        The DataFrame containing the raw sensor data.

    Raises:
        FileNotFoundError: if the path does not identify a file.
        DataValidationError: if the TSV cannot be read or does not satisfy
            the sensor contract.
    """
    # Validate readings before they reach transformations and HPC computations.
    df = _read_tsv(path, "Sensor data")
    # Polars infers a completely empty TSV column as text.
    # Set its numeric type explicitly without converting any textual values.
    if "quantity_liters" in df.columns and df.get_column("quantity_liters").null_count() == df.height:
        df = df.with_columns(pl.col("quantity_liters").cast(pl.Float64))
    validate_sensors(df)
    logger.info("Sensor data loaded and validated (%d rows)", df.height)
    return df


def read_tank_info(path: str) -> pl.DataFrame:
    """Read the tank information TSV file.

    The file contains ``tank_id``, ``grape_variety`` (multiple varieties
    separated by commas), and ``capacity_liters``. The ``grape_variety``
    column is converted from strings to lists here, and surrounding
    whitespace is stripped from each item so that downstream transformations
    (e.g. ``WineryTransformer.add_num_readings_per_grape_variety``) receive
    ready-to-use data.

    Args:
        path: path to the TSV file to read.

    Returns:
        The DataFrame with ``grape_variety`` already split into lists.

    Raises:
        FileNotFoundError: if the path does not identify a file.
        DataValidationError: if the TSV cannot be read or does not satisfy
            the tank contract.
    """
    df = _read_tsv(path, "Tank information")
    validate_tank_info(df)
    logger.info("Tank information loaded and validated (%d rows)", df.height)
    return df.with_columns(pl.col("grape_variety").str.split(",").list.eval(pl.element().str.strip_chars()))


def write_output(df: pl.DataFrame, path: str) -> None:
    """Write the processed DataFrame to a CSV file.

    Args:
        df: final DataFrame to save (transformations and HPC applied).
        path: path to the output file.

    Raises:
        OSError: if the output file cannot be written.
    """
    try:
        df.write_csv(path)
    except OSError as exc:
        logger.error("Unable to write pipeline output")
        raise OSError(f"Unable to write pipeline output: {path}") from exc

    logger.info("Pipeline output written (%d rows)", df.height)
