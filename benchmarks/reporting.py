"""Generate presentation charts or import existing benchmark evidence into W&B."""

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path


def measurement_series(report: dict) -> dict[str, list[float]]:
    """Extract finite, non-negative timing/memory samples from supported benchmark JSONs.

    Args:
        report: a pipeline, kernel, cache, or Joblib report produced by this package.

    Returns:
        Metric names mapped to raw samples, preserving repetition order.

    Raises:
        ValueError: if the report format, measurements, or correctness checks are invalid.
    """
    try:
        if report.get("kind") == "cache" or "seconds" in report:
            correctness = "outputs_match" if report.get("kind") == "joblib" else "scores_finite"
            if report[correctness] is not True:
                raise ValueError("Failed benchmark correctness check")
            series = {f"{key}_seconds": value for key, value in report["seconds"].items()}
            expected = (
                {"cold_seconds", "cached_seconds", "warm_seconds"}
                if report.get("kind") == "cache"
                else {"serial_seconds", "parallel_seconds"}
            )
            if report.get("kind") == "joblib":
                jobs = report["parameters"]["jobs"]
                if (
                    1 not in jobs
                    or len(set(jobs)) != len(jobs)
                    or any(type(j) is not int or j not in (1, 2, 4, -1) for j in jobs)
                ):
                    raise ValueError("Invalid Joblib worker configurations")
                expected = {f"{phase}_{j}_seconds" for j in jobs for phase in ("cold", "warm")}
            elif "python_seconds" in series and report.get("kind") != "cache":
                expected.add("python_seconds")
            if set(series) != expected:
                raise ValueError("Unexpected timing variants")
        else:
            iterations = report["iterations"]
            if not iterations or any(i["stress_scores_finite"] is not True for i in iterations):
                raise ValueError("Missing iterations or non-finite benchmark output")
            phases = list(iterations[0]["phases"])
            if any(set(i["phases"]) != set(phases) for i in iterations):
                raise ValueError("Inconsistent pipeline phases")
            series = {"total_seconds": [i["total_seconds"] for i in iterations]}
            for phase in phases:
                for metric in ("seconds", "python_peak_mib"):
                    series[f"{phase}_{metric}"] = [i["phases"][phase][metric] for i in iterations]
        repetitions = report["parameters"]["repetitions"]
        if not series or repetitions <= 0 or any(len(values) != repetitions for values in series.values()):
            raise ValueError("Sample count does not match repetitions")
        for values in series.values():
            if any(
                isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or v < 0 for v in values
            ):
                raise ValueError("Measurements must be finite non-negative numbers")
        error = report.get("max_absolute_error", 0.0)
        if not isinstance(error, (float, int)) or not math.isfinite(error) or error < 0:
            raise ValueError("Numerical error must be finite and non-negative")
        return series
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Unsupported or incomplete benchmark report") from exc


def relative_speedups(report: dict) -> dict[str, float]:
    """Compute ratios of median runtimes; values below one indicate a slowdown.

    Args:
        report: a validated benchmark report with raw timing samples.

    Returns:
        Ratios for the variants with strictly positive denominator medians.

    Raises:
        ValueError: if measurements or correctness checks are invalid.
    """
    medians = {key: statistics.median(value) for key, value in measurement_series(report).items()}
    pairs = {}
    if report.get("kind") == "joblib":
        pairs = {
            f"{phase}_{j}_speedup": (f"{phase}_1_seconds", f"{phase}_{j}_seconds")
            for phase in ("cold", "warm")
            for j in report["parameters"]["jobs"]
        }
    elif "serial_seconds" in medians:
        pairs = {"parallel_vs_serial_speedup": ("serial_seconds", "parallel_seconds")}
        if "python_seconds" in medians:
            pairs.update(
                {
                    f"{variant}_vs_python_speedup": ("python_seconds", f"{variant}_seconds")
                    for variant in ("serial", "parallel")
                }
            )
    return {
        name: medians[baseline] / medians[variant]
        for name, (baseline, variant) in pairs.items()
        if medians[variant] > 0
    }


def _load_report(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    measurement_series(report)
    return report


def _check_comparable(production: dict, legacy: dict) -> None:
    # Do not silently draw a before/after comparison of different workloads or source versions.
    if production["parameters"].get("order") != "hpc-first" or legacy["parameters"].get("order") != "transformer-first":
        raise ValueError("Expected production hpc-first and legacy transformer-first reports")
    for key in ("num_tanks", "num_readings", "seed", "repetitions"):
        if production["parameters"].get(key) != legacy["parameters"].get(key):
            raise ValueError(f"Pipeline reports differ in {key}")
    for key in ("sensor_sha256", "tank_info_sha256"):
        if not production.get("dataset", {}).get(key) or production["dataset"][key] != legacy["dataset"].get(key):
            raise ValueError(f"Pipeline reports differ in {key}")
    if (
        production.get("environment") != legacy.get("environment")
        or not production.get("source_sha256")
        or (production["source_sha256"] != legacy.get("source_sha256"))
    ):
        raise ValueError("Pipeline reports must share environment and recorded source fingerprints")
    if [i["output_rows"] for i in production["iterations"]] != [i["output_rows"] for i in legacy["iterations"]]:
        raise ValueError("Pipeline output row counts differ")


def _bars(ax, labels, groups, ylabel="Seconds", logarithmic=False):
    """Draw medians and observed min/max; log axes use points, not zero-based bars."""
    width = 0.75 / len(groups)
    colors = ("#6b7280", "#167d8d", "#8254a0")
    for index, (name, samples) in enumerate(groups.items()):
        medians = [statistics.median(values) for values in samples]
        positions = [x + (index - (len(groups) - 1) / 2) * width for x in range(len(labels))]
        errors = [
            [m - min(v) for m, v in zip(medians, samples, strict=True)],
            [max(v) - m for m, v in zip(medians, samples, strict=True)],
        ]
        color = colors[index % len(colors)]
        if logarithmic:
            # A log axis has no zero baseline: marker position represents the value.
            ax.errorbar(positions, medians, yerr=errors, fmt="o", label=name, color=color, capsize=4)
            for position, median, values in zip(positions, medians, samples, strict=True):
                ax.annotate(
                    f"{median:.4g}",
                    (position, max(values)),
                    xytext=(0, 8),
                    textcoords="offset points",
                    ha="center",
                    fontsize=9,
                )
        else:
            bars = ax.bar(positions, medians, width, label=name, color=color, yerr=errors, capsize=4)
            ax.bar_label(bars, labels=[f"{v:.4g}" for v in medians], padding=6, fontsize=9)
    ax.set_xticks(range(len(labels)), labels)
    ax.set_ylabel(ylabel)
    if logarithmic:
        ax.set_yscale("log")
    else:
        ax.set_ylim(bottom=0)
    ax.margins(y=0.22)
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    if len(groups) > 1:
        ax.legend()


def generate_charts(
    production: Path,
    legacy: Path,
    kernels: Path,
    output_dir: Path,
    cache: Path | None = None,
    joblib_report: Path | None = None,
) -> list[Path]:
    """Create PNG charts in Python with Matplotlib, without rerunning benchmarks.

    Args:
        production: HPC-first pipeline JSON.
        legacy: comparable Transformer-first pipeline JSON.
        kernels: controlled kernel JSON, optionally including Python (independent experiment).
        output_dir: destination, created if needed; same-named charts are regenerated.
        cache: optional fresh-process cache experiment JSON.
        joblib_report: optional generator worker-scaling report.

    Returns:
        Paths of the generated images.

    Raises:
        ValueError: for invalid or incomparable reports.
        ImportError: if the optional plotting dependencies are not installed.
        OSError: if an input or output cannot be accessed.
    """
    from matplotlib.figure import Figure

    prod, old, kernel = (_load_report(p) for p in (production, legacy, kernels))
    _check_comparable(prod, old)
    p, o, k = (measurement_series(r) for r in (prod, old, kernel))
    has_python = "python_seconds" in k
    if has_python and any(v <= 0 for values in k.values() for v in values):
        raise ValueError("Kernel timings must be positive for a logarithmic chart")
    charts = [
        (
            "pipeline-total",
            "Pipeline runtime: analyzer reordering",
            ["Full pipeline"],
            {"Transformer-first": [o["total_seconds"]], "HPC-first": [p["total_seconds"]]},
            False,
            [production, legacy],
        ),
        (
            "pipeline-phases",
            "Pipeline runtime by phase",
            ["Input I/O", "Preflight", "HPC", "Transformer", "Output I/O"],
            {
                "Transformer-first": [
                    o[f"{phase}_seconds"] for phase in ("input_io", "preflight", "hpc", "transformations", "output_io")
                ],
                "HPC-first": [
                    p[f"{phase}_seconds"] for phase in ("input_io", "preflight", "hpc", "transformations", "output_io")
                ],
            },
            False,
            [production, legacy],
        ),
        (
            "pipeline-memory",
            "Peak traced Python allocations by phase (not total process RAM)",
            ["Input I/O", "Preflight", "HPC", "Transformer", "Output I/O"],
            {
                "Transformer-first": [
                    o[f"{phase}_python_peak_mib"]
                    for phase in ("input_io", "preflight", "hpc", "transformations", "output_io")
                ],
                "HPC-first": [
                    p[f"{phase}_python_peak_mib"]
                    for phase in ("input_io", "preflight", "hpc", "transformations", "output_io")
                ],
            },
            False,
            [production, legacy],
        ),
        (
            "kernel-parallelism",
            (
                "Kernel runtime: Python vs Numba (not full pipeline)"
                if has_python
                else "Kernel runtime: Numba serial vs parallel"
            ),
            ["All tank kernels"],
            {
                **({"Python": [k["python_seconds"]]} if has_python else {}),
                "Numba serial": [k["serial_seconds"]],
                "Numba parallel": [k["parallel_seconds"]],
            },
            has_python,
            [kernels],
        ),
    ]
    if cache is not None:
        cache_report = _load_report(cache)
        if cache_report.get("kind") != "cache":
            raise ValueError("Expected a cache experiment")
        c = measurement_series(cache_report)
        if any(v <= 0 for values in c.values() for v in values):
            raise ValueError("Cache timings must be positive for a logarithmic chart")
        charts.append(
            (
                "numba-cache",
                "Numba call latency (imports and process startup excluded)",
                ["New process\nempty cache", "New process\npopulated cache", "Warm call\nsame process"],
                {"Latency": [c["cold_seconds"], c["cached_seconds"], c["warm_seconds"]]},
                True,
                [cache],
            )
        )
    # Validate the optional report before replacing any presentation images.
    if joblib_report is not None:
        report = _load_report(joblib_report)
        if report.get("kind") != "joblib":
            raise ValueError("Expected a Joblib experiment")
        series = measurement_series(report)
        if any(v <= 0 for values in series.values() for v in values):
            raise ValueError("Joblib timings must be positive for speedup charts")
        jobs = report["parameters"]["jobs"]
        if -1 in jobs:
            available = report.get("environment", {}).get("effective_workers", {}).get("-1")
            if type(available) is not int or available < 1:
                raise ValueError("Missing effective worker count for n_jobs=-1")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for stem, title, labels, groups, log_scale, sources in charts:
        figure = Figure(figsize=(11, 6))
        ax = figure.subplots()
        ylabel = (
            "Peak traced Python allocations (MiB)"
            if stem == "pipeline-memory"
            else ("Seconds (log scale)" if log_scale else "Seconds")
        )
        _bars(ax, labels, groups, ylabel=ylabel, logarithmic=log_scale)
        ax.set_title(title, pad=18, fontweight="bold")
        note = "Median; whiskers: observed min-max. Lower is better."
        if stem == "numba-cache":
            note += " Warm samples: one median per process pair."
        elif stem == "pipeline-memory":
            note += " Phase peaks are independent, not additive."
        elif stem == "kernel-parallelism" and has_python:
            ratios = relative_speedups(kernel)
            note += (
                f"\nPython / Numba parallel: {ratios['parallel_vs_python_speedup']:.2f}x; "
                f"Numba serial / parallel: {ratios['parallel_vs_serial_speedup']:.2f}x (same workload)."
            )
        elif stem in ("pipeline-total", "kernel-parallelism"):
            medians = [statistics.median(values[0]) for values in groups.values()]
            baseline, optimized = medians[0], medians[-1]
            if optimized > 0:
                note += f" Median speedup: {baseline / optimized:.2f}x."
        details = cache_report if stem == "numba-cache" else kernel if stem == "kernel-parallelism" else prod
        parameters = details["parameters"]
        workload = (
            f"{parameters.get('size')} readings in one synthetic tank"
            if stem == "numba-cache"
            else f"{parameters.get('num_readings'):,} readings; {parameters.get('num_tanks')} tanks"
        )
        figure.text(0.02, 0.10, f"{workload}; {parameters['repetitions']} repetitions", fontsize=9)
        figure.text(0.02, 0.045 if "\n" in note else 0.06, note, fontsize=9)
        figure.text(0.02, 0.025, "Sources: " + ", ".join(path.name for path in sources), fontsize=8)
        figure.tight_layout(rect=(0, 0.15, 1, 1))
        path = output_dir / f"{stem}.png"
        figure.savefig(path, dpi=180)
        paths.append(path)
        figure.clear()
    if joblib_report is not None:
        labels = [
            f"All available ({report['environment']['effective_workers']['-1']})" if j == -1 else str(j) for j in jobs
        ]
        figure = Figure(figsize=(11, 8))
        time_ax, speed_ax = figure.subplots(2, 1)
        _bars(
            time_ax,
            labels,
            {
                "First call": [series[f"cold_{j}_seconds"] for j in jobs],
                "Repeat call": [series[f"warm_{j}_seconds"] for j in jobs],
            },
        )
        time_ax.set_title("Joblib generator: execution time and scaling", fontweight="bold", pad=15)
        ratios = relative_speedups(report)
        for phase, label, color in (("cold", "First call", "#6b7280"), ("warm", "Repeat call", "#167d8d")):
            values = [ratios[f"{phase}_{j}_speedup"] for j in jobs]
            speed_ax.plot(range(len(jobs)), values, "o-", label=label, color=color)
            for x, value in enumerate(values):
                other_phase = "warm" if phase == "cold" else "cold"
                other_value = ratios[f"{other_phase}_{jobs[x]}_speedup"]
                above = value > other_value or (value == other_value and phase == "cold")
                # Keep labels for small speedups inside the axes, clear of worker labels.
                near_zero = value < 0.1 * max(1, max(ratios.values()))
                above = above or near_zero
                speed_ax.annotate(
                    f"{value:.2f}x",
                    (x, value),
                    xytext=(-12 if near_zero else 0, 9 if above else -14),
                    textcoords="offset points",
                    ha="right" if near_zero else "center",
                    fontsize=8,
                    color=color,
                )
        speed_ax.axhline(1, color="#8254a0", linestyle="--", label="Sequential baseline")
        speed_ax.set_xticks(range(len(jobs)), labels)
        speed_ax.set_xlabel("Joblib workers (not physical cores)")
        speed_ax.set_ylabel("Speedup vs 1 worker")
        speed_ax.set_ylim(0, max(1, max(ratios.values())) * 1.2)
        speed_ax.grid(axis="y", alpha=0.2)
        speed_ax.legend(fontsize=8)
        params = report["parameters"]
        figure.text(
            0.02,
            0.09,
            f"{params['num_readings']:,} readings; {params['num_tanks']} tanks; "
            f"{params['repetitions']} fresh processes per configuration; loky backend",
            fontsize=9,
        )
        figure.text(
            0.02,
            0.055,
            "Times: median and observed min-max. Speedup: ratio of medians; below 1 means slower.",
            fontsize=9,
        )
        figure.text(
            0.02,
            0.025,
            f"Source: {joblib_report.name}. First call includes pool startup; interpreter imports excluded.",
            fontsize=8,
        )
        figure.tight_layout(rect=(0, 0.13, 1, 1))
        path = output_dir / "joblib-scaling.png"
        figure.savefig(path, dpi=180)
        figure.clear()
        paths.append(path)
    return paths


def upload_report(
    path: Path, project: str, entity: str | None = None, group: str | None = None, mode: str = "online"
) -> str:
    """Import a JSON into one W&B run after measurement, preserving measured-code provenance.

    Args:
        path: existing pipeline, kernel, cache, or Joblib JSON; never modified.
        project: destination W&B project.
        entity: optional W&B account or team (not a GitHub owner).
        group: optional experiment group for comparable reports.
        mode: online upload or offline local recording for later synchronization.

    Returns:
        The newly created W&B run ID; each import creates a separate run.

    Raises:
        ValueError: for invalid report contents or an unsupported mode.
        Exception: W&B initialization, logging, artifact, or finalization errors.
    """
    report = _load_report(path)
    series = measurement_series(report)
    if mode not in ("online", "offline"):
        raise ValueError("mode must be online or offline")
    # Chart generation and report validation do not import the tracking SDK.
    import wandb

    kind = report.get("kind", "kernel" if "seconds" in report else "pipeline")
    # The importing checkout is not necessarily the measured version: disable automatic Git attribution.
    config = {
        "benchmark_kind": kind,
        "imported_report": True,
        "measurement_environment": report.get("environment", {}),
        "measurement_parameters": report["parameters"],
        "measurement_sources": report.get("source_sha256", {}),
        "measurement_dataset": report.get("dataset", {}),
        "measured_at_utc": report.get("measured_at_utc", "not recorded in original JSON"),
        "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    with wandb.init(
        project=project,
        entity=entity,
        group=group,
        name=path.stem,
        job_type="benchmark-import",
        config=config,
        mode=mode,
        reinit="create_new",
        settings=wandb.Settings(disable_git=True),
        save_code=False,
    ) as run:
        # Repetitions are measurements, not successive software versions or training epochs.
        for repetition in range(report["parameters"]["repetitions"]):
            run.log({"repetition": repetition + 1, **{name: values[repetition] for name, values in series.items()}})
        for name, values in series.items():
            run.summary[f"{name}_median"] = statistics.median(values)
            run.summary[f"{name}_min"] = min(values)
            run.summary[f"{name}_max"] = max(values)
        run.summary["outputs_match" if kind == "joblib" else "scores_finite"] = True
        for name, value in relative_speedups(report).items():
            run.summary[name] = value
        if "max_absolute_error" in report:
            run.summary["max_absolute_error"] = report["max_absolute_error"]
        if kind == "pipeline":
            run.summary["output_rows"] = report["iterations"][0]["output_rows"]
        artifact = wandb.Artifact(name=f"benchmark-{run.id}", type="benchmark-report")
        artifact.add_file(str(path))
        run.log_artifact(artifact)
        return run.id


def main() -> None:
    """Generate local charts or explicitly import one or more existing JSONs into W&B."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plots = commands.add_parser("plot", help="Generate local PNG charts with Matplotlib; no W&B connection")
    for argument in ("production", "legacy", "kernels", "output-dir"):
        plots.add_argument(f"--{argument}", type=Path, required=True)
    plots.add_argument("--cache", type=Path)
    plots.add_argument("--joblib", type=Path)
    upload = commands.add_parser("upload", help="Import recorded evidence, without running benchmarks")
    upload.add_argument("reports", nargs="+", type=Path)
    upload.add_argument("--project", required=True)
    upload.add_argument("--entity")
    upload.add_argument("--group")
    upload.add_argument("--mode", choices=("online", "offline"), default="online")
    args = parser.parse_args()
    if args.command == "plot":
        for path in generate_charts(
            args.production, args.legacy, args.kernels, args.output_dir, args.cache, args.joblib
        ):
            print(path)
    else:
        for path in args.reports:
            print(f"Imported {path}: run {upload_report(path, args.project, args.entity, args.group, args.mode)}")


if __name__ == "__main__":
    main()
