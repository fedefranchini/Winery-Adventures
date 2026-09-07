import math

import numpy as np
import polars as pl
import pytest
from numba import _dispatcher

from winery_adventures.computations import WineryHPCComputations, pairwise_stress_function
from winery_adventures.validation import DataValidationError, validate_sensors


def test_pairwise_stress_small():
    pH = [3.4, 3.6]
    temp = [25.0, 26.0]
    cap = [500.0, 500.0]

    arguments = (pl.Series(pH).to_numpy(), pl.Series(temp).to_numpy(), pl.Series(cap).to_numpy())

    # Compare the Numba-compiled result with the original Python function.
    compiled_value = pairwise_stress_function(*arguments)
    python_value = pairwise_stress_function.py_func(*arguments)

    assert math.isclose(compiled_value, 2.2, abs_tol=1e-7)
    assert math.isclose(python_value, compiled_value, abs_tol=1e-7)


def test_pairwise_stress_empty_input():
    # A group with no readings must produce zero stress without errors.
    empty = np.array([], dtype=np.float64)

    assert pairwise_stress_function(empty, empty, empty) == 0.0
    assert pairwise_stress_function.py_func(empty, empty, empty) == 0.0


def test_is_function_numba():
    assert isinstance(pairwise_stress_function, _dispatcher.Dispatcher), "Numba JIT compilation failed"


def test_hpc_computations_class():
    df_input = pl.DataFrame({"tank_id": [1, 1], "pH": [3.4, 3.6], "temp": [25, 26], "quantity_liters": [500, 500]})
    hpc = WineryHPCComputations()
    df_out = hpc.analyze_data(df_input)
    assert "stress_score" in df_out.columns
    assert df_out["stress_score"][0] == 2.2
    assert df_out["stress_score"][1] == 2.2


def test_hpc_computations_empty_dataframe():
    # Preserve the expected schema even when there are no rows to process.
    empty_df = pl.DataFrame(
        schema={
            "tank_id": pl.Int64,
            "pH": pl.Float64,
            "temp": pl.Float64,
            "quantity_liters": pl.Float64,
        }
    )

    result = WineryHPCComputations().analyze_data(empty_df)

    assert result.is_empty()
    assert result.schema["stress_score"] == pl.Float64


def test_hpc_computations_keeps_tank_scores_separate():
    # Check that one tank's stress is not propagated to other tanks.
    df_input = pl.DataFrame(
        {
            "tank_id": [1, 1, 2],
            "pH": [3.4, 3.6, 3.5],
            "temp": [25.0, 26.0, 24.0],
            "quantity_liters": [500.0, 500.0, 750.0],
        }
    )

    result = WineryHPCComputations().analyze_data(df_input)

    assert result.filter(pl.col("tank_id") == 1).get_column("stress_score").to_list() == [2.2, 2.2]
    assert result.filter(pl.col("tank_id") == 2).get_column("stress_score").to_list() == [0.0]


def test_hpc_computations_ignores_readings_without_quantity():
    # The formula uses only complete readings, without removing rows from the output.
    df_input = pl.DataFrame(
        {
            "tank_id": [1, 1, 1],
            "pH": [3.4, 3.6, 3.8],
            "temp": [25.0, 26.0, 27.0],
            "quantity_liters": [500.0, None, 1000.0],
        }
    )

    result = WineryHPCComputations().analyze_data(df_input)

    assert result.height == df_input.height
    assert all(math.isclose(score, 3.3, abs_tol=1e-12) for score in result.get_column("stress_score"))
    assert result.get_column("stress_score").is_finite().all()


def test_hpc_computations_returns_zero_without_computable_quantities():
    # No pairs can be computed: the n=0 case of the formula applies.
    all_null = pl.DataFrame(
        {
            "tank_id": [1, 1],
            "pH": [3.4, 3.6],
            "temp": [25.0, 26.0],
            "quantity_liters": pl.Series([None, None], dtype=pl.Float64),
        }
    )
    missing_column = all_null.drop("quantity_liters")

    null_result = WineryHPCComputations().analyze_data(all_null)
    missing_result = WineryHPCComputations().analyze_data(missing_column)

    assert null_result.get_column("stress_score").to_list() == [0.0, 0.0]
    assert missing_result.get_column("stress_score").to_list() == [0.0, 0.0]


@pytest.mark.parametrize(
    ("temperatures", "quantity"),
    [([25.0, 26.0], 1e-310), ([1e308, -1e308], 500.0)],
    ids=["tiny-positive-quantity", "extreme-finite-temperature"],
)
def test_hpc_computations_rejects_non_finite_stress(temperatures, quantity):
    # Validation accepts finite inputs; the computation detects the subsequent overflow.
    df_input = pl.DataFrame(
        {
            "tank_id": [7, 7],
            "time": ["2025-03-01 00:00:00", "2025-03-01 01:00:00"],
            "pH": [3.4, 3.6],
            "temp": temperatures,
            "quantity_liters": [quantity, quantity],
        }
    )
    validate_sensors(df_input)

    with pytest.raises(DataValidationError, match="Non-finite stress_score for tank_id 7"):
        WineryHPCComputations().analyze_data(df_input)
