import math

import numpy as np
import polars as pl
from numba import _dispatcher

from winery_adventures.computations import WineryHPCComputations, pairwise_stress_function


def test_pairwise_stress_small():
    pH = [3.4, 3.6]
    temp = [25.0, 26.0]
    cap = [500.0, 500.0]

    arguments = (pl.Series(pH).to_numpy(), pl.Series(temp).to_numpy(), pl.Series(cap).to_numpy())

    # Confronta il risultato compilato da Numba con la funzione Python originale.
    compiled_value = pairwise_stress_function(*arguments)
    python_value = pairwise_stress_function.py_func(*arguments)

    assert math.isclose(compiled_value, 2.2, abs_tol=1e-7)
    assert math.isclose(python_value, compiled_value, abs_tol=1e-7)


def test_pairwise_stress_empty_input():
    # Un gruppo privo di letture deve produrre uno stress nullo senza errori.
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
    # Mantiene lo schema previsto anche quando non esistono righe da elaborare.
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
    # Verifica che lo stress di una cisterna non venga propagato alle altre.
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
