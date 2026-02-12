"""Tests for mojomark benchmark runner."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mojomark.runner import (
    BenchmarkResult,
    _parse_internal_timing,
    discover_benchmarks,
    get_mojo_version,
    run_binary,
)

# ---------------------------------------------------------------------------
# BenchmarkResult stats + serialization
# ---------------------------------------------------------------------------


class TestBenchmarkResult:
    def test_mean(self):
        r = BenchmarkResult("fib", "compute", [100, 200, 300])
        assert r.mean_ns == 200.0

    def test_median_odd(self):
        r = BenchmarkResult("fib", "compute", [100, 300, 200])
        assert r.median_ns == 200.0

    def test_median_even(self):
        r = BenchmarkResult("fib", "compute", [100, 200, 300, 400])
        assert r.median_ns == 250.0

    def test_min_max(self):
        r = BenchmarkResult("fib", "compute", [50, 100, 200])
        assert r.min_ns == 50
        assert r.max_ns == 200

    def test_std_dev_identical_samples(self):
        r = BenchmarkResult("fib", "compute", [100, 100, 100])
        assert r.std_dev_ns == 0.0

    def test_std_dev_varied_samples(self):
        r = BenchmarkResult("fib", "compute", [100, 200])
        assert r.std_dev_ns > 0

    def test_empty_samples_safe(self):
        r = BenchmarkResult("fib", "compute", [])
        assert r.mean_ns == 0
        assert r.median_ns == 0
        assert r.min_ns == 0
        assert r.max_ns == 0
        assert r.std_dev_ns == 0

    def test_single_sample_std_dev(self):
        r = BenchmarkResult("fib", "compute", [42])
        assert r.std_dev_ns == 0

    def test_to_dict_schema(self):
        r = BenchmarkResult("fib", "compute", [100, 200, 300])
        d = r.to_dict()
        assert d["name"] == "fib"
        assert d["category"] == "compute"
        assert d["samples_ns"] == [100, 200, 300]
        expected_keys = {"mean_ns", "median_ns", "min_ns", "max_ns", "std_dev_ns", "samples"}
        assert set(d["stats"].keys()) == expected_keys
        assert d["stats"]["samples"] == 3


# ---------------------------------------------------------------------------
# discover_benchmarks
# ---------------------------------------------------------------------------


class TestDiscoverBenchmarks:
    def test_finds_mojo_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "compute").mkdir()
            (base / "compute" / "fib.mojo").write_text("fn main(): pass")
            (base / "compute" / "sort.mojo").write_text("fn main(): pass")

            benchmarks = discover_benchmarks(benchmarks_dir=base)
            assert len(benchmarks) == 2
            names = {b[0] for b in benchmarks}
            assert names == {"fib", "sort"}

    def test_category_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "compute").mkdir()
            (base / "simd").mkdir()
            (base / "compute" / "fib.mojo").write_text("fn main(): pass")
            (base / "simd" / "dot.mojo").write_text("fn main(): pass")

            benchmarks = discover_benchmarks(benchmarks_dir=base, category="simd")
            assert len(benchmarks) == 1
            assert benchmarks[0][0] == "dot"

    def test_nonexistent_directory(self):
        assert discover_benchmarks(benchmarks_dir=Path("/nonexistent")) == []

    def test_extracts_category_from_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "memory").mkdir()
            (base / "memory" / "alloc.mojo").write_text("fn main(): pass")

            benchmarks = discover_benchmarks(benchmarks_dir=base)
            assert benchmarks[0][1] == "memory"


# ---------------------------------------------------------------------------
# get_mojo_version (mocked)
# ---------------------------------------------------------------------------


class TestGetMojoVersion:
    def test_parses_version_string(self):
        with patch("mojomark.runner.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "mojo 0.8.0 (af002202)\n"
            mock_run.return_value.returncode = 0
            assert get_mojo_version() == "0.8.0"

    def test_handles_missing_mojo(self):
        with patch("mojomark.runner.subprocess.run", side_effect=FileNotFoundError):
            assert get_mojo_version() == "unknown"

    def test_handles_unexpected_output(self):
        with patch("mojomark.runner.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "something unexpected"
            mock_run.return_value.returncode = 0
            # Should return something rather than crash
            result = get_mojo_version()
            assert isinstance(result, str)
            assert len(result) > 0


# ---------------------------------------------------------------------------
# _parse_internal_timing — parsing MOJOMARK_NS from stdout
# ---------------------------------------------------------------------------


class TestParseInternalTiming:
    """Tests for the Mojo-side timing marker parser."""

    def test_parses_valid_marker(self):
        stdout = "some setup output\nMOJOMARK_NS 12345678\n"
        assert _parse_internal_timing(stdout) == 12345678

    def test_parses_large_value(self):
        stdout = "MOJOMARK_NS 9999999999999\n"
        assert _parse_internal_timing(stdout) == 9999999999999

    def test_returns_none_when_no_marker(self):
        stdout = "hello world\nno timing here\n"
        assert _parse_internal_timing(stdout) is None

    def test_returns_none_for_empty_stdout(self):
        assert _parse_internal_timing("") is None

    def test_ignores_malformed_value(self):
        stdout = "MOJOMARK_NS not_a_number\n"
        assert _parse_internal_timing(stdout) is None

    def test_takes_first_marker(self):
        stdout = "MOJOMARK_NS 111\nMOJOMARK_NS 222\n"
        assert _parse_internal_timing(stdout) == 111

    def test_ignores_partial_marker(self):
        # Only one token on the line — no value after the marker
        stdout = "MOJOMARK_NS\n"
        assert _parse_internal_timing(stdout) is None

    def test_marker_among_other_output(self):
        stdout = (
            "Compiling benchmark...\nRunning 10 iterations\nchecksum = 42\nMOJOMARK_NS 500000\n"
        )
        assert _parse_internal_timing(stdout) == 500000


# ---------------------------------------------------------------------------
# run_binary — integration of internal vs wall-clock timing
# ---------------------------------------------------------------------------


class TestRunBinary:
    """Tests for run_binary with mocked subprocess."""

    def test_uses_internal_timing_when_marker_present(self):
        with patch("mojomark.runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "MOJOMARK_NS 42000\n"
            mock_run.return_value.stderr = ""

            result = run_binary(Path("/fake/binary"))
            assert result == 42000

    def test_falls_back_to_wall_clock_when_no_marker(self):
        with patch("mojomark.runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "no marker here\n"
            mock_run.return_value.stderr = ""

            result = run_binary(Path("/fake/binary"))
            # Should be a positive wall-clock value (not 42000)
            assert isinstance(result, int)
            assert result > 0

    def test_raises_on_nonzero_exit(self):
        with patch("mojomark.runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "segfault"

            with pytest.raises(RuntimeError, match="failed"):
                run_binary(Path("/fake/binary"))
