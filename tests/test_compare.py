"""Tests for mojomark comparison engine."""

import pytest

from mojomark.compare import (
    BenchmarkDiff,
    Status,
    classify_delta,
    compare_results,
    summarize_diffs,
)

# ---------------------------------------------------------------------------
# classify_delta — parametrized across all thresholds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("delta_pct", "expected"),
    [
        (-20.0, Status.IMPROVED),  # well below -5%
        (-5.0, Status.IMPROVED),  # exact boundary
        (-5.01, Status.IMPROVED),  # just past boundary
        (-4.9, Status.WARNING),  # between -5% and -3% — not yet "improved"
        (0.0, Status.STABLE),  # no change
        (2.9, Status.STABLE),  # just under 3%
        (3.0, Status.WARNING),  # exact warning boundary
        (5.0, Status.WARNING),  # mid-warning range
        (9.9, Status.WARNING),  # just under 10%
        (10.0, Status.REGRESSION),  # exact regression boundary
        (50.0, Status.REGRESSION),  # severe regression
    ],
)
def test_classify_delta(delta_pct, expected):
    assert classify_delta(delta_pct) == expected


# ---------------------------------------------------------------------------
# Status properties
# ---------------------------------------------------------------------------


def test_status_indicator_returns_string():
    for status in Status:
        assert isinstance(status.indicator, str)
        assert len(status.indicator) > 0


def test_status_label_returns_string():
    for status in Status:
        assert isinstance(status.label, str)
        assert len(status.label) > 0


# ---------------------------------------------------------------------------
# compare_results
# ---------------------------------------------------------------------------


def _make_run(version, benchmarks):
    """Helper to build a minimal result dict."""
    return {
        "mojo_version": version,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "benchmarks": [
            {
                "name": name,
                "category": cat,
                "samples_ns": [],
                "stats": {
                    "mean_ns": mean,
                    "median_ns": mean,
                    "min_ns": mean,
                    "max_ns": mean,
                    "std_dev_ns": 0,
                    "samples": 1,
                },
            }
            for name, cat, mean in benchmarks
        ],
    }


class TestCompareResults:
    def test_matching_benchmarks_produce_diffs(self):
        base = _make_run("0.7.0", [("fib", "compute", 100)])
        target = _make_run("0.8.0", [("fib", "compute", 90)])
        diffs = compare_results(base, target)
        assert len(diffs) == 1
        assert diffs[0].name == "fib"
        assert diffs[0].delta_pct == pytest.approx(-10.0)

    def test_no_overlap_returns_empty(self):
        base = _make_run("0.7.0", [("fib", "compute", 100)])
        target = _make_run("0.8.0", [("sort", "compute", 90)])
        assert compare_results(base, target) == []

    def test_partial_overlap(self):
        base = _make_run("0.7.0", [("fib", "compute", 100), ("sort", "compute", 50)])
        target = _make_run("0.8.0", [("fib", "compute", 90), ("matrix", "compute", 200)])
        diffs = compare_results(base, target)
        assert len(diffs) == 1
        assert diffs[0].name == "fib"

    def test_zero_base_mean_skipped(self):
        base = _make_run("0.7.0", [("fib", "compute", 0)])
        target = _make_run("0.8.0", [("fib", "compute", 100)])
        assert compare_results(base, target) == []

    def test_delta_direction(self):
        base = _make_run("0.7.0", [("fib", "compute", 100)])
        target = _make_run("0.8.0", [("fib", "compute", 120)])
        diffs = compare_results(base, target)
        assert diffs[0].delta_pct > 0  # slower = positive


# ---------------------------------------------------------------------------
# summarize_diffs
# ---------------------------------------------------------------------------


class TestSummarizeDiffs:
    def test_counts_each_status(self):
        diffs = [
            BenchmarkDiff("a", "c", 100, 80, -20.0, Status.IMPROVED),
            BenchmarkDiff("b", "c", 100, 101, 1.0, Status.STABLE),
            BenchmarkDiff("c", "c", 100, 150, 50.0, Status.REGRESSION),
        ]
        summary = summarize_diffs(diffs)
        assert summary[Status.IMPROVED] == 1
        assert summary[Status.STABLE] == 1
        assert summary[Status.REGRESSION] == 1
        assert summary[Status.WARNING] == 0

    def test_empty_input(self):
        summary = summarize_diffs([])
        assert all(v == 0 for v in summary.values())
        assert len(summary) == len(Status)
