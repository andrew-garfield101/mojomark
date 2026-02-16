"""Tests for mojomark trend module."""

import json
import tempfile
from pathlib import Path

from mojomark.trend import (
    BenchmarkTrend,
    VersionPoint,
    export_csv,
    gather_trends,
    sparkline,
    trend_bar,
)


def _write_result(results_dir, version, benchmarks, timestamp="2026-01-01T00:00:00+00:00"):
    """Helper: write a fake result JSON file."""
    results_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "mojo_version": version,
        "timestamp": timestamp,
        "benchmarks": [
            {
                "name": name,
                "category": cat,
                "samples_ns": [],
                "stats": {
                    "mean_ns": mean,
                    "median_ns": mean,
                    "min_ns": mean * 0.9,
                    "max_ns": mean * 1.1,
                    "std_dev_ns": mean * 0.05,
                    "samples": 10,
                },
            }
            for name, cat, mean in benchmarks
        ],
    }
    filename = f"2026-01-01_000000_mojo-{version}.json"
    (results_dir / filename).write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# gather_trends
# ---------------------------------------------------------------------------


class TestGatherTrends:
    def test_gathers_from_multiple_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            rdir = Path(tmp)
            _write_result(rdir, "0.7.0", [("fib", "compute", 100)])
            _write_result(rdir, "0.26.1", [("fib", "compute", 80)])

            trends = gather_trends(results_dir=rdir)
            assert len(trends) == 1
            assert trends[0].name == "fib"
            assert len(trends[0].points) == 2
            assert trends[0].points[0].version == "0.7.0"
            assert trends[0].points[1].version == "0.26.1"

    def test_sorts_by_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            rdir = Path(tmp)
            _write_result(rdir, "0.26.1", [("fib", "compute", 80)])
            _write_result(rdir, "0.7.0", [("fib", "compute", 100)])
            _write_result(rdir, "0.25.0", [("fib", "compute", 90)])

            trends = gather_trends(results_dir=rdir)
            versions = [p.version for p in trends[0].points]
            assert versions == ["0.7.0", "0.25.0", "0.26.1"]

    def test_category_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            rdir = Path(tmp)
            _write_result(rdir, "0.7.0", [("fib", "compute", 100), ("dot", "simd", 200)])

            trends = gather_trends(results_dir=rdir, category="simd")
            assert len(trends) == 1
            assert trends[0].name == "dot"

    def test_benchmark_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            rdir = Path(tmp)
            _write_result(rdir, "0.7.0", [("fib", "compute", 100), ("sort", "compute", 200)])

            trends = gather_trends(results_dir=rdir, benchmark="fib")
            assert len(trends) == 1
            assert trends[0].name == "fib"

    def test_version_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            rdir = Path(tmp)
            _write_result(rdir, "0.7.0", [("fib", "compute", 100)])
            _write_result(rdir, "0.25.0", [("fib", "compute", 90)])
            _write_result(rdir, "0.26.1", [("fib", "compute", 80)])

            trends = gather_trends(results_dir=rdir, versions=["0.7.0", "0.26.1"])
            assert len(trends[0].points) == 2
            versions = [p.version for p in trends[0].points]
            assert "0.25.0" not in versions

    def test_empty_results_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            trends = gather_trends(results_dir=Path(tmp))
            assert trends == []

    def test_nonexistent_dir(self):
        trends = gather_trends(results_dir=Path("/nonexistent"))
        assert trends == []

    def test_multiple_benchmarks_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            rdir = Path(tmp)
            _write_result(
                rdir,
                "0.7.0",
                [("sort", "compute", 300), ("fib", "compute", 100), ("dot", "simd", 200)],
            )

            trends = gather_trends(results_dir=rdir)
            names = [(t.category, t.name) for t in trends]
            assert names == [("compute", "fib"), ("compute", "sort"), ("simd", "dot")]

    def test_deduplicates_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            rdir = Path(tmp)
            _write_result(rdir, "0.7.0", [("fib", "compute", 100)])

            second = rdir / "2026-01-02_000000_mojo-0.7.0.json"
            first = rdir / "2026-01-01_000000_mojo-0.7.0.json"
            second.write_text(first.read_text())

            trends = gather_trends(results_dir=rdir)
            assert len(trends[0].points) == 1


# ---------------------------------------------------------------------------
# BenchmarkTrend properties
# ---------------------------------------------------------------------------


class TestBenchmarkTrend:
    def test_overall_delta_pct(self):
        trend = BenchmarkTrend(
            name="fib",
            category="compute",
            points=[
                VersionPoint("0.7.0", "", 100, 100, 90, 110, 5, 10),
                VersionPoint("0.26.1", "", 80, 80, 72, 88, 4, 10),
            ],
        )
        assert trend.overall_delta_pct == -20.0

    def test_overall_delta_single_point(self):
        trend = BenchmarkTrend(
            name="fib",
            category="compute",
            points=[VersionPoint("0.7.0", "", 100, 100, 90, 110, 5, 10)],
        )
        assert trend.overall_delta_pct is None

    def test_overall_delta_zero_base(self):
        trend = BenchmarkTrend(
            name="fib",
            category="compute",
            points=[
                VersionPoint("0.7.0", "", 0, 0, 0, 0, 0, 10),
                VersionPoint("0.26.1", "", 100, 100, 90, 110, 5, 10),
            ],
        )
        assert trend.overall_delta_pct is None

    def test_versions_property(self):
        trend = BenchmarkTrend(
            name="fib",
            category="compute",
            points=[
                VersionPoint("0.7.0", "", 100, 100, 90, 110, 5, 10),
                VersionPoint("0.26.1", "", 80, 80, 72, 88, 4, 10),
            ],
        )
        assert trend.versions == ["0.7.0", "0.26.1"]

    def test_latest_earliest(self):
        p1 = VersionPoint("0.7.0", "", 100, 100, 90, 110, 5, 10)
        p2 = VersionPoint("0.26.1", "", 80, 80, 72, 88, 4, 10)
        trend = BenchmarkTrend(name="fib", category="compute", points=[p1, p2])
        assert trend.earliest is p1
        assert trend.latest is p2

    def test_empty_trend(self):
        trend = BenchmarkTrend(name="fib", category="compute")
        assert trend.earliest is None
        assert trend.latest is None
        assert trend.overall_delta_pct is None
        assert trend.versions == []
        assert trend.mean_values == []


# ---------------------------------------------------------------------------
# sparkline
# ---------------------------------------------------------------------------


class TestSparkline:
    def test_basic(self):
        result = sparkline([100, 200, 150])
        assert len(result) == 3

    def test_single_value(self):
        assert sparkline([100]) == "▅"

    def test_empty(self):
        assert sparkline([]) == ""

    def test_equal_values(self):
        result = sparkline([100, 100, 100])
        assert len(result) == 3
        assert result == "▅▅▅"

    def test_decreasing_trend(self):
        result = sparkline([1000, 500, 100])
        assert result[0] > result[2]


# ---------------------------------------------------------------------------
# trend_bar
# ---------------------------------------------------------------------------


class TestTrendBar:
    def test_full_bar(self):
        bar = trend_bar(100, 100, width=10)
        assert len(bar) == 10

    def test_half_bar(self):
        bar = trend_bar(50, 100, width=10)
        assert len(bar) == 5

    def test_zero_max(self):
        assert trend_bar(0, 0) == ""

    def test_minimum_one_block(self):
        bar = trend_bar(1, 1000, width=10)
        assert len(bar) >= 1


# ---------------------------------------------------------------------------
# export_csv
# ---------------------------------------------------------------------------


class TestExportCsv:
    def test_produces_valid_csv(self):
        trends = [
            BenchmarkTrend(
                name="fib",
                category="compute",
                points=[
                    VersionPoint("0.7.0", "2026-01-01", 100, 100, 90, 110, 5, 10),
                    VersionPoint("0.26.1", "2026-01-02", 80, 80, 72, 88, 4, 10),
                ],
            )
        ]
        csv_str = export_csv(trends)
        lines = csv_str.strip().split("\n")
        assert len(lines) == 3
        assert "benchmark" in lines[0]
        assert "fib" in lines[1]
        assert "0.7.0" in lines[1]
        assert "0.26.1" in lines[2]

    def test_empty_trends(self):
        csv_str = export_csv([])
        lines = csv_str.strip().split("\n")
        assert len(lines) == 1
        assert "benchmark" in lines[0]
