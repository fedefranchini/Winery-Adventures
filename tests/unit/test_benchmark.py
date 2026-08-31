import pytest

from benchmarks.benchmark_pipeline import PHASES, run_benchmark


def test_benchmark_produces_repeatable_dataset_and_phase_metrics():
    # Due esecuzioni con lo stesso seed devono generare input byte per byte identici.
    first_result = run_benchmark(num_tanks=2, num_readings=12, repetitions=2, seed=123)
    second_result = run_benchmark(num_tanks=2, num_readings=12, repetitions=1, seed=123)

    assert first_result["dataset"]["sensor_sha256"] == second_result["dataset"]["sensor_sha256"]
    assert first_result["dataset"]["tank_info_sha256"] == second_result["dataset"]["tank_info_sha256"]
    assert len(first_result["iterations"]) == 2

    # Ogni lettura viene espansa nelle tre varietà associate alla cisterna.
    for iteration in first_result["iterations"]:
        assert iteration["output_rows"] == 36
        assert iteration["total_seconds"] >= 0
        assert set(iteration["phases"]) == set(PHASES)
        assert all(metrics["seconds"] >= 0 for metrics in iteration["phases"].values())
        assert all(metrics["python_peak_mib"] >= 0 for metrics in iteration["phases"].values())


@pytest.mark.parametrize(
    ("num_tanks", "num_readings", "repetitions"),
    [(0, 10, 1), (2, 0, 1), (2, 10, 0)],
)
def test_benchmark_rejects_non_positive_parameters(num_tanks, num_readings, repetitions):
    # Evita benchmark vuoti che produrrebbero misure prive di significato.
    with pytest.raises(ValueError, match="must be positive"):
        run_benchmark(num_tanks=num_tanks, num_readings=num_readings, repetitions=repetitions)
