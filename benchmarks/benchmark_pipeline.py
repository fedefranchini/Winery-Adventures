"""Reproducible benchmark of the main phases of Winery Adventures."""

import argparse
import hashlib
import json
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import joblib
import numba
import numpy as np
import polars as pl

from data_generator import generate_sensor_data, generate_tank_info, generate_variety_pool
from winery_adventures.computations import WineryHPCComputations, pairwise_stress_function
from winery_adventures.io import read_sensors, read_tank_info, write_output
from winery_adventures.transformations import WineryTransformer

ResultT = TypeVar("ResultT")
PHASES = ("input_io", "transformations", "hpc", "output_io")


def _measure(function: Callable[[], ResultT]) -> tuple[ResultT, float, float]:
    """Run a function, measuring time and the peak of Python allocations."""
    # Start memory tracing and the high-resolution timer together.
    tracemalloc.start()
    started_at = time.perf_counter()
    try:
        result = function()
        elapsed_seconds = time.perf_counter() - started_at
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    return result, elapsed_seconds, peak_bytes / (1024 * 1024)


def _git_revision() -> str:
    """Return the base commit, if the benchmark runs inside a Git repository."""
    # HEAD alone does not identify any uncommitted changes.
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _sha256(path: Path) -> str:
    """Compute an input's fingerprint to make reproducibility verifiable."""
    digest = hashlib.sha256()
    # Read the file in chunks to avoid loading large datasets entirely into memory.
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _create_dataset(data_dir: Path, num_tanks: int, num_readings: int, seed: int) -> dict[str, Any]:
    """Generate and save a deterministic pair of TSV files for the benchmark."""
    # The same seed must produce the same files and therefore the same SHA-256 hashes.
    random.seed(seed)
    generation_started_at = time.perf_counter()

    variety_pool = generate_variety_pool(num_varieties=500)
    tank_info = generate_tank_info(num_tanks=num_tanks, variety_list=variety_pool)
    sensors = generate_sensor_data(num_tanks=num_tanks, num_readings=num_readings)

    sensor_path = data_dir / "benchmark_sensors.tsv"
    tank_info_path = data_dir / "benchmark_tank_info.tsv"

    # Write the inputs to disk to include the actual cost of reading TSV files.
    pl.DataFrame(tank_info, schema=["tank_id", "grape_variety", "capacity_liters"]).write_csv(
        tank_info_path,
        separator="\t",
    )
    pl.DataFrame(sensors, schema=["tank_id", "time", "pH", "temp", "quantity_liters"]).write_csv(
        sensor_path,
        separator="\t",
    )

    return {
        "sensor_path": sensor_path,
        "tank_info_path": tank_info_path,
        "generation_seconds": time.perf_counter() - generation_started_at,
        "sensor_sha256": _sha256(sensor_path),
        "tank_info_sha256": _sha256(tank_info_path),
    }


def _load_inputs(sensor_path: Path, tank_info_path: Path) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Read the two inputs in parallel, as in the application orchestration."""
    # Threads are suitable for these two predominantly I/O-bound tasks.
    sensors, tank_info = joblib.Parallel(n_jobs=2, prefer="threads")(
        [
            joblib.delayed(read_sensors)(str(sensor_path)),
            joblib.delayed(read_tank_info)(str(tank_info_path)),
        ]
    )
    return sensors, tank_info


def _run_iteration(sensor_path: Path, tank_info_path: Path, output_path: Path) -> dict[str, Any]:
    """Separately measure I/O, transformations, HPC computation, and writing."""
    iteration_started_at = time.perf_counter()

    # Each phase records its time and peak memory to identify the bottleneck.
    inputs, input_seconds, input_peak_mib = _measure(lambda: _load_inputs(sensor_path, tank_info_path))
    sensors, tank_info = inputs

    transformed, transformation_seconds, transformation_peak_mib = _measure(
        lambda: WineryTransformer(tank_info).analyze_data(sensors)
    )
    computed, hpc_seconds, hpc_peak_mib = _measure(lambda: WineryHPCComputations().analyze_data(transformed))

    # A performance measurement is valid only if the computation produces
    # numerically usable scores, even when quantities are missing.
    stress_scores = computed.get_column("stress_score")
    stress_scores_finite = stress_scores.null_count() == 0 and stress_scores.is_finite().all()
    if not stress_scores_finite:
        raise RuntimeError("Benchmark produced non-finite stress scores")

    _, output_seconds, output_peak_mib = _measure(lambda: write_output(computed, str(output_path)))

    return {
        "total_seconds": time.perf_counter() - iteration_started_at,
        "output_rows": computed.height,
        "stress_scores_finite": stress_scores_finite,
        "phases": {
            "input_io": {"seconds": input_seconds, "python_peak_mib": input_peak_mib},
            "transformations": {
                "seconds": transformation_seconds,
                "python_peak_mib": transformation_peak_mib,
            },
            "hpc": {"seconds": hpc_seconds, "python_peak_mib": hpc_peak_mib},
            "output_io": {"seconds": output_seconds, "python_peak_mib": output_peak_mib},
        },
    }


def _summarize(iterations: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate multiple measurements using the median and observed range."""
    phase_summary = {}
    for phase in PHASES:
        # The median reduces the influence of individual unusually slow runs.
        seconds = [iteration["phases"][phase]["seconds"] for iteration in iterations]
        peak_memory = [iteration["phases"][phase]["python_peak_mib"] for iteration in iterations]
        phase_summary[phase] = {
            "median_seconds": statistics.median(seconds),
            "min_seconds": min(seconds),
            "max_seconds": max(seconds),
            "max_python_peak_mib": max(peak_memory),
        }

    total_seconds = [iteration["total_seconds"] for iteration in iterations]
    return {
        "median_total_seconds": statistics.median(total_seconds),
        "min_total_seconds": min(total_seconds),
        "max_total_seconds": max(total_seconds),
        "phases": phase_summary,
    }


def run_benchmark(
    num_tanks: int = 100,
    num_readings: int = 100_000,
    repetitions: int = 3,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate the inputs and run a repeatable baseline of the pipeline.

    Args:
        num_tanks: positive number of tanks generated.
        num_readings: positive number of readings generated.
        repetitions: positive number of measured iterations.
        seed: seed shared by the generation of the two inputs.

    Returns:
        Environment, parameters, input fingerprints, individual
        measurements, and summary.

    Raises:
        ValueError: if a size or the number of repetitions is not positive,
            or if the generated data cannot be processed.
        RuntimeError: if an iteration produces null or non-finite scores.
        OSError: if a temporary file cannot be read or written.
    """
    if num_tanks <= 0 or num_readings <= 0 or repetitions <= 0:
        raise ValueError("num_tanks, num_readings and repetitions must be positive")

    # The first call triggers Numba compilation outside the measured time window.
    # Polars returns read-only arrays: Numba treats them as a distinct signature,
    # so warm-up must cover both variants; otherwise, compilation would occur
    # within the first measured iteration.
    warmup_values = np.array([3.4], dtype=np.float64)
    pairwise_stress_function(warmup_values, warmup_values, warmup_values)
    readonly_warmup_values = warmup_values.copy()
    readonly_warmup_values.flags.writeable = False
    pairwise_stress_function(readonly_warmup_values, readonly_warmup_values, readonly_warmup_values)

    # Intermediate inputs and outputs are automatically deleted when execution finishes.
    with tempfile.TemporaryDirectory(prefix="winery-benchmark-") as temporary_directory:
        data_dir = Path(temporary_directory)
        dataset = _create_dataset(data_dir, num_tanks, num_readings, seed)

        iterations = []
        # Each repetition reuses the same inputs to make the measurements comparable.
        for repetition in range(repetitions):
            output_path = data_dir / f"result-{repetition + 1}.csv"
            iterations.append(_run_iteration(dataset["sensor_path"], dataset["tank_info_path"], output_path))

    return {
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "git_revision": _git_revision(),
            "polars": pl.__version__,
            "numba": numba.__version__,
            "joblib": joblib.__version__,
        },
        "parameters": {
            "num_tanks": num_tanks,
            "num_readings": num_readings,
            "repetitions": repetitions,
            "seed": seed,
        },
        "dataset": {
            "generation_seconds": dataset["generation_seconds"],
            "sensor_sha256": dataset["sensor_sha256"],
            "tank_info_sha256": dataset["tank_info_sha256"],
        },
        "iterations": iterations,
        "summary": _summarize(iterations),
        "memory_note": (
            "python_peak_mib measures traced Python allocations; "
            "it does not include all the native memory used by Polars and Numba."
        ),
    }


def parse_args() -> argparse.Namespace:
    """Read the benchmark parameters from the command line."""
    parser = argparse.ArgumentParser(description="Measure time and memory of the Winery Adventures pipeline.")
    parser.add_argument("--tanks", type=int, default=100, help="Number of tanks to generate.")
    parser.add_argument("--readings", type=int, default=100_000, help="Number of readings to generate.")
    parser.add_argument("--repetitions", type=int, default=3, help="Number of measurements.")
    parser.add_argument("--seed", type=int, default=42, help="Seed for the reproducible dataset.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results.json"),
        help="JSON file to save measurements and metadata to.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the benchmark and save the result in JSON format."""
    args = parse_args()
    results = run_benchmark(
        num_tanks=args.tanks,
        num_readings=args.readings,
        repetitions=args.repetitions,
        seed=args.seed,
    )
    # The JSON format preserves both individual measurements and the aggregated summary.
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Benchmark completed: results written to {args.output}")


if __name__ == "__main__":
    main()
