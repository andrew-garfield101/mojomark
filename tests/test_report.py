"""Tests for mojomark report generation."""

import tempfile
from pathlib import Path

import pytest

from mojomark.compare import BenchmarkDiff, compare_results
from mojomark.report import (
    generate_comparison_html,
    generate_comparison_markdown,
    generate_single_run_html,
    generate_single_run_markdown,
    save_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def single_run_data() -> dict:
    """Sample single-run result data."""
    return {
        "mojo_version": "0.8.0",
        "timestamp": "2026-02-11T02:30:00+00:00",
        "benchmarks": [
            {
                "name": "fibonacci",
                "category": "compute",
                "samples_ns": [100_000_000, 102_000_000, 99_000_000],
                "stats": {
                    "mean_ns": 100_333_333,
                    "median_ns": 100_000_000,
                    "min_ns": 99_000_000,
                    "max_ns": 102_000_000,
                    "std_dev_ns": 1_527_525,
                    "samples": 3,
                },
            },
            {
                "name": "sorting",
                "category": "compute",
                "samples_ns": [50_000_000, 51_000_000, 49_000_000],
                "stats": {
                    "mean_ns": 50_000_000,
                    "median_ns": 50_000_000,
                    "min_ns": 49_000_000,
                    "max_ns": 51_000_000,
                    "std_dev_ns": 1_000_000,
                    "samples": 3,
                },
            },
        ],
    }


@pytest.fixture
def base_run_data() -> dict:
    """Baseline result data for comparison tests."""
    return {
        "mojo_version": "0.7.0",
        "timestamp": "2026-02-10T12:00:00+00:00",
        "benchmarks": [
            {
                "name": "fibonacci",
                "category": "compute",
                "samples_ns": [110_000_000, 112_000_000, 108_000_000],
                "stats": {
                    "mean_ns": 110_000_000,
                    "median_ns": 110_000_000,
                    "min_ns": 108_000_000,
                    "max_ns": 112_000_000,
                    "std_dev_ns": 2_000_000,
                    "samples": 3,
                },
            },
            {
                "name": "sorting",
                "category": "compute",
                "samples_ns": [45_000_000, 46_000_000, 44_000_000],
                "stats": {
                    "mean_ns": 45_000_000,
                    "median_ns": 45_000_000,
                    "min_ns": 44_000_000,
                    "max_ns": 46_000_000,
                    "std_dev_ns": 1_000_000,
                    "samples": 3,
                },
            },
        ],
    }


@pytest.fixture
def sample_diffs(base_run_data, single_run_data) -> list[BenchmarkDiff]:
    """Pre-computed diffs from base -> target."""
    return compare_results(base_run_data, single_run_data)


# ---------------------------------------------------------------------------
# Single-run Markdown
# ---------------------------------------------------------------------------


class TestSingleRunMarkdown:
    def test_contains_version_header(self, single_run_data):
        md = generate_single_run_markdown(single_run_data)
        assert "# mojomark Report — Mojo 0.8.0" in md

    def test_contains_metadata(self, single_run_data):
        md = generate_single_run_markdown(single_run_data)
        assert "**Mojo version:** 0.8.0" in md
        assert "**Benchmarks:** 2" in md

    def test_contains_table_header(self, single_run_data):
        md = generate_single_run_markdown(single_run_data)
        assert "| Category | Benchmark | Mean | Median | Min | Max | Std Dev | Samples |" in md

    def test_contains_benchmark_rows(self, single_run_data):
        md = generate_single_run_markdown(single_run_data)
        assert "fibonacci" in md
        assert "sorting" in md
        assert "compute" in md

    def test_contains_time_values(self, single_run_data):
        md = generate_single_run_markdown(single_run_data)
        # fibonacci mean is ~100ms
        assert "100.3 ms" in md
        # sorting mean is 50ms
        assert "50.0 ms" in md

    def test_empty_benchmarks(self):
        data = {
            "mojo_version": "0.8.0",
            "timestamp": "2026-02-11T02:30:00+00:00",
            "benchmarks": [],
        }
        md = generate_single_run_markdown(data)
        assert "# mojomark Report" in md
        assert "**Benchmarks:** 0" in md


# ---------------------------------------------------------------------------
# Comparison Markdown
# ---------------------------------------------------------------------------


class TestComparisonMarkdown:
    def test_contains_version_header(self, base_run_data, single_run_data, sample_diffs):
        md = generate_comparison_markdown(base_run_data, single_run_data, sample_diffs)
        assert "# mojomark Comparison — Mojo 0.7.0 vs 0.8.0" in md

    def test_contains_both_versions_in_table(
        self, base_run_data, single_run_data, sample_diffs
    ):
        md = generate_comparison_markdown(base_run_data, single_run_data, sample_diffs)
        assert "0.7.0" in md
        assert "0.8.0" in md

    def test_contains_delta_percentages(self, base_run_data, single_run_data, sample_diffs):
        md = generate_comparison_markdown(base_run_data, single_run_data, sample_diffs)
        # fibonacci: 110ms -> 100ms = ~-8.8% (improved)
        assert "-8.8%" in md
        # sorting: 45ms -> 50ms = ~+11.1% (regression)
        assert "+11.1%" in md

    def test_contains_status_indicators(self, base_run_data, single_run_data, sample_diffs):
        md = generate_comparison_markdown(base_run_data, single_run_data, sample_diffs)
        assert "improved" in md
        assert "REGRESSION" in md

    def test_contains_summary_section(self, base_run_data, single_run_data, sample_diffs):
        md = generate_comparison_markdown(base_run_data, single_run_data, sample_diffs)
        assert "## Summary" in md

    def test_contains_threshold_legend(self, base_run_data, single_run_data, sample_diffs):
        md = generate_comparison_markdown(base_run_data, single_run_data, sample_diffs)
        assert "### Thresholds" in md


# ---------------------------------------------------------------------------
# Single-run HTML
# ---------------------------------------------------------------------------


class TestSingleRunHtml:
    def test_is_valid_html_structure(self, single_run_data):
        html = generate_single_run_html(single_run_data)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "</body>" in html

    def test_contains_title(self, single_run_data):
        html = generate_single_run_html(single_run_data)
        assert "<title>mojomark — Mojo 0.8.0</title>" in html

    def test_contains_benchmark_data(self, single_run_data):
        html = generate_single_run_html(single_run_data)
        assert "fibonacci" in html
        assert "sorting" in html

    def test_contains_inline_styles(self, single_run_data):
        html = generate_single_run_html(single_run_data)
        assert "<style>" in html
        assert "--accent" in html

    def test_contains_summary_cards(self, single_run_data):
        html = generate_single_run_html(single_run_data)
        assert "summary-card" in html
        assert "Benchmarks" in html
        assert "Categories" in html


# ---------------------------------------------------------------------------
# Comparison HTML
# ---------------------------------------------------------------------------


class TestComparisonHtml:
    def test_is_valid_html_structure(self, base_run_data, single_run_data, sample_diffs):
        html = generate_comparison_html(base_run_data, single_run_data, sample_diffs)
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_contains_both_versions(self, base_run_data, single_run_data, sample_diffs):
        html = generate_comparison_html(base_run_data, single_run_data, sample_diffs)
        assert "0.7.0" in html
        assert "0.8.0" in html

    def test_contains_status_badges(self, base_run_data, single_run_data, sample_diffs):
        html = generate_comparison_html(base_run_data, single_run_data, sample_diffs)
        assert "border-radius" in html
        assert "improved" in html

    def test_contains_delta_colors(self, base_run_data, single_run_data, sample_diffs):
        html = generate_comparison_html(base_run_data, single_run_data, sample_diffs)
        assert "delta-negative" in html  # fibonacci improved
        assert "delta-positive" in html  # sorting regressed

    def test_contains_summary_cards(self, base_run_data, single_run_data, sample_diffs):
        html = generate_comparison_html(base_run_data, single_run_data, sample_diffs)
        assert "Improved" in html
        assert "Regression" in html


# ---------------------------------------------------------------------------
# File saving
# ---------------------------------------------------------------------------


class TestSaveReport:
    def test_saves_to_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_report("# Test Report", "test.md", Path(tmpdir))
            assert path.exists()
            assert path.read_text() == "# Test Report"

    def test_creates_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "sub" / "dir"
            path = save_report("content", "test.html", nested)
            assert path.exists()
            assert path.parent == nested

    def test_filename_preserved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_report("content", "my_report.md", Path(tmpdir))
            assert path.name == "my_report.md"
