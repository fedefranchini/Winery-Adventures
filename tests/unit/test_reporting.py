import copy
import json
import statistics
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import wandb

from benchmarks import reporting

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "benchmark-results"


@pytest.fixture
def reports():
    return {
        kind: json.loads((EVIDENCE / name).read_text(encoding="utf-8"))
        for kind, name in {
            "production": "pipeline-wa22-hpc-first.json",
            "legacy": "pipeline-wa22-transformer-first.json",
            "kernel": "kernels-wa22-hpc-first.json",
        }.items()
    }


@pytest.fixture
def joblib_report():
    return {
        "kind": "joblib",
        "parameters": {"repetitions": 2, "jobs": [1, 2, 4, -1], "num_readings": 100, "num_tanks": 2},
        "outputs_match": True,
        "seconds": {
            f"{phase}_{j}": [value, value]
            for phase in ("cold", "warm")
            for j, value in ((1, 1.0), (2, 4.0), (4, 2.0), (-1, 5.0))
        },
        "environment": {"effective_workers": {"-1": 8}},
        "source_sha256": {"generator.py": "measured-source"},
    }


@pytest.fixture
def cache_report():
    return {
        "kind": "cache",
        "parameters": {"repetitions": 2, "size": 8},
        "scores_finite": True,
        "seconds": {"cold": [1.0, 2.0], "cached": [0.1, 0.2], "warm": [0.001, 0.002]},
        "environment": {"git_revision": "measured-commit"},
        "source_sha256": {"kernel.py": "measured-source"},
        "max_absolute_error": 0.0,
    }


def test_reporting_recomputes_samples_from_raw_iterations(reports):
    report = reports["production"]
    # Cached summaries are not trusted when drawing or importing raw evidence.
    report["summary"]["median_total_seconds"] = 999
    series = reporting.measurement_series(report)
    assert series["total_seconds"] == [i["total_seconds"] for i in report["iterations"]]
    assert "hpc_python_peak_mib" in series


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -1, True])
def test_reporting_rejects_invalid_measurements(cache_report, invalid):
    cache_report["seconds"]["cold"][0] = invalid
    with pytest.raises(ValueError, match="finite non-negative"):
        reporting.measurement_series(cache_report)


def test_reporting_rejects_failed_or_incomplete_reports(cache_report):
    cache_report["scores_finite"] = False
    with pytest.raises(ValueError):
        reporting.measurement_series(cache_report)
    with pytest.raises(ValueError):
        reporting.measurement_series({})
    cache_report["scores_finite"] = True
    cache_report["parameters"]["repetitions"] = 3
    with pytest.raises(ValueError, match="Sample count"):
        reporting.measurement_series(cache_report)


@pytest.mark.parametrize("field", ["dataset", "environment", "source_sha256", "parameters"])
def test_chart_comparison_rejects_incomparable_runs(reports, field):
    legacy = copy.deepcopy(reports["legacy"])
    key = {"dataset": "sensor_sha256", "environment": "python", "source_sha256": "extra", "parameters": "seed"}[field]
    legacy[field][key] = "different"
    with pytest.raises(ValueError, match="differ|share"):
        reporting._check_comparable(reports["production"], legacy)


def test_generate_charts_creates_only_png_without_network(tmp_path, cache_report, monkeypatch):
    pytest.importorskip("matplotlib")
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps(cache_report), encoding="utf-8")
    init = MagicMock(side_effect=AssertionError("Plots must not initialize W&B"))
    monkeypatch.setattr(wandb, "init", init)
    paths = reporting.generate_charts(
        EVIDENCE / "pipeline-wa22-hpc-first.json",
        EVIDENCE / "pipeline-wa22-transformer-first.json",
        EVIDENCE / "kernels-wa22-hpc-first.json",
        tmp_path / "charts",
        cache_path,
    )
    assert len(paths) == 5
    assert set((tmp_path / "charts").iterdir()) == set(paths)
    for path in paths:
        assert path.suffix == ".png"
        assert path.stat().st_size > 1000
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    init.assert_not_called()


@pytest.mark.parametrize("kind", ["production", "kernel", "cache", "joblib", "python"])
def test_wandb_import_preserves_provenance_raw_samples_and_artifact(
    tmp_path, reports, cache_report, joblib_report, monkeypatch, kind
):
    reports.update(cache=cache_report, joblib=joblib_report, python=copy.deepcopy(reports["kernel"]))
    reports["python"]["seconds"]["python"] = [1.0] * reports["python"]["parameters"]["repetitions"]
    report = reports[kind]
    path = tmp_path / "recorded.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    before = path.read_bytes()
    run = MagicMock(id="import-run", summary={})
    context = MagicMock()
    context.__enter__.return_value = run
    init = MagicMock(return_value=context)
    artifact = MagicMock()
    monkeypatch.setattr(wandb, "init", init)
    monkeypatch.setattr(wandb, "Artifact", MagicMock(return_value=artifact))

    assert reporting.upload_report(path, "benchmarks", "team", "experiment", "offline") == "import-run"
    options = init.call_args.kwargs
    assert options["config"]["measurement_sources"] == report["source_sha256"]
    assert options["config"]["measurement_environment"] == report["environment"]
    assert options["config"]["imported_report"] is True
    assert options["settings"].disable_git and options["save_code"] is False
    assert options["mode"] == "offline" and options["group"] == "experiment"
    assert options["reinit"] == "create_new"
    assert run.log.call_count == report["parameters"]["repetitions"]
    first_metric = next(iter(reporting.measurement_series(report)))
    assert f"{first_metric}_median" in run.summary
    for name, value in reporting.relative_speedups(report).items():
        assert run.summary[name] == value
    if kind == "joblib":
        assert run.summary["outputs_match"] is True
        assert "scores_finite" not in run.summary
    artifact.add_file.assert_called_once_with(str(path))
    run.log_artifact.assert_called_once_with(artifact)
    context.__exit__.assert_called_once()
    assert before == path.read_bytes()


def test_wandb_import_failure_propagates_and_closes_context(tmp_path, cache_report, monkeypatch):
    path = tmp_path / "recorded.json"
    path.write_text(json.dumps(cache_report), encoding="utf-8")
    run = MagicMock()
    run.log.side_effect = RuntimeError("upload failed")
    context = MagicMock()
    context.__enter__.return_value = run
    context.__exit__.return_value = False
    monkeypatch.setattr(wandb, "init", MagicMock(return_value=context))
    with pytest.raises(RuntimeError, match="upload failed"):
        reporting.upload_report(path, "benchmarks")
    assert context.__exit__.call_args.args[0] is RuntimeError


def test_wandb_import_validates_before_opening_run(tmp_path, monkeypatch):
    path = tmp_path / "invalid.json"
    path.write_text("{}", encoding="utf-8")
    init = MagicMock()
    monkeypatch.setattr(wandb, "init", init)
    with pytest.raises(ValueError):
        reporting.upload_report(path, "benchmarks")
    init.assert_not_called()


def test_extended_charts_and_speedups_preserve_slowdowns(tmp_path, reports, joblib_report, monkeypatch):
    pytest.importorskip("matplotlib")
    kernel = reports["kernel"]
    kernel["seconds"]["python"] = [1.0] * kernel["parameters"]["repetitions"]
    kernel_path, jobs_path = tmp_path / "kernel.json", tmp_path / "jobs.json"
    kernel_path.write_text(json.dumps(kernel), encoding="utf-8")
    jobs_path.write_text(json.dumps(joblib_report), encoding="utf-8")
    init = MagicMock(side_effect=AssertionError("No W&B during plotting"))
    monkeypatch.setattr(wandb, "init", init)
    paths = reporting.generate_charts(
        EVIDENCE / "pipeline-wa22-hpc-first.json",
        EVIDENCE / "pipeline-wa22-transformer-first.json",
        kernel_path,
        tmp_path / "plots",
        joblib_report=jobs_path,
    )
    assert len(paths) == 5 and paths[-1].name == "joblib-scaling.png"
    assert all(p.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for p in paths)
    assert reporting.relative_speedups(joblib_report)["cold_2_speedup"] == 0.25
    assert reporting.relative_speedups(joblib_report)["warm_1_speedup"] == 1
    assert "serial_vs_python_speedup" in reporting.relative_speedups(kernel)
    init.assert_not_called()


@pytest.mark.parametrize("fault", ["correctness", "variant", "jobs", "samples"])
def test_reporting_rejects_invalid_joblib_evidence(joblib_report, fault):
    if fault == "correctness":
        joblib_report["outputs_match"] = False
    elif fault == "variant":
        del joblib_report["seconds"]["cold_2"]
    elif fault == "jobs":
        joblib_report["parameters"]["jobs"] = [2]
    else:
        joblib_report["seconds"]["warm_1"] = [1.0]
    with pytest.raises(ValueError):
        reporting.measurement_series(joblib_report)


def test_invalid_joblib_chart_does_not_replace_existing_png(tmp_path, joblib_report):
    pytest.importorskip("matplotlib")
    joblib_report["seconds"]["warm_1"] = [0.0, 0.0]
    path = tmp_path / "joblib.json"
    path.write_text(json.dumps(joblib_report), encoding="utf-8")
    plots = tmp_path / "plots"
    plots.mkdir()
    existing = plots / "pipeline-total.png"
    existing.write_bytes(b"original")
    with pytest.raises(ValueError, match="positive"):
        reporting.generate_charts(
            EVIDENCE / "pipeline-wa22-hpc-first.json",
            EVIDENCE / "pipeline-wa22-transformer-first.json",
            EVIDENCE / "kernels-wa22-hpc-first.json",
            plots,
            joblib_report=path,
        )
    assert existing.read_bytes() == b"original"
    assert list(plots.iterdir()) == [existing]


@pytest.mark.parametrize("path", sorted(EVIDENCE.glob("*.json")), ids=lambda path: path.name)
def test_archived_benchmark_reports_have_valid_measurements(path):
    # Validate recorded evidence too, not only synthetic report fixtures.
    report = json.loads(path.read_text(encoding="utf-8"))
    assert reporting.measurement_series(report)


def test_plot_cli_runs_without_importing_wandb(tmp_path):
    pytest.importorskip("matplotlib")
    # A fresh interpreter prevents other tests from preloading the optional SDK.
    command = [
        sys.executable,
        "-c",
        "import sys; sys.modules['wandb'] = None; from benchmarks.reporting import main; main()",
        "plot",
        "--production",
        str(EVIDENCE / "pipeline-wa22-hpc-first.json"),
        "--legacy",
        str(EVIDENCE / "pipeline-wa22-transformer-first.json"),
        "--kernels",
        str(EVIDENCE / "kernels-wa22-python-numba.json"),
        "--cache",
        str(EVIDENCE / "cache-wa22.json"),
        "--joblib",
        str(EVIDENCE / "joblib-wa22.json"),
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, cwd=EVIDENCE.parents[1], timeout=60)
    assert result.returncode == 0, result.stderr
    paths = list(tmp_path.iterdir())
    assert len(paths) == 6
    assert all(path.suffix == ".png" for path in paths)


def test_charts_show_recorded_memory_log_markers_and_kernel_ratio(tmp_path, reports, monkeypatch):
    pytest.importorskip("matplotlib")
    from matplotlib.figure import Figure

    captured = {}

    def capture(figure, path, **kwargs):
        ax = figure.axes[0]
        captured[path.stem] = {
            "ylabel": ax.get_ylabel(),
            "scale": ax.get_yscale(),
            "heights": [patch.get_height() for patch in ax.patches],
            "lines": len(ax.lines),
            "notes": "\n".join(t.get_text() for t in figure.texts),
        }

    monkeypatch.setattr(Figure, "savefig", capture)
    reporting.generate_charts(
        EVIDENCE / "pipeline-wa22-hpc-first.json",
        EVIDENCE / "pipeline-wa22-transformer-first.json",
        EVIDENCE / "kernels-wa22-python-numba.json",
        tmp_path,
        EVIDENCE / "cache-wa22.json",
    )
    memory = captured["pipeline-memory"]
    assert memory["ylabel"] == "Peak traced Python allocations (MiB)"
    expected = [
        statistics.median(reporting.measurement_series(reports[kind])[f"{phase}_python_peak_mib"])
        for kind in ("legacy", "production")
        for phase in ("input_io", "preflight", "hpc", "transformations", "output_io")
    ]
    assert memory["heights"] == pytest.approx(expected)
    for name in ("kernel-parallelism", "numba-cache"):
        assert captured[name]["scale"] == "log"
        assert captured[name]["heights"] == []
        assert captured[name]["lines"] > 0
    kernel = json.loads((EVIDENCE / "kernels-wa22-python-numba.json").read_text(encoding="utf-8"))
    ratio = reporting.relative_speedups(kernel)["parallel_vs_serial_speedup"]
    assert f"Numba serial / parallel: {ratio:.2f}x (same workload)" in captured["kernel-parallelism"]["notes"]
