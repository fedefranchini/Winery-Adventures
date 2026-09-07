import pytest

from benchmarks.compare_kernels import compare_kernels


def test_kernel_comparison_checks_equivalence_and_records_evidence():
    result = compare_kernels(num_tanks=2, num_readings=12, repetitions=2, seed=123)

    assert result["dataset"]["output_rows"] == 36
    assert result["scores_finite"] is True
    assert result["max_absolute_error"] < 1e-10
    assert len(result["source_sha256"]["winery_adventures/computations.py"]) == 64
    assert all(len(values) == 2 for values in result["seconds"].values())
    assert all(value >= 0 for values in result["seconds"].values() for value in values)


def test_kernel_comparison_rejects_empty_workload():
    with pytest.raises(ValueError, match="must be positive"):
        compare_kernels(num_readings=0)
