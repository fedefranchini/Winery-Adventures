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
    # The mean weights output rows rather than assigning equal weight to tanks.
    pipeline.log_to_wandb(pl.DataFrame({"tank_id": [1, 1, 2], "stress_score": [0.5, 0.5, 0.8]}))

    assert wandb.run == monkey_wandb_run, "wandb.init() should be called"
    assert monkey_wandb_run.logs == [
        {
            "output_rows": 3,
            "tank_count": 2,
            "stress_score_count": 3,
            "stress_score": pytest.approx(0.6),
            "stress_score_min": 0.5,
            "stress_score_max": 0.8,
        }
    ]


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


def test_wandb_logging_uses_explicit_reinit_and_finishes_each_run(monkeypatch):
    # Each call uses a separate run and completes its init/log/finish cycle.
    calls = []

    class RecordingRun:
        def log(self, data):
            calls.append(("log", data))

        def finish(self):
            calls.append(("finish", None))

    def init(**kwargs):
        calls.append(("init", kwargs))
        return RecordingRun()

    monkeypatch.setattr(wandb, "init", init)
    pipeline = WineryPipeline([], project_name="TestProj")
    for _ in range(2):
        pipeline.log_to_wandb(pl.DataFrame({"tank_id": [1]}))

    expected_cycle = [
        ("init", {"project": "TestProj", "reinit": "finish_previous"}),
        ("log", {"output_rows": 1, "tank_count": 1}),
        ("finish", None),
    ]
    assert calls == expected_cycle * 2


def test_pipeline_logs_and_propagates_analyzer_errors(caplog, sensors_df):
    class FailingAnalyzer:
        def analyze_data(self, df):
            raise RuntimeError("controlled failure")

    pipeline = WineryPipeline([FailingAnalyzer()])

    # The error remains visible to the caller, and the log identifies only the component.
    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="controlled failure"):
        pipeline.run(sensors_df)

    assert "Analyzer FailingAnalyzer failed" in caplog.text
    assert "3.3" not in caplog.text


def test_wandb_run_is_finished_when_logging_fails(monkeypatch):
    # Record the call to finish without actually contacting the wandb service.
    finish_calls = []

    class FailingRun:
        def log(self, data):
            raise RuntimeError("wandb unavailable")

        def finish(self):
            finish_calls.append(True)

    monkeypatch.setattr(wandb, "init", lambda **kwargs: FailingRun())

    pipeline = WineryPipeline([], project_name="TestProj")

    # An error during log must also pass through the pipeline's finally block.
    with pytest.raises(RuntimeError, match="wandb unavailable"):
        pipeline.log_to_wandb(pl.DataFrame({"stress_score": [0.5]}))

    assert finish_calls == [True]
