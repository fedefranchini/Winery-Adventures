"""Compare serial and parallel Numba kernels, optionally including interpreted Python."""

import argparse
import json
import platform
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numba
import numpy as np
import polars as pl

from benchmarks.benchmark_pipeline import _create_dataset, _git_revision, _load_inputs, _sha256
from winery_adventures.computations import pairwise_stress_function
from winery_adventures.transformations import WineryTransformer


def compare_kernels(
    num_tanks: int = 100,
    num_readings: int = 100_000,
    repetitions: int = 5,
    seed: int = 42,
    include_python: bool = False,
) -> dict:
    """Measure the same formula on identical unexpanded sensor arrays.

    Args:
        num_tanks: number of tanks generated, positive.
        num_readings: number of readings generated, positive.
        repetitions: number of comparisons, positive.
        seed: seed shared by the inputs.
        include_python: also time the original Python body; limited to five
            million valid ordered pairs to keep interpreted execution bounded.

    Returns:
        Environment, source and input fingerprints, timings, and numeric verification.

    Raises:
        ValueError: if a size/repetition count is not positive or the Python
            experiment exceeds five million valid ordered pairs.
        AssertionError: if the two variants do not produce equivalent results.
    """
    if min(num_tanks, num_readings, repetitions) <= 0:
        raise ValueError("num_tanks, num_readings and repetitions must be positive")

    # With parallel=False, Numba interprets prange as a regular serial loop.
    # Reusing the application function body avoids maintaining two separate formulas.
    serial_kernel = numba.njit(parallel=False)(pairwise_stress_function.py_func)
    kernels = {"serial": serial_kernel, "parallel": pairwise_stress_function}
    if include_python:
        # py_func executes the undecorated body: prange behaves as a Python range.
        kernels = {"python": pairwise_stress_function.py_func, **kernels}

    with tempfile.TemporaryDirectory(prefix="winery-kernel-comparison-") as directory:
        dataset = _create_dataset(Path(directory), num_tanks, num_readings, seed)
        sensors, tanks = _load_inputs(dataset["sensor_path"], dataset["tank_info_path"])
        transformed = WineryTransformer(tanks).analyze_data(sensors)

    # In production, pairwise stress is computed on unexpanded sensor readings before variety expansion.
    groups = []
    for tank in sensors.partition_by("tank_id", maintain_order=True):
        complete = tank.drop_nulls(subset=["quantity_liters"])
        groups.append(
            tuple(complete.get_column(name).cast(pl.Float64).to_numpy() for name in ("pH", "temp", "quantity_liters"))
        )

    ordered_pairs = sum(len(group[0]) ** 2 for group in groups)
    if include_python and ordered_pairs > 5_000_000:
        raise ValueError("Python comparison exceeds five million pairs; reduce readings or increase tanks")

    # Compile for the actual input signatures, outside the measured times.
    expected = np.array([serial_kernel(*group) for group in groups])
    actual = np.array([pairwise_stress_function(*group) for group in groups])
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-10)
    assert np.isfinite(expected).all() and np.isfinite(actual).all()
    max_error = float(np.max(np.abs(actual - expected)))
    if include_python:
        python_scores = np.array([kernels["python"](*group) for group in groups])
        np.testing.assert_allclose(python_scores, expected, rtol=1e-10, atol=1e-10)
        max_error = max(max_error, float(np.max(np.abs(python_scores - expected))))

    timings = {name: [] for name in kernels}
    for repetition in range(repetitions):
        # Rotate all variants through each timing position, including Python when selected.
        names = list(kernels)
        offset = repetition % len(names)
        order = names[offset:] + names[:offset]
        for name in order:
            started = time.perf_counter()
            scores = np.array([kernels[name](*group) for group in groups])
            timings[name].append(time.perf_counter() - started)
            np.testing.assert_allclose(scores, expected, rtol=1e-10, atol=1e-10)
            assert np.isfinite(scores).all()
            max_error = max(max_error, float(np.max(np.abs(scores - expected))))

    source_root = Path(__file__).resolve().parents[1]
    sources = [
        "benchmarks/compare_kernels.py",
        "benchmarks/benchmark_pipeline.py",
        "data_generator.py",
        "winery_adventures/computations.py",
        "winery_adventures/transformations.py",
        "winery_adventures/io.py",
        "winery_adventures/validation.py",
    ]
    medians = {name: statistics.median(values) for name, values in timings.items()}
    return {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "numba": numba.__version__,
            "numpy": np.__version__,
            "polars": pl.__version__,
            "numba_threads": numba.get_num_threads(),
            "git_revision": _git_revision(),
        },
        "source_sha256": {name: _sha256(source_root / name) for name in sources},
        "parameters": {
            "num_tanks": num_tanks,
            "num_readings": num_readings,
            "repetitions": repetitions,
            "seed": seed,
            "parallel_cache_enabled": True,
            "timing_mode": "warm (compilation and cache loading excluded)",
            "include_python": include_python,
        },
        "dataset": {
            "sensor_sha256": dataset["sensor_sha256"],
            "tank_info_sha256": dataset["tank_info_sha256"],
            "output_rows": transformed.height,
            "computable_rows": sum(len(group[0]) for group in groups),
            "ordered_pairs": ordered_pairs,
        },
        "seconds": timings,
        "median_seconds": medians,
        "speedup": medians["serial"] / medians["parallel"],
        "max_absolute_error": max_error,
        "scores_finite": True,
        "method": (
            "Same current formula and complete unexpanded readings across all variants. "
            "Python, when selected, executes the undecorated body; serial and parallel use Numba. "
            "Times include kernel calls and collection of scores, excluding data preparation and compilation. "
            "output_rows reports the total rows produced by the full pipeline after variety expansion, "
            "while computable_rows counts the valid unexpanded sensor readings evaluated by the kernels. "
            "This is not a benchmark of the historical repository revision."
        ),
    }


def main() -> None:
    """Read the comparison parameters and save the evidence as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tanks", type=int, default=100)
    parser.add_argument("--readings", type=int, default=100_000)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--include-python", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new file to preserve recorded evidence")
    results = compare_kernels(args.tanks, args.readings, args.repetitions, args.seed, args.include_python)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(results, indent=2) + "\n")
    print(f"Kernel comparison completed: results written to {args.output}")


if __name__ == "__main__":
    main()
