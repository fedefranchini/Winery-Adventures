"""Benchmark riproducibile delle fasi principali di Winery Adventures."""

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
    """Esegue una funzione misurando tempo e picco delle allocazioni Python."""
    # Avvia insieme il tracciamento della memoria e il cronometro ad alta risoluzione.
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
    """Restituisce il commit misurato, se il benchmark viene eseguito in un repository Git."""
    # Il commit permette di associare ogni misura a una versione precisa del codice.
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
    """Calcola l'impronta di un input per rendere verificabile la riproducibilità."""
    digest = hashlib.sha256()
    # Legge il file a blocchi per non caricare interamente in memoria dataset grandi.
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _create_dataset(data_dir: Path, num_tanks: int, num_readings: int, seed: int) -> dict[str, Any]:
    """Genera e salva una coppia di TSV deterministica per il benchmark."""
    # Lo stesso seed deve produrre gli stessi file e quindi le stesse impronte SHA-256.
    random.seed(seed)
    generation_started_at = time.perf_counter()

    variety_pool = generate_variety_pool(num_varieties=500)
    tank_info = generate_tank_info(num_tanks=num_tanks, variety_list=variety_pool)
    sensors = generate_sensor_data(num_tanks=num_tanks, num_readings=num_readings)

    sensor_path = data_dir / "benchmark_sensors.tsv"
    tank_info_path = data_dir / "benchmark_tank_info.tsv"

    # Materializza gli input su disco per includere il costo reale di lettura TSV.
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
    """Legge in parallelo i due input come avviene nell'orchestrazione applicativa."""
    # I thread sono adatti a queste due attività prevalentemente di I/O.
    sensors, tank_info = joblib.Parallel(n_jobs=2, prefer="threads")(
        [
            joblib.delayed(read_sensors)(str(sensor_path)),
            joblib.delayed(read_tank_info)(str(tank_info_path)),
        ]
    )
    return sensors, tank_info


def _run_iteration(sensor_path: Path, tank_info_path: Path, output_path: Path) -> dict[str, Any]:
    """Misura separatamente I/O, trasformazioni, calcolo HPC e scrittura."""
    iteration_started_at = time.perf_counter()

    # Ogni fase conserva il proprio tempo e picco di memoria per individuare il collo di bottiglia.
    inputs, input_seconds, input_peak_mib = _measure(lambda: _load_inputs(sensor_path, tank_info_path))
    sensors, tank_info = inputs

    transformed, transformation_seconds, transformation_peak_mib = _measure(
        lambda: WineryTransformer(tank_info).analyze_data(sensors)
    )
    computed, hpc_seconds, hpc_peak_mib = _measure(lambda: WineryHPCComputations().analyze_data(transformed))
    _, output_seconds, output_peak_mib = _measure(lambda: write_output(computed, str(output_path)))

    return {
        "total_seconds": time.perf_counter() - iteration_started_at,
        "output_rows": computed.height,
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
    """Aggrega più misurazioni usando mediana e intervallo osservato."""
    phase_summary = {}
    for phase in PHASES:
        # La mediana riduce l'influenza di singole esecuzioni insolitamente lente.
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
    """Genera gli input ed esegue una baseline ripetibile della pipeline."""
    if num_tanks <= 0 or num_readings <= 0 or repetitions <= 0:
        raise ValueError("num_tanks, num_readings and repetitions must be positive")

    # La prima chiamata compila Numba fuori dalla finestra temporale misurata.
    warmup_values = np.array([3.4], dtype=np.float64)
    pairwise_stress_function(warmup_values, warmup_values, warmup_values)

    # Input e output intermedi vengono eliminati automaticamente al termine dell'esecuzione.
    with tempfile.TemporaryDirectory(prefix="winery-benchmark-") as temporary_directory:
        data_dir = Path(temporary_directory)
        dataset = _create_dataset(data_dir, num_tanks, num_readings, seed)

        iterations = []
        # Ogni ripetizione riusa gli stessi input per rendere confrontabili le misure.
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
            "python_peak_mib misura le allocazioni Python tracciate; "
            "non include tutta la memoria nativa di Polars e Numba."
        ),
    }


def parse_args() -> argparse.Namespace:
    """Legge i parametri del benchmark dalla riga di comando."""
    parser = argparse.ArgumentParser(description="Misura tempo e memoria della pipeline Winery Adventures.")
    parser.add_argument("--tanks", type=int, default=100, help="Numero di cisterne da generare.")
    parser.add_argument("--readings", type=int, default=100_000, help="Numero di letture da generare.")
    parser.add_argument("--repetitions", type=int, default=3, help="Numero di misurazioni.")
    parser.add_argument("--seed", type=int, default=42, help="Seed del dataset riproducibile.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results.json"),
        help="File JSON in cui salvare misure e metadati.",
    )
    return parser.parse_args()


def main() -> None:
    """Esegue il benchmark e salva il risultato in formato JSON."""
    args = parse_args()
    results = run_benchmark(
        num_tanks=args.tanks,
        num_readings=args.readings,
        repetitions=args.repetitions,
        seed=args.seed,
    )
    # Il formato JSON conserva sia le singole misure sia il riepilogo aggregato.
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Benchmark completed: results written to {args.output}")


if __name__ == "__main__":
    main()
