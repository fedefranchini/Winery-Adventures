import polars as pl
import pytest
import wandb
from polars.testing import assert_frame_equal

from winery_adventures.computations import WineryHPCComputations
from winery_adventures.io import read_sensors, read_tank_info, write_output
from winery_adventures.main import run_full_pipeline
from winery_adventures.pipeline import WineryPipeline
from winery_adventures.transformations import WineryTransformer
from winery_adventures.validation import DataValidationError


@pytest.mark.parametrize("with_tank_info", [False, True])
def test_run_full_pipeline_with_all_null_quantities(tmp_path, sensors_df, tank_info_df, with_tank_info):
    # Use real I/O and Joblib to cover TSV type inference as well.
    sensor_path = tmp_path / "sensors.tsv"
    tank_path = tmp_path / "tanks.tsv"
    output_path = tmp_path / "result.csv"
    sensors_df.with_columns(pl.lit(None).alias("quantity_liters")).write_csv(sensor_path, separator="\t")
    tank_info_df.write_csv(tank_path, separator="\t")

    run_full_pipeline(str(sensor_path), str(tank_path) if with_tank_info else None, str(output_path))

    result = pl.read_csv(output_path)
    assert result.height == (9 if with_tank_info else 3)
    assert result.get_column("stress_score").to_list() == [0.0] * result.height
    assert result.get_column("temperature_deviation_scaled").null_count() == result.height


def test_run_full_pipeline_without_tank_info(
    tmp_path,
    monkey_joblib,
    monkey_wandb_run,
    sensors_df,
):
    # Prepare only the required dataset to exercise the branch without tank information.
    sensor_path = tmp_path / "sensors.tsv"
    output_path = tmp_path / "result.csv"
    sensors_df.write_csv(sensor_path, separator="\t")

    run_full_pipeline(
        input_csv=str(sensor_path),
        output_csv=str(output_path),
        project_name="UnitTest",
    )

    result = pl.read_csv(output_path)

    # Without tank_info, readings must not be expanded by grape variety.
    assert result.height == sensors_df.height
    assert "avg_pH_per_tank" in result.columns
    assert "stress_score" in result.columns
    assert "grape_variety" not in result.columns

    parallel_mock, delayed_mock = monkey_joblib
    # Without the second file, Joblib must receive only one loading task.
    parallel_mock.assert_called_once()
    delayed_mock.assert_called_once()


def test_run_full_pipeline_without_quantities_or_wandb(
    tmp_path,
    monkeypatch,
    monkey_joblib,
    sensors_df_without_quantities,
):
    sensor_path = tmp_path / "sensors.tsv"
    output_path = tmp_path / "result.csv"
    sensors_df_without_quantities.write_csv(sensor_path, separator="\t")
    wandb_init_calls = []
    monkeypatch.setattr(wandb, "init", lambda **kwargs: wandb_init_calls.append(kwargs))

    # project_name=None disables W&B, and missing quantities produce scores of 0.0.
    run_full_pipeline(input_csv=str(sensor_path), output_csv=str(output_path))

    result = pl.read_csv(output_path)
    assert result.height == sensors_df_without_quantities.height
    assert result.get_column("stress_score").to_list() == [0.0, 0.0, 0.0]
    assert wandb_init_calls == []


def _reference_tank_stress(ph_list: list[float], temp_list: list[float], q_list: list[float | None]) -> float:
    valid = [(p, t, q) for p, t, q in zip(ph_list, temp_list, q_list, strict=True) if q is not None]
    n = len(valid)
    if n == 0:
        return 0.0
    total = 0.0
    for i in range(n):
        for j in range(n):
            p_dev = abs(valid[i][0] - valid[j][0])
            t_dev = abs(valid[i][1] - valid[j][1]) * 2.0
            q_fac = (500.0 / valid[i][2]) + (500.0 / valid[j][2])
            total += (p_dev + t_dev) * q_fac
    return total / (n * n)


@pytest.mark.parametrize(
    ("scenario_name", "sensors_builder", "tank_builder"),
    [
        (
            "without_tank_info",
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 1, 2],
                    "time": ["2025-01-01 00:00:00", "2025-01-01 01:00:00", "2025-01-01 02:00:00"],
                    "pH": [3.3, 3.5, 3.7],
                    "temp": [25.0, 26.0, 24.5],
                    "quantity_liters": [500.0, 600.0, 1000.0],
                }
            ),
            lambda: None,
        ),
        (
            "one_variety",
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 1, 2],
                    "time": ["2025-01-01 00:00:00", "2025-01-01 01:00:00", "2025-01-01 02:00:00"],
                    "pH": [3.3, 3.5, 3.7],
                    "temp": [25.0, 26.0, 24.5],
                    "quantity_liters": [500.0, 600.0, 1000.0],
                }
            ),
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 2],
                    "capacity_liters": [1000, 1500],
                    "grape_variety": ["Merlot", "Cabernet"],
                }
            ),
        ),
        (
            "varying_multiple_and_duplicate_labels",
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 1, 2],
                    "time": ["2025-01-01 00:00:00", "2025-01-01 01:00:00", "2025-01-01 02:00:00"],
                    "pH": [3.3, 3.5, 3.7],
                    "temp": [25.0, 26.0, 24.5],
                    "quantity_liters": [500.0, 600.0, 1000.0],
                }
            ),
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 2],
                    "capacity_liters": [1000, 1500],
                    "grape_variety": ["Merlot,Merlot,Syrah", "Vermentino,Cannonau"],
                }
            ),
        ),
        (
            "genuine_duplicate_readings",
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 1, 1],
                    "time": ["2025-01-01 00:00:00", "2025-01-01 00:00:00", "2025-01-01 01:00:00"],
                    "pH": [3.4, 3.4, 3.6],
                    "temp": [25.0, 25.0, 26.0],
                    "quantity_liters": [500.0, 500.0, 500.0],
                }
            ),
            lambda: pl.DataFrame(
                {
                    "tank_id": [1],
                    "capacity_liters": [1000],
                    "grape_variety": ["Merlot,Syrah"],
                }
            ),
        ),
        (
            "mixed_quantities",
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 1, 2, 2],
                    "time": [
                        "2025-01-01 00:00:00",
                        "2025-01-01 01:00:00",
                        "2025-01-01 02:00:00",
                        "2025-01-01 03:00:00",
                    ],
                    "pH": [3.3, 3.5, 3.6, 3.8],
                    "temp": [25.0, 26.0, 24.0, 25.0],
                    "quantity_liters": [500.0, None, 800.0, None],
                }
            ),
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 2],
                    "capacity_liters": [1000, 1500],
                    "grape_variety": ["Merlot", "Syrah,Cabernet"],
                }
            ),
        ),
        (
            "missing_quantities_column",
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 1, 2],
                    "time": ["2025-01-01 00:00:00", "2025-01-01 01:00:00", "2025-01-01 02:00:00"],
                    "pH": [3.3, 3.5, 3.7],
                    "temp": [25.0, 26.0, 24.5],
                }
            ),
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 2],
                    "capacity_liters": [1000, 1500],
                    "grape_variety": ["Merlot", "Cabernet"],
                }
            ),
        ),
        (
            "extra_metadata_only_tank",
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 2],
                    "time": ["2025-01-01 00:00:00", "2025-01-01 01:00:00"],
                    "pH": [3.3, 3.5],
                    "temp": [25.0, 26.0],
                    "quantity_liters": [500.0, 600.0],
                }
            ),
            lambda: pl.DataFrame(
                {
                    "tank_id": [1, 2, 3],
                    "capacity_liters": [1000, 1500, 2000],
                    "grape_variety": ["Merlot", "Cabernet", "Nebbiolo"],
                }
            ),
        ),
    ],
)
def test_run_full_pipeline_reordered_vs_reference_and_legacy_order(
    tmp_path, scenario_name, sensors_builder, tank_builder
):
    sensors_df = sensors_builder()
    tank_df = tank_builder()

    sensor_path = tmp_path / f"{scenario_name}_sensors.tsv"
    sensors_df.write_csv(sensor_path, separator="\t")

    tank_path = None
    if tank_df is not None:
        tank_path = tmp_path / f"{scenario_name}_tanks.tsv"
        tank_df.write_csv(tank_path, separator="\t")

    out_path = tmp_path / f"{scenario_name}_result.csv"
    run_full_pipeline(
        input_csv=str(sensor_path),
        tank_info_csv=str(tank_path) if tank_path is not None else None,
        output_csv=str(out_path),
    )

    result = pl.read_csv(out_path)

    # Check complete column schema and that stress_score is in final position
    assert "stress_score" in result.columns
    assert result.columns[-1] == "stress_score"
    assert result.get_column("stress_score").is_finite().all()

    # Compare against independent reference formula for each tank
    for tank_id in sensors_df.get_column("tank_id").unique().to_list():
        tank_sensors = sensors_df.filter(pl.col("tank_id") == tank_id)
        ph_vals = tank_sensors.get_column("pH").cast(pl.Float64).to_list()
        temp_vals = tank_sensors.get_column("temp").cast(pl.Float64).to_list()
        q_vals = (
            tank_sensors.get_column("quantity_liters").cast(pl.Float64).to_list()
            if "quantity_liters" in tank_sensors.columns
            else [None] * tank_sensors.height
        )
        expected_stress = _reference_tank_stress(ph_vals, temp_vals, q_vals)

        tank_rows = result.filter(pl.col("tank_id") == tank_id)
        assert tank_rows.height > 0
        for actual_score in tank_rows.get_column("stress_score").to_list():
            assert actual_score == pytest.approx(expected_stress, abs=1e-7, rel=1e-7)

    # Compare with legacy explicitly ordered pipeline
    loaded_sensors = read_sensors(str(sensor_path))
    loaded_tanks = read_tank_info(str(tank_path)) if tank_path is not None else None
    legacy_pipeline = WineryPipeline([WineryTransformer(tank_info=loaded_tanks), WineryHPCComputations()])
    legacy_result = legacy_pipeline.run(loaded_sensors)

    reordered_pipeline = WineryPipeline([WineryHPCComputations(), WineryTransformer(tank_info=loaded_tanks)])
    reordered_result = reordered_pipeline.run(loaded_sensors)

    # In-memory comparison: all columns, dtypes, and values must match within tolerance
    assert_frame_equal(reordered_result, legacy_result, check_exact=False, rel_tol=1e-9, abs_tol=1e-9)

    # Re-read CSV comparison: output CSV matches reloaded legacy execution across all columns
    legacy_csv = tmp_path / f"{scenario_name}_legacy.csv"
    write_output(legacy_result, str(legacy_csv))
    reloaded_legacy = pl.read_csv(legacy_csv)
    assert_frame_equal(result, reloaded_legacy, check_exact=False, rel_tol=1e-9, abs_tol=1e-9)


def test_run_full_pipeline_preflight_catches_unknown_tank_competing_with_overflow(tmp_path):
    sensors = pl.DataFrame(
        {
            "tank_id": [1, 99, 99],
            "time": ["2025-01-01 00:00:00", "2025-01-01 01:00:00", "2025-01-01 02:00:00"],
            "pH": [3.4, 3.5, 3.6],
            "temp": [25.0, 1e308, -1e308],
            "quantity_liters": [500.0, 500.0, 500.0],
        }
    )
    tanks = pl.DataFrame(
        {
            "tank_id": [1],
            "capacity_liters": [1000],
            "grape_variety": ["Merlot"],
        }
    )

    sensor_path = tmp_path / "overflow_sensors.tsv"
    tank_path = tmp_path / "overflow_tanks.tsv"
    output_path = tmp_path / "overflow_result.csv"

    sensors.write_csv(sensor_path, separator="\t")
    tanks.write_csv(tank_path, separator="\t")

    # Missing tank coverage must fail preflight before HPC computation encounters non-finite values
    with pytest.raises(DataValidationError, match="Tank information is missing tank_id values: 99"):
        run_full_pipeline(str(sensor_path), str(tank_path), str(output_path))
