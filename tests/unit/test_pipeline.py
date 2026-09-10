import logging
from unittest.mock import Mock

import polars as pl
import pytest

import wandb
from winery_adventures.computations import WineryHPCComputations
from winery_adventures.pipeline import WineryPipeline
from winery_adventures.transformations import WineryTransformer


@pytest.mark.parametrize("project_name", ["TestProj", None])
def test_pipeline_chain(monkey_wandb_run, sensors_df, project_name):
    pipeline = WineryPipeline([WineryTransformer(), WineryHPCComputations()], project_name=project_name)
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


@pytest.mark.parametrize("project_name", ["TestProj", None])
def test_wandb_logging_uses_explicit_reinit_and_finishes_each_run(monkeypatch, project_name):
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
    pipeline = WineryPipeline([], project_name=project_name)
    for _ in range(2):
        pipeline.log_to_wandb(pl.DataFrame({"tank_id": [1]}))

    expected_cycle = [
        ("init", {"project": project_name, "reinit": "finish_previous"}),
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


def test_wandb_init_failure_propagates(monkeypatch):
    monkeypatch.setattr(wandb, "init", Mock(side_effect=RuntimeError("init failed")))
    pipeline = WineryPipeline([], project_name="TestProj")
    with pytest.raises(RuntimeError, match="init failed"):
        pipeline.log_to_wandb(pl.DataFrame({"stress_score": [0.5]}))


def test_wandb_log_and_finish_both_fail_preserves_log_error(monkeypatch):
    class DoubleFailingRun:
        def log(self, data):
            raise RuntimeError("primary log failure")

        def finish(self):
            raise RuntimeError("secondary finish failure")

    monkeypatch.setattr(wandb, "init", lambda **kwargs: DoubleFailingRun())
    pipeline = WineryPipeline([], project_name="TestProj")
    with pytest.raises(RuntimeError, match="primary log failure"):
        pipeline.log_to_wandb(pl.DataFrame({"stress_score": [0.5]}))


def test_wandb_finish_only_fails_propagates(monkeypatch):
    class FinishFailingRun:
        def log(self, data):
            pass

        def finish(self):
            raise RuntimeError("finish cleanup failure")

    monkeypatch.setattr(wandb, "init", lambda **kwargs: FinishFailingRun())
    pipeline = WineryPipeline([], project_name="TestProj")
    with pytest.raises(RuntimeError, match="finish cleanup failure"):
        pipeline.log_to_wandb(pl.DataFrame({"stress_score": [0.5]}))


def test_pipeline_analyzer_failure_with_logging_requested_never_calls_wandb(monkeypatch, sensors_df):
    class FailingAnalyzer:
        def analyze_data(self, df):
            raise ValueError("analyzer error")

    init_mock = Mock()
    monkeypatch.setattr(wandb, "init", init_mock)
    pipeline = WineryPipeline([FailingAnalyzer()], project_name="TestProj")
    with pytest.raises(ValueError, match="analyzer error"):
        pipeline.run(sensors_df, log_to_wandb=True)

    init_mock.assert_not_called()


def test_legacy_explicitly_ordered_pipeline_usable(sensors_df, tank_info_df_grape_variety_split):
    legacy_pipeline = WineryPipeline(
        [WineryTransformer(tank_info=tank_info_df_grape_variety_split), WineryHPCComputations()]
    )
    reordered_pipeline = WineryPipeline(
        [WineryHPCComputations(), WineryTransformer(tank_info=tank_info_df_grape_variety_split)]
    )

    legacy_out = legacy_pipeline.run(sensors_df)
    reordered_out = reordered_pipeline.run(sensors_df)

    assert legacy_out.columns == reordered_out.columns
    assert legacy_out.columns[-1] == "stress_score"
    assert legacy_out.dtypes == reordered_out.dtypes
    assert legacy_out.height == reordered_out.height
