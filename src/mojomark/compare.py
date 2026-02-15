"""Comparison engine — diff benchmark results across Mojo versions."""

from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    """Regression detection status based on percentage change thresholds."""

    IMPROVED = "improved"
    STABLE = "stable"
    WARNING = "warning"
    REGRESSION = "regression"

    @property
    def indicator(self) -> str:
        indicators = {
            Status.IMPROVED: "[bold green]>>[/bold green]",
            Status.STABLE: "[green]OK[/green]",
            Status.WARNING: "[yellow]!![/yellow]",
            Status.REGRESSION: "[bold red]XX[/bold red]",
        }
        return indicators[self]

    @property
    def label(self) -> str:
        labels = {
            Status.IMPROVED: "[bold green]improved[/bold green]",
            Status.STABLE: "[green]stable[/green]",
            Status.WARNING: "[yellow]warning[/yellow]",
            Status.REGRESSION: "[bold red]REGRESSION[/bold red]",
        }
        return labels[self]


@dataclass
class BenchmarkDiff:
    """Comparison result for a single benchmark."""

    name: str
    category: str
    base_mean_ns: float
    target_mean_ns: float
    delta_pct: float
    status: Status


DEFAULT_THRESHOLD_STABLE = 3.0
DEFAULT_THRESHOLD_WARNING = 10.0
DEFAULT_THRESHOLD_IMPROVED = -5.0


@dataclass
class Thresholds:
    """Regression classification boundaries (percentage change).

    Positive delta = slower, negative = faster.
    """

    stable: float = DEFAULT_THRESHOLD_STABLE
    warning: float = DEFAULT_THRESHOLD_WARNING
    improved: float = DEFAULT_THRESHOLD_IMPROVED


def classify_delta(
    delta_pct: float,
    thresholds: Thresholds | None = None,
) -> Status:
    """Classify a percentage change into a regression status.

    Args:
        delta_pct: Percentage change (positive = slower, negative = faster).
        thresholds: Classification boundaries. Uses defaults if None.

    Returns:
        Status classification.
    """
    t = thresholds or Thresholds()

    if delta_pct <= t.improved:
        return Status.IMPROVED
    elif abs(delta_pct) < t.stable:
        return Status.STABLE
    elif delta_pct >= t.warning:
        return Status.REGRESSION
    else:
        return Status.WARNING


def compare_results(
    base_data: dict,
    target_data: dict,
    thresholds: Thresholds | None = None,
) -> list[BenchmarkDiff]:
    """Compare benchmark results between two runs.

    Args:
        base_data: The baseline result data (older version).
        target_data: The target result data (newer version).
        thresholds: Classification boundaries. Uses defaults if None.

    Returns:
        List of BenchmarkDiff objects, one per matched benchmark.
    """
    base_benchmarks = {(b["category"], b["name"]): b for b in base_data["benchmarks"]}

    diffs = []
    for target_bench in target_data["benchmarks"]:
        key = (target_bench["category"], target_bench["name"])
        base_bench = base_benchmarks.get(key)

        if base_bench is None:
            continue

        base_mean = base_bench["stats"]["mean_ns"]
        target_mean = target_bench["stats"]["mean_ns"]

        if base_mean == 0:
            continue

        delta_pct = ((target_mean - base_mean) / base_mean) * 100

        diffs.append(
            BenchmarkDiff(
                name=target_bench["name"],
                category=target_bench["category"],
                base_mean_ns=base_mean,
                target_mean_ns=target_mean,
                delta_pct=delta_pct,
                status=classify_delta(delta_pct, thresholds),
            )
        )

    return diffs


def summarize_diffs(diffs: list[BenchmarkDiff]) -> dict[Status, int]:
    """Count benchmarks in each status category.

    Args:
        diffs: List of benchmark comparisons.

    Returns:
        Dict mapping Status to count.
    """
    summary: dict[Status, int] = {s: 0 for s in Status}
    for d in diffs:
        summary[d.status] += 1
    return summary
