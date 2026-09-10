"""Measure generator scaling with fresh processes and repeat calls using Joblib."""

import argparse
import hashlib
import json
import platform
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib

from benchmarks.benchmark_pipeline import _git_revision, _sha256
from data_generator import generate_sensor_data


def _fingerprint(rows: list[dict]) -> str:
    """Hash ordered records, including null values, independently of worker scheduling."""
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _worker(num_tanks: int, num_readings: int, seed: int, n_jobs: int) -> dict:
    result = {"effective_workers": joblib.effective_n_jobs(n_jobs)}
    # A fresh interpreter owns this pool; the second call can reuse the loky executor.
    with joblib.parallel_config(backend="loky", inner_max_num_threads=1):
        for phase in ("cold", "warm"):
            random.seed(seed)
            started = time.perf_counter()
            rows = generate_sensor_data(num_tanks, num_readings, n_jobs=n_jobs, show_progress=False)
            elapsed = time.perf_counter() - started
            result[phase] = {"seconds": elapsed, "output_sha256": _fingerprint(rows), "output_rows": len(rows)}
    return result


def compare_joblib(
    num_tanks: int = 100,
    num_readings: int = 10_000,
    repetitions: int = 3,
    seed: int = 42,
    jobs: tuple[int, ...] = (1, 2, 4, -1),
) -> dict:
    """Time the real generator with sequential and process-based execution.

    Args:
        num_tanks: positive number of tank identifiers.
        num_readings: positive number of generated records per call.
        repetitions: positive number of fresh-process measurements per variant.
        seed: fixed seed reused for every call.
        jobs: unique worker configurations from 1, 2, 4, -1; must include 1.

    Returns:
        Timings, environment, source hashes, and exact ordered-output verification.

    Raises:
        ValueError: for invalid sizes or worker configurations.
        AssertionError: if any variant changes the generated records.
        subprocess.SubprocessError: if a worker fails or exceeds five minutes.
    """
    if min(num_tanks, num_readings, repetitions) <= 0:
        raise ValueError("Workload and repetitions must be positive")
    if 1 not in jobs or len(set(jobs)) != len(jobs) or any(type(j) is not int or j not in (1, 2, 4, -1) for j in jobs):
        raise ValueError("jobs must contain unique values from 1, 2, 4, -1, including 1")
    # The untimed sequential reference uses exactly the same public generator.
    random_state = random.getstate()
    try:
        random.seed(seed)
        expected = _fingerprint(generate_sensor_data(num_tanks, num_readings, n_jobs=1, show_progress=False))
    finally:
        random.setstate(random_state)
    root = Path(__file__).resolve().parents[1]
    seconds = {f"{phase}_{j}": [] for j in jobs for phase in ("cold", "warm")}
    iterations = []
    effective_workers = {}
    for repetition in range(repetitions):
        offset = repetition % len(jobs)
        order = jobs[offset:] + jobs[:offset]
        measurements = {}
        for n_jobs in order:
            command = [
                sys.executable,
                "-m",
                "benchmarks.compare_joblib",
                "--worker",
                "--tanks",
                str(num_tanks),
                "--readings",
                str(num_readings),
                "--seed",
                str(seed),
                "--jobs",
                str(n_jobs),
            ]
            completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=300)
            measured = json.loads(completed.stdout)
            effective_workers[str(n_jobs)] = measured["effective_workers"]
            for phase in ("cold", "warm"):
                sample = measured[phase]
                if sample["output_sha256"] != expected or sample["output_rows"] != num_readings:
                    raise AssertionError("Joblib configuration changed generated records")
                seconds[f"{phase}_{n_jobs}"].append(sample["seconds"])
            measurements[str(n_jobs)] = measured
        iterations.append({"order": list(order), "measurements": measurements})
    sources = ("benchmarks/compare_joblib.py", "benchmarks/benchmark_pipeline.py", "data_generator.py")
    return {
        "kind": "joblib",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "joblib": joblib.__version__,
            "available_cpus": joblib.cpu_count(),
            "effective_workers": effective_workers,
            "git_revision": _git_revision(),
        },
        "parameters": {
            "num_tanks": num_tanks,
            "num_readings": num_readings,
            "repetitions": repetitions,
            "seed": seed,
            "jobs": list(jobs),
            "backend": "loky",
            "inner_max_num_threads": 1,
        },
        "source_sha256": {name: _sha256(root / name) for name in sources},
        "dataset": {"output_sha256": expected, "output_rows": num_readings},
        "seconds": seconds,
        "median_seconds": {key: statistics.median(value) for key, value in seconds.items()},
        "iterations": iterations,
        "outputs_match": True,
        "method": "Each configuration/repetition starts in a fresh interpreter. Cold includes pool startup; "
        "warm is a second generator call eligible for executor reuse. Both include row seeds, scheduling, "
        "serialization and result collection; exclude interpreter startup, imports, hashing and file I/O. "
        "n_jobs=1 is sequential and has no worker pool. Worker counts are not physical core counts. "
        "The same seed produces exactly identical ordered records across every call. "
        "These are generator timings, not pipeline I/O or Numba timings.",
    }


def main() -> None:
    """Save new evidence without overwriting previous measurements, or run one private worker."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tanks", type=int, default=100)
    parser.add_argument("--readings", type=int, default=10_000)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--jobs", nargs="+", type=int, default=[1, 2, 4, -1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(_worker(args.tanks, args.readings, args.seed, args.jobs[0])))
        return
    if args.output is None or args.output.exists():
        parser.error("Provide --output with a new filename to preserve recorded evidence")
    report = compare_joblib(args.tanks, args.readings, args.repetitions, args.seed, tuple(args.jobs))
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(f"Joblib comparison completed: {args.output}")


if __name__ == "__main__":
    main()
