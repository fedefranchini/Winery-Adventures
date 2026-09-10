"""Measure Numba first-call latency in fresh processes with empty and populated caches."""

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numba
import numpy as np

from benchmarks.benchmark_pipeline import _git_revision, _sha256
from winery_adventures.computations import pairwise_stress_function


def _worker(size: int, warm_calls: int) -> dict:
    """Time actual kernel calls, excluding Python startup, imports, and array construction."""
    arrays = [np.linspace(low, high, size) for low, high in [(3.0, 4.0), (22.0, 28.0), (200.0, 1000.0)]]
    # Match the read-only Float64 arrays normally supplied by Polars.
    for values in arrays:
        values.flags.writeable = False
    started = time.perf_counter()
    score = pairwise_stress_function(*arrays)
    first_seconds = time.perf_counter() - started
    warmed = []
    for _ in range(warm_calls):
        started = time.perf_counter()
        repeated_score = pairwise_stress_function(*arrays)
        warmed.append(time.perf_counter() - started)
        np.testing.assert_allclose(repeated_score, score, rtol=1e-10, atol=1e-10)

    # An independent NumPy expression checks the full ordered-pair formula, including the diagonal.
    ph, temp, quantity = arrays
    reference = np.mean(
        (np.abs(ph[:, None] - ph) + 2 * np.abs(temp[:, None] - temp)) * (500 / quantity[:, None] + 500 / quantity)
    )
    np.testing.assert_allclose(score, reference, rtol=1e-10, atol=1e-10)
    if not np.isfinite(score):
        raise ValueError("Cache benchmark produced non-finite stress")
    return {
        "first_call_seconds": first_seconds,
        "warm_call_seconds": warmed,
        "score": float(score),
        "max_absolute_error": float(abs(score - reference)),
        "cache_hits": sum(pairwise_stress_function.stats.cache_hits.values()),
        "cache_misses": sum(pairwise_stress_function.stats.cache_misses.values()),
        "input_sha256": hashlib.sha256(b"".join(a.tobytes() for a in arrays)).hexdigest(),
        "numba_threads": numba.get_num_threads(),
    }


def compare_cache(size: int = 256, repetitions: int = 3, warm_calls: int = 5) -> dict:
    """Compare first-call compilation, disk-cache loading, and warm execution.

    Args:
        size: positive readings per synthetic tank (at most 4096 for the reference check).
        repetitions: positive number of independent cold/cached process pairs.
        warm_calls: positive repeated calls per worker after its first call.

    Returns:
        Raw timings, observed cache hits, correctness checks, and source provenance.

    Raises:
        ValueError: for invalid sizes or unexpected cache behavior.
        subprocess.SubprocessError: if a worker fails or exceeds five minutes.
    """
    if not 0 < size <= 4096 or min(repetitions, warm_calls) <= 0:
        raise ValueError("size must be between 1 and 4096; repetitions and warm_calls must be positive")
    iterations = []
    for _ in range(repetitions):
        # Only this benchmark's temporary cache is removed, never the application's cache.
        with tempfile.TemporaryDirectory(prefix="winery-cache-") as directory:
            environment = dict(os.environ, NUMBA_CACHE_DIR=directory, NUMBA_DEBUG_CACHE="0", NUMBA_DISABLE_JIT="0")
            pair = []
            for _state in ("cold", "cached"):
                process = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "benchmarks.compare_cache",
                        "--worker",
                        "--size",
                        str(size),
                        "--warm-calls",
                        str(warm_calls),
                    ],
                    cwd=Path(__file__).resolve().parents[1],
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=300,
                )
                pair.append(json.loads(process.stdout))
            cold, cached = pair
            if (
                cold["cache_hits"] != 0
                or cold["cache_misses"] < 1
                or cached["cache_hits"] < 1
                or cached["cache_misses"]
            ):
                raise ValueError("Expected compilation with an empty cache and a cache hit in the next process")
            if cold["input_sha256"] != cached["input_sha256"]:
                raise ValueError("Cache workers used different inputs")
            np.testing.assert_allclose(cold["score"], cached["score"], rtol=1e-10, atol=1e-10)
            iterations.append({"cold": cold, "cached": cached})
    seconds = {
        "cold": [pair["cold"]["first_call_seconds"] for pair in iterations],
        "cached": [pair["cached"]["first_call_seconds"] for pair in iterations],
        # One warm median per process pair avoids treating inner calls as independent experiments.
        "warm": [statistics.median(pair["cached"]["warm_call_seconds"]) for pair in iterations],
    }
    root = Path(__file__).resolve().parents[1]
    return {
        "kind": "cache",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "numpy": np.__version__,
            "numba": numba.__version__,
            "numba_threads": iterations[0]["cached"]["numba_threads"],
            "git_revision": _git_revision(),
        },
        "source_sha256": {
            p: _sha256(root / p)
            for p in [
                "benchmarks/compare_cache.py",
                "benchmarks/benchmark_pipeline.py",
                "winery_adventures/computations.py",
                "winery_adventures/base.py",
                "winery_adventures/validation.py",
            ]
        },
        "parameters": {"size": size, "repetitions": repetitions, "warm_calls": warm_calls, "cache_enabled": True},
        "dataset": {"input_sha256": iterations[0]["cold"]["input_sha256"]},
        "iterations": iterations,
        "seconds": seconds,
        "median_seconds": {name: statistics.median(values) for name, values in seconds.items()},
        "scores_finite": True,
        "max_absolute_error": max(p[state]["max_absolute_error"] for p in iterations for state in ("cold", "cached")),
        "method": "First kernel call only, not total program startup. Cold and cached calls use distinct processes. "
        "Imports, input construction, and correctness checks are excluded. Warm values are per-pair medians.",
    }


def main() -> None:
    """Run the cache experiment and write a new JSON without overwriting earlier evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--warm-calls", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(_worker(args.size, args.warm_calls)))
        return
    if args.output is None:
        parser.error("--output is required")
    if args.output.exists():
        parser.error("output already exists; choose a new filename to preserve previous measurements")
    result = compare_cache(args.size, args.repetitions, args.warm_calls)
    with args.output.open("x", encoding="utf-8") as destination:
        destination.write(json.dumps(result, indent=2) + "\n")
    print(f"Cache comparison written to {args.output}")


if __name__ == "__main__":
    main()
