import pytest
import json
import random
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from benchmarks.benchmark_pipeline import PHASES, run_benchmark
from benchmarks import compare_joblib, compare_kernels
from data_generator import generate_sensor_data


def test_benchmark_produces_repeatable_dataset_and_phase_metrics():
    # Two runs with the same seed must generate byte-for-byte identical inputs.
    first_result = run_benchmark(num_tanks=2, num_readings=12, repetitions=2, seed=123)
    second_result = run_benchmark(num_tanks=2, num_readings=12, repetitions=1, seed=123)

    assert first_result["dataset"]["sensor_sha256"] == second_result["dataset"]["sensor_sha256"]
    assert first_result["dataset"]["tank_info_sha256"] == second_result["dataset"]["tank_info_sha256"]
    assert len(first_result["iterations"]) == 2

    assert "source_sha256" in first_result
    assert "benchmarks/benchmark_pipeline.py" in first_result["source_sha256"]
    assert "winery_adventures/validation.py" in first_result["source_sha256"]
    assert all(len(sha) == 64 for sha in first_result["source_sha256"].values())

    assert "preflight" in PHASES
    assert "preflight" in first_result["summary"]["phases"]

    # Each reading is expanded into the three varieties associated with its tank.
    for iteration in first_result["iterations"]:
        assert iteration["output_rows"] == 36
        assert iteration["stress_scores_finite"] is True
        assert iteration["total_seconds"] >= 0
        assert set(iteration["phases"]) == set(PHASES)
        assert "preflight" in iteration["phases"]
        assert all(metrics["seconds"] >= 0 for metrics in iteration["phases"].values())
        assert all(metrics["python_peak_mib"] >= 0 for metrics in iteration["phases"].values())


@pytest.mark.parametrize(
    ("num_tanks", "num_readings", "repetitions"),
    [(0, 10, 1), (2, 0, 1), (2, 10, 0)],
)
def test_benchmark_rejects_non_positive_parameters(num_tanks, num_readings, repetitions):
    # Prevent empty benchmarks that would produce meaningless measurements.
    with pytest.raises(ValueError, match="must be positive"):
        run_benchmark(num_tanks=num_tanks, num_readings=num_readings, repetitions=repetitions)


@pytest.mark.parametrize("order", ["hpc-first", "transformer-first"])
def test_benchmark_supports_both_orders(order):
    result = run_benchmark(num_tanks=2, num_readings=12, repetitions=1, seed=123, order=order)
    assert result["parameters"]["order"] == order
    assert len(result["iterations"]) == 1
    assert result["iterations"][0]["output_rows"] == 36
    assert result["iterations"][0]["stress_scores_finite"] is True
    assert "preflight" in result["iterations"][0]["phases"]
    assert result["iterations"][0]["phases"]["preflight"]["seconds"] >= 0


def test_benchmark_rejects_invalid_order():
    with pytest.raises(ValueError, match="Expected 'hpc-first' or 'transformer-first'"):
        run_benchmark(num_tanks=2, num_readings=12, repetitions=1, seed=123, order="invalid-order")


@pytest.mark.parametrize("include_python", [False, True])
def test_kernel_comparison_checks_same_workload_for_all_variants(include_python):
    result = compare_kernels.compare_kernels(2, 12, 3, 123, include_python)
    assert set(result["seconds"]) == ({"python", "serial", "parallel"} if include_python else {"serial", "parallel"})
    assert all(len(values) == 3 and all(v > 0 for v in values) for values in result["seconds"].values())
    assert result["scores_finite"] is True
    assert result["max_absolute_error"] < 1e-10
    assert result["dataset"]["ordered_pairs"] > 0
    assert result["dataset"]["output_rows"] == 36


def test_python_comparison_rejects_excessive_pair_work(monkeypatch):
    import polars as pl

    sensors = pl.DataFrame(
        {"tank_id": [1] * 2237, "pH": [3.5] * 2237, "temp": [25.0] * 2237, "quantity_liters": [500.0] * 2237}
    )
    monkeypatch.setattr(compare_kernels, "_create_dataset", lambda *a: {"sensor_path": "s", "tank_info_path": "t"})
    monkeypatch.setattr(compare_kernels, "_load_inputs", lambda *a: (sensors, None))
    monkeypatch.setattr(compare_kernels.WineryTransformer, "analyze_data", lambda self, df: df)
    with pytest.raises(ValueError, match="five million"):
        compare_kernels.compare_kernels(1, 2237, 1, include_python=True)


def test_joblib_comparison_preserves_ordered_records_and_random_state():
    state = random.getstate()
    result = compare_joblib.compare_joblib(2, 16, 2, 123, (1, 2))
    assert random.getstate() == state
    assert result["outputs_match"] is True
    assert set(result["seconds"]) == {"cold_1", "warm_1", "cold_2", "warm_2"}
    assert all(len(v) == 2 and min(v) > 0 for v in result["seconds"].values())
    assert [i["order"] for i in result["iterations"]] == [[1, 2], [2, 1]]
    for iteration in result["iterations"]:
        for measurement in iteration["measurements"].values():
            for phase in ("cold", "warm"):
                assert measurement[phase]["output_sha256"] == result["dataset"]["output_sha256"]
                assert measurement[phase]["output_rows"] == 16


@pytest.mark.parametrize("jobs", [(2,), (1, 1), (1, 0), (1, -2), (True, 2)])
def test_joblib_comparison_rejects_invalid_workers(jobs):
    with pytest.raises(ValueError, match="jobs must"):
        compare_joblib.compare_joblib(2, 16, 1, jobs=jobs)


def test_joblib_comparison_rejects_non_positive_workload():
    with pytest.raises(ValueError, match="positive"):
        compare_joblib.compare_joblib(num_readings=0)


def test_joblib_comparison_rejects_changed_output(monkeypatch):
    worker = {"effective_workers": 1, "cold": {"seconds": 0.1, "output_sha256": "changed", "output_rows": 2}}
    monkeypatch.setattr(compare_joblib.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=json.dumps(worker)))
    with pytest.raises(AssertionError, match="changed generated"):
        compare_joblib.compare_joblib(2, 2, 1, jobs=(1,))


@pytest.mark.parametrize("module", [compare_joblib, compare_kernels])
def test_comparison_cli_preserves_existing_evidence(tmp_path, monkeypatch, module):
    path = tmp_path / "existing.json"
    path.write_text("preserve", encoding="utf-8")
    measure = MagicMock(side_effect=AssertionError("Should not start measurement"))
    monkeypatch.setattr(module, module.__name__.split(".")[-1], measure)
    monkeypatch.setattr(sys, "argv", ["benchmark", "--output", str(path)])
    with pytest.raises(SystemExit):
        module.main()
    assert path.read_text(encoding="utf-8") == "preserve"
    measure.assert_not_called()


def test_generator_worker_options_preserve_default_records(monkeypatch):
    state = random.getstate()
    try:
        random.seed(123)
        expected = generate_sensor_data(2, 10, n_jobs=1, show_progress=False)
        random.seed(123)
        assert generate_sensor_data(2, 10, n_jobs=2, show_progress=False) == expected
    finally:
        random.setstate(state)
