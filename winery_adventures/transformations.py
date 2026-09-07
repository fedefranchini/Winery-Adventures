"""Definition of the analyzer dedicated to data transformations."""

import polars as pl

from winery_adventures.base import BaseWineryAnalyzer
from winery_adventures.validation import DataValidationError


class WineryTransformer(BaseWineryAnalyzer):
    """Groups the transformations applied to tank readings."""

    STANDARD_TEMPERATURE = 26.0

    def __init__(self, tank_info: pl.DataFrame | None = None):
        """Configure the transformations with the optional tank information.

        Args:
            tank_info: tank information, already validated and with
                ``grape_variety`` represented as a list.
        """
        self.tank_info = tank_info

    def analyze_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply all available transformations in sequence.

        Args:
            df: sensor readings to enrich.

        Returns:
            The readings with per-tank aggregations, optional per-variety
            aggregations, and temperature deviations.

        Raises:
            DataValidationError: if a tank in the readings is missing from
                the tank information.
            polars.exceptions.ColumnNotFoundError: if a required column is missing.
        """
        df = self.add_avg_ph_per_tank(df)
        df = self.add_num_readings_per_tank(df)
        if self.tank_info is not None:
            df = self.add_num_readings_per_grape_variety(df)
        return self.add_temperature_deviation(df)

    def add_avg_ph_per_tank(self, df: pl.DataFrame) -> pl.DataFrame:
        """Add the tank's average pH to every reading.

        Args:
            df: readings containing ``tank_id`` and ``pH``.

        Returns:
            The readings with the ``avg_pH_per_tank`` column.

        Raises:
            polars.exceptions.ColumnNotFoundError: if a required column is missing.
        """
        return df.with_columns(pl.col("pH").mean().over("tank_id").alias("avg_pH_per_tank"))

    def add_num_readings_per_tank(self, df: pl.DataFrame) -> pl.DataFrame:
        """Add the tank's number of readings to every reading.

        Args:
            df: readings containing ``tank_id``.

        Returns:
            The readings with the ``tank_num_readings`` column.

        Raises:
            polars.exceptions.ColumnNotFoundError: if ``tank_id`` is missing.
        """
        return df.with_columns(pl.len().over("tank_id").alias("tank_num_readings"))

    def add_num_readings_per_grape_variety(self, df: pl.DataFrame) -> pl.DataFrame:
        """Add each reading's grape variety's number of readings.

        Args:
            df: readings containing ``tank_id``.

        Returns:
            The readings associated with grape varieties and enriched with
            the ``grape_variety_num_readings`` column. A tank with several
            varieties produces one row per variety.

        Raises:
            AttributeError: if ``tank_info`` was not provided.
            DataValidationError: if a tank in the readings is not present in
                the tank information.
            polars.exceptions.ColumnNotFoundError: if a required column is missing.
        """
        if self.tank_info is None:
            raise AttributeError("tank_info is required for grape variety analysis")

        # Check tank information coverage before the inner join can discard readings.
        sensor_tank_ids = set(df.get_column("tank_id").to_list())
        known_tank_ids = set(self.tank_info.get_column("tank_id").to_list())
        missing_tank_ids = sorted(sensor_tank_ids.difference(known_tank_ids))
        if missing_tank_ids:
            missing_values = ", ".join(str(tank_id) for tank_id in missing_tank_ids)
            raise DataValidationError(f"Tank information is missing tank_id values: {missing_values}")

        # Associate each reading with the information for its tank.
        df = self.tank_info.join(df, on="tank_id", how="inner")

        # Expand each variety list into a separate row for each grape variety.
        df = df.explode("grape_variety", empty_as_null=True)

        # Count the readings associated with each grape variety.
        return df.with_columns(pl.len().over("grape_variety").alias("grape_variety_num_readings"))

    def add_temperature_deviation(self, df: pl.DataFrame) -> pl.DataFrame:
        """Add the absolute, unscaled and scaled temperature deviation.

        Args:
            df: readings containing ``temp`` and, optionally,
                ``quantity_liters``.

        Returns:
            The readings with ``temperature_deviation`` and, when the
            quantity is available, ``temperature_deviation_scaled``.

        Raises:
            polars.exceptions.ColumnNotFoundError: if ``temp`` is missing.
        """
        # Compute the absolute deviation from the standard temperature.
        result = df.with_columns((pl.col("temp") - self.STANDARD_TEMPERATURE).abs().alias("temperature_deviation"))

        # If the quantity column is missing, keep only the unscaled deviation.
        if "quantity_liters" not in result.columns:
            return result

        # Normalize the deviation relative to 1,000 liters of product.
        return result.with_columns(
            (pl.col("temperature_deviation") * 1000 / pl.col("quantity_liters")).alias("temperature_deviation_scaled")
        )
