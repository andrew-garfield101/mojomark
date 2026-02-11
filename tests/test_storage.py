"""Tests for mojomark result storage."""

import json
import tempfile
from pathlib import Path

from mojomark.runner import BenchmarkResult
from mojomark.storage import (
    find_results_for_version,
    list_result_files,
    load_results,
    save_results,
)


def _make_result(name="fib", category="compute", samples=None):
    """Helper to build a BenchmarkResult."""
    return BenchmarkResult(
        name=name,
        category=category,
        samples_ns=samples or [100_000, 110_000, 105_000],
    )


# ---------------------------------------------------------------------------
# save + load roundtrip
# ---------------------------------------------------------------------------


class TestSaveAndLoad:
    def test_roundtrip_preserves_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = [_make_result(), _make_result("sort", "compute", [50_000, 55_000])]
            path = save_results(results, "0.8.0", results_dir=Path(tmpdir))

            assert path.exists()
            data = load_results(path)

            # Valid JSON with correct schema
            assert data["mojo_version"] == "0.8.0"
            assert "timestamp" in data
            assert len(data["benchmarks"]) == 2
            assert data["benchmarks"][0]["name"] == "fib"
            assert data["benchmarks"][0]["stats"]["samples"] == 3

    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "deep" / "nested"
            path = save_results([_make_result()], "0.8.0", results_dir=nested)
            assert path.exists()
            assert nested.exists()

    def test_output_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_results([_make_result()], "0.8.0", results_dir=Path(tmpdir))
            # Parsing raw text should not raise
            data = json.loads(path.read_text())
            assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# find_results_for_version
# ---------------------------------------------------------------------------


class TestFindResults:
    def test_finds_matching_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_results([_make_result()], "0.8.0", results_dir=Path(tmpdir))
            found = find_results_for_version("0.8.0", results_dir=Path(tmpdir))
            assert found is not None
            assert "mojo-0.8.0" in found.name

    def test_returns_none_for_missing_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_results([_make_result()], "0.8.0", results_dir=Path(tmpdir))
            assert find_results_for_version("0.9.0", results_dir=Path(tmpdir)) is None

    def test_returns_none_for_missing_directory(self):
        assert find_results_for_version("0.8.0", results_dir=Path("/nonexistent")) is None


# ---------------------------------------------------------------------------
# list_result_files
# ---------------------------------------------------------------------------


class TestListResults:
    def test_lists_newest_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two result files with different timestamps in the name
            dir_path = Path(tmpdir)
            (dir_path / "2026-01-01_000000_mojo-0.7.0.json").write_text("{}")
            (dir_path / "2026-02-01_000000_mojo-0.8.0.json").write_text("{}")

            files = list_result_files(results_dir=dir_path)
            assert len(files) == 2
            # Newest (Feb) should come first due to reverse sort
            assert "2026-02" in files[0].name

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert list_result_files(results_dir=Path(tmpdir)) == []

    def test_nonexistent_directory(self):
        assert list_result_files(results_dir=Path("/nonexistent")) == []
