"""Historical trend analysis — track benchmark performance across versions.

Aggregates stored results into per-benchmark timelines, enabling
visualization of performance changes over Mojo's evolution.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from mojomark.codegen import parse_version_tuple
from mojomark.storage import list_result_files, load_results

SPARK_BLOCKS = " ▁▂▃▄▅▆▇█"


@dataclass
class VersionPoint:
    """A single benchmark measurement for one Mojo version."""

    version: str
    timestamp: str
    mean_ns: float
    median_ns: float
    min_ns: float
    max_ns: float
    std_dev_ns: float
    samples: int


@dataclass
class BenchmarkTrend:
    """Performance history for a single benchmark across versions."""

    name: str
    category: str
    points: list[VersionPoint] = field(default_factory=list)

    @property
    def versions(self) -> list[str]:
        return [p.version for p in self.points]

    @property
    def mean_values(self) -> list[float]:
        return [p.mean_ns for p in self.points]

    @property
    def latest(self) -> VersionPoint | None:
        return self.points[-1] if self.points else None

    @property
    def earliest(self) -> VersionPoint | None:
        return self.points[0] if self.points else None

    @property
    def overall_delta_pct(self) -> float | None:
        """Percentage change from earliest to latest version."""
        if len(self.points) < 2:
            return None
        first = self.points[0].mean_ns
        last = self.points[-1].mean_ns
        if first == 0:
            return None
        return ((last - first) / first) * 100


def gather_trends(
    results_dir: Path | None = None,
    category: str | None = None,
    benchmark: str | None = None,
    versions: list[str] | None = None,
) -> list[BenchmarkTrend]:
    """Load all stored results and organize into per-benchmark trends.

    Args:
        results_dir: Override the results directory.
        category: Filter to a specific category.
        benchmark: Filter to a specific benchmark name.
        versions: Only include these Mojo versions.

    Returns:
        List of BenchmarkTrend objects sorted by category then name.
        Each trend's points are sorted by version (semver order).
    """
    from mojomark.storage import RESULTS_DIR

    rdir = results_dir or RESULTS_DIR
    result_files = list_result_files(rdir)

    if not result_files:
        return []

    version_set = set(versions) if versions else None
    trends: dict[str, BenchmarkTrend] = {}
    seen_versions: dict[str, set[str]] = {}

    for filepath in result_files:
        data = load_results(filepath)
        mojo_version = data["mojo_version"]
        timestamp = data.get("timestamp", "")

        if version_set and mojo_version not in version_set:
            continue

        for bench in data.get("benchmarks", []):
            name = bench["name"]
            cat = bench["category"]

            if category and cat != category:
                continue
            if benchmark and name != benchmark:
                continue

            key = f"{cat}/{name}"

            if key not in seen_versions:
                seen_versions[key] = set()
            if mojo_version in seen_versions[key]:
                continue
            seen_versions[key].add(mojo_version)

            if key not in trends:
                trends[key] = BenchmarkTrend(name=name, category=cat)

            stats = bench.get("stats", {})
            trends[key].points.append(
                VersionPoint(
                    version=mojo_version,
                    timestamp=timestamp,
                    mean_ns=stats.get("mean_ns", 0),
                    median_ns=stats.get("median_ns", 0),
                    min_ns=stats.get("min_ns", 0),
                    max_ns=stats.get("max_ns", 0),
                    std_dev_ns=stats.get("std_dev_ns", 0),
                    samples=stats.get("samples", 0),
                )
            )

    for trend in trends.values():
        trend.points.sort(key=lambda p: parse_version_tuple(p.version))

    return sorted(trends.values(), key=lambda t: (t.category, t.name))


def sparkline(values: list[float]) -> str:
    """Render a sparkline from a list of numeric values.

    Uses Unicode block characters to create a compact visual
    representation of the trend. Lower values (faster) produce
    shorter bars.

    Args:
        values: List of timing values (nanoseconds).

    Returns:
        A short string of block characters.
    """
    if not values:
        return ""
    if len(values) == 1:
        return "▅"

    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        return "▅" * len(values)

    chars = []
    for v in values:
        idx = int((v - min_val) / (max_val - min_val) * 8)
        idx = min(idx, 8)
        chars.append(SPARK_BLOCKS[idx])
    return "".join(chars)


def trend_bar(value: float, max_value: float, width: int = 30) -> str:
    """Render a horizontal bar proportional to value/max_value.

    Args:
        value: The timing value for this bar.
        max_value: The maximum value across all bars in the group.
        width: Maximum bar width in characters.

    Returns:
        A string of block characters representing the bar.
    """
    if max_value == 0:
        return ""
    ratio = value / max_value
    full_blocks = int(ratio * width)
    return "█" * max(full_blocks, 1)


def export_csv(trends: list[BenchmarkTrend]) -> str:
    """Export trend data as CSV.

    Args:
        trends: List of BenchmarkTrend objects.

    Returns:
        CSV-formatted string.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "benchmark",
            "category",
            "version",
            "timestamp",
            "mean_ns",
            "median_ns",
            "min_ns",
            "max_ns",
            "std_dev_ns",
            "samples",
        ]
    )

    for trend in trends:
        for p in trend.points:
            writer.writerow(
                [
                    trend.name,
                    trend.category,
                    p.version,
                    p.timestamp,
                    f"{p.mean_ns:.0f}",
                    f"{p.median_ns:.0f}",
                    f"{p.min_ns:.0f}",
                    f"{p.max_ns:.0f}",
                    f"{p.std_dev_ns:.0f}",
                    p.samples,
                ]
            )

    return output.getvalue()
