import json
from types import SimpleNamespace

import pytest

from benchmarks import compare_cache


def test_cache_comparison_uses_fresh_processes_and_preserves_results(tmp_path, monkeypatch):
    # Exercise real Numba disk-cache misses and hits, not a mocked speedup.
    monkeypatch.setattr(compare_cache.tempfile, "tempdir", str(tmp_path))
    report = compare_cache.compare_cache(size=8, repetitions=1, warm_calls=2)
    pair = report["iterations"][0]
    assert pair["cold"]["cache_misses"] == 1 and pair["cold"]["cache_hits"] == 0
    assert pair["cached"]["cache_hits"] == 1 and pair["cached"]["cache_misses"] == 0
    assert pair["cold"]["score"] == pytest.approx(pair["cached"]["score"])
    assert report["scores_finite"] is True and report["max_absolute_error"] < 1e-10
    assert all(v >= 0 for values in report["seconds"].values() for v in values)
    assert not list(tmp_path.glob("winery-cache-*"))


@pytest.mark.parametrize("arguments", [{"size": 0}, {"size": 4097}, {"repetitions": 0}, {"warm_calls": 0}])
def test_cache_comparison_rejects_invalid_workload(arguments):
    with pytest.raises(ValueError):
        compare_cache.compare_cache(**arguments)


def test_cache_comparison_rejects_unexpected_cache_behavior(monkeypatch):
    # A supposedly cold process must not already have loaded a specialization.
    monkeypatch.setattr(
        compare_cache.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(stdout=json.dumps({"cache_hits": 1, "cache_misses": 0})),
    )
    with pytest.raises(ValueError, match="Expected compilation"):
        compare_cache.compare_cache(size=8, repetitions=1)


def test_cache_cli_preserves_existing_evidence(tmp_path, monkeypatch):
    path = tmp_path / "existing.json"
    path.write_text("original", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["compare_cache", "--output", str(path)])
    with pytest.raises(SystemExit):
        compare_cache.main()
    assert path.read_text(encoding="utf-8") == "original"
