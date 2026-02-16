"""Result storage — save and load benchmark results as JSON."""

import json
from datetime import datetime, timezone
from pathlib import Path

from mojomark.machine import get_machine_info
from mojomark.runner import BenchmarkResult

RESULTS_DIR = Path.cwd() / "results"


def save_results(
    results: list[BenchmarkResult],
    mojo_version: str,
    results_dir: Path = RESULTS_DIR,
) -> Path:
    """Save benchmark results to a timestamped JSON file.

    Args:
        results: List of benchmark results to save.
        mojo_version: Mojo version string.
        results_dir: Directory to store result files.

    Returns:
        Path to the saved JSON file.
    """
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    filename = f"{timestamp}_mojo-{mojo_version}.json"
    filepath = results_dir / filename

    data = {
        "mojo_version": mojo_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "machine": get_machine_info(),
        "benchmarks": [r.to_dict() for r in results],
    }

    filepath.write_text(json.dumps(data, indent=2) + "\n")
    return filepath


def load_results(filepath: Path) -> dict:
    """Load benchmark results from a JSON file.

    Args:
        filepath: Path to the JSON result file.

    Returns:
        Parsed result data.
    """
    return json.loads(filepath.read_text())


def find_results_for_version(
    version: str,
    results_dir: Path = RESULTS_DIR,
) -> Path | None:
    """Find the most recent result file for a given Mojo version.

    Args:
        version: Mojo version string to search for.
        results_dir: Directory containing result files.

    Returns:
        Path to the most recent matching result file, or None.
    """
    if not results_dir.exists():
        return None

    matches = sorted(
        results_dir.glob(f"*_mojo-{version}.json"),
        reverse=True,
    )
    return matches[0] if matches else None


def list_result_files(results_dir: Path = RESULTS_DIR) -> list[Path]:
    """List all result files, newest first.

    Args:
        results_dir: Directory containing result files.

    Returns:
        List of result file paths, sorted newest first.
    """
    if not results_dir.exists():
        return []
    return sorted(results_dir.glob("*.json"), reverse=True)
