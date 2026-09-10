"""Definition of the analyzer dedicated to high-performance computations."""

import numpy as np
import polars as pl
from numba import njit, prange

from winery_adventures.base import BaseWineryAnalyzer
from winery_adventures.validation import DataValidationError


# Persist compiled specializations between processes; results are still computed on every call.
@njit(parallel=True, cache=True)
def pairwise_stress_function(
    pH_vals: np.ndarray,
    temp_vals: np.ndarray,
    quantity_vals: np.ndarray,
) -> float:
    """Compute the average stress by comparing every pair of readings.

    Equivalence between evaluating this formula before versus after grape variety
    expansion is mathematical within floating-point tolerances (not bitwise identical),
    as differing summation order and size affect floating-point rounding. Computing
    pairwise stress early on unexpanded sensor readings avoids expansion-induced
    accumulation overflow in intermediate sums.

    Args:
        pH_vals: pH values ordered by reading.
        temp_vals: temperatures ordered the same way as the pH values.
        quantity_vals: quantities in liters associated with the readings.

    Returns:
        The average stress across pairs, or ``0.0`` if the arrays are empty.
    """
    # The number of readings sets the loop bounds and is used for the final normalization.
    n = len(pH_vals)

    # A set with no readings produces no stress.
    if n == 0:
        return 0.0

    stress_sum = 0.0

    # Compare each reading with all the others, including reversed pairs.
    # 'prange' parallelizes the outer loop across multiple CPU cores; the inner loop remains sequential.
    for i in prange(n):
        for j in range(n):
            # Measure the differences within the pair, giving temperature twice the weight.
            pH_dev = abs(pH_vals[i] - pH_vals[j])
            temp_dev = abs(temp_vals[i] - temp_vals[j]) * 2.0

            # Smaller volumes produce a higher factor because they are considered less stable.
            quantity_factor = (500.0 / quantity_vals[i]) + (500.0 / quantity_vals[j])

            stress_sum += (pH_dev + temp_dev) * quantity_factor

    # Normalize the sum over the n^2 pairs compared.
    return stress_sum / (n * n)


class WineryHPCComputations(BaseWineryAnalyzer):
    """Groups the intensive numeric computations applied to readings."""

    def analyze_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Compute and assign the fermentation stress of every tank.

        Args:
            df: readings containing ``tank_id``, ``pH``, and ``temp``. The
                ``quantity_liters`` column may be absent or contain null
                values.

        Returns:
            A logical copy of the readings with the ``stress_score`` column.
            Each tank's computation only considers readings with an
            available quantity; if none exist, the score is ``0.0``.

        Raises:
            DataValidationError: if the computation produces a non-finite stress.
            polars.exceptions.ColumnNotFoundError: if a required column is missing.
        """
        stress_by_tank = {}

        # Without quantities, no pairs can be computed: the specified function
        # returns 0.0 for empty input, while all rows are still preserved.
        if "quantity_liters" not in df.columns:
            return df.with_columns(pl.lit(0.0, dtype=pl.Float64).alias("stress_score"))

        # Partition the DataFrame by tank, preserving the original group order.
        for tank_df in df.partition_by("tank_id", maintain_order=True):
            # All rows in the group share the same identifier.
            tank_id = tank_df.get_column("tank_id")[0]

            # Readings without a quantity remain in the output, but cannot
            # contribute to the formula because the volume factor is undefined.
            computable_df = tank_df.drop_nulls(subset=["quantity_liters"])

            # Convert the complete numeric columns into Numba-compatible arrays.
            stress_score = pairwise_stress_function(
                computable_df.get_column("pH").cast(pl.Float64).to_numpy(),
                computable_df.get_column("temp").cast(pl.Float64).to_numpy(),
                computable_df.get_column("quantity_liters").cast(pl.Float64).to_numpy(),
            )

            # Even finite inputs can cause overflow: do not propagate unusable scores.
            if not np.isfinite(stress_score):
                raise DataValidationError(f"Non-finite stress_score for tank_id {tank_id}")
            stress_by_tank[tank_id] = stress_score

        # Assign each row the stress computed for its tank.
        stress_scores = []
        for tank_id in df.get_column("tank_id").to_list():
            stress_scores.append(stress_by_tank[tank_id])

        # Add the results to the DataFrame without removing existing columns.
        return df.with_columns(pl.Series("stress_score", stress_scores, dtype=pl.Float64))
