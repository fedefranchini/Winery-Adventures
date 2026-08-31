import logging

import polars as pl
import pytest

import wandb
from winery_adventures.computations import WineryHPCComputations
from winery_adventures.pipeline import WineryPipeline
from winery_adventures.transformations import WineryTransformer


def test_pipeline_chain(monkey_wandb_run, sensors_df):
    pipeline = WineryPipeline([WineryTransformer(), WineryHPCComputations()], project_name="TestProj")
    df_out = pipeline.run(sensors_df, log_to_wandb=True)

    assert "avg_pH_per_tank" in df_out.columns, "Missing transformation column"
    assert "stress_score" in df_out.columns, "Missing HPC column"

    assert wandb.run == monkey_wandb_run, "wandb.init() should be called"
    assert any("stress_score" in d for d in monkey_wandb_run.logs), "No 'stress_score' logs found"


def test_analyzers_run(sensors_df):
    pipeline = WineryPipeline([WineryTransformer(), WineryHPCComputations()], project_name="TestProj")
    df_out = pipeline.run(sensors_df, log_to_wandb=False)

    assert "avg_pH_per_tank" in df_out.columns, "Missing transformation column"
    assert "stress_score" in df_out.columns, "Missing HPC column"


def test_null_analyzers_run(sensors_df):
    class MockAnalyzer:
        def analyze_data(self, df):
            return df

    pipeline = WineryPipeline([MockAnalyzer(), MockAnalyzer()])
    df_out = pipeline.run(sensors_df)

    assert df_out is sensors_df, "Pipeline should return the input DataFrame"


def test_log_wandb(monkey_wandb_run):
    pipeline = WineryPipeline([WineryTransformer(), WineryHPCComputations()], project_name="TestProj")
    pipeline.log_to_wandb(pl.DataFrame({"tank_id": [1, 2], "stress_score": [0.5, 0.6]}))

    assert wandb.run == monkey_wandb_run, "wandb.init() should be called"
    assert any("stress_score" in d for d in monkey_wandb_run.logs), "No 'stress_score' logs found"


def test_pipeline_logs_phases_without_sensor_values(caplog, sensors_df):
    class MockAnalyzer:
        def analyze_data(self, df):
            return df

    pipeline = WineryPipeline([MockAnalyzer()])

    with caplog.at_level(logging.INFO):
        pipeline.run(sensors_df)

    assert "Running analyzer MockAnalyzer" in caplog.text
    assert "Winery pipeline completed" in caplog.text
    assert "3.3" not in caplog.text


def test_pipeline_logs_and_propagates_analyzer_errors(caplog, sensors_df):
    class FailingAnalyzer:
        def analyze_data(self, df):
            raise RuntimeError("controlled failure")

    pipeline = WineryPipeline([FailingAnalyzer()])

    # L'errore resta visibile al chiamante e il log identifica soltanto il componente.
    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="controlled failure"):
        pipeline.run(sensors_df)

    assert "Analyzer FailingAnalyzer failed" in caplog.text
    assert "3.3" not in caplog.text


def test_wandb_run_is_finished_when_logging_fails(monkeypatch):
    # Registra la chiamata a finish senza contattare realmente il servizio wandb.
    finish_calls = []

    monkeypatch.setattr(wandb, "init", lambda **kwargs: object())

    def fail_log(data):
        raise RuntimeError("wandb unavailable")

    monkeypatch.setattr(wandb, "log", fail_log)
    monkeypatch.setattr(wandb, "finish", lambda: finish_calls.append(True))

    pipeline = WineryPipeline([], project_name="TestProj")

    # Anche un errore durante log deve attraversare il blocco finally della pipeline.
    with pytest.raises(RuntimeError, match="wandb unavailable"):
        pipeline.log_to_wandb(pl.DataFrame({"stress_score": [0.5]}))

    assert finish_calls == [True]
