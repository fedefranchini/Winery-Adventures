import polars as pl

from winery_adventures.main import run_full_pipeline


def test_run_full_pipeline_without_tank_info(
    tmp_path,
    monkey_joblib,
    monkey_wandb_run,
    sensors_df,
):
    # Prepara soltanto il dataset obbligatorio per esercitare il ramo senza anagrafica.
    sensor_path = tmp_path / "sensors.tsv"
    output_path = tmp_path / "result.csv"
    sensors_df.write_csv(sensor_path, separator="\t")

    run_full_pipeline(
        input_csv=str(sensor_path),
        output_csv=str(output_path),
        project_name="UnitTest",
    )

    result = pl.read_csv(output_path)

    # Senza tank_info le letture non devono essere espanse per varietà d'uva.
    assert result.height == sensors_df.height
    assert "avg_pH_per_tank" in result.columns
    assert "stress_score" in result.columns
    assert "grape_variety" not in result.columns

    parallel_mock, delayed_mock = monkey_joblib
    # In assenza del secondo file Joblib deve ricevere una sola attività di caricamento.
    parallel_mock.assert_called_once()
    delayed_mock.assert_called_once()
