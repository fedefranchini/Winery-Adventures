import polars as pl
import pytest
import wandb

from winery_adventures.main import run_full_pipeline


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
