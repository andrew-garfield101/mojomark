"""Benchmark runner — discovers, compiles, and executes Mojo benchmarks."""

import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# Marker printed by instrumented Mojo benchmarks (see benchmarks/*.mojo).
# Format: "MOJOMARK_NS <elapsed_nanoseconds>"
TIMING_MARKER = "MOJOMARK_NS"

BENCHMARKS_DIR = Path(__file__).parent.parent.parent / "benchmarks"


def _parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse a version string like ``'0.7.0'`` into a comparable tuple."""
    parts: list[int] = []
    for part in version_str.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def find_benchmark_set(
    mojo_version: str,
    benchmarks_dir: Path = BENCHMARKS_DIR,
) -> Path:
    """Find the best benchmark set for a given Mojo version.

    Scans *benchmarks_dir* for versioned subdirectories (``v0.7/``, ``v0.26/``,
    etc.) and returns the one whose version tag is the highest that does not
    exceed *mojo_version*.

    Falls back to *benchmarks_dir* itself if no versioned subdirs exist (e.g.
    in test fixtures).

    Args:
        mojo_version: Target Mojo version string.
        benchmarks_dir: Root benchmarks directory.

    Returns:
        Path to the selected benchmark set directory.
    """
    target = _parse_version_tuple(mojo_version)

    # Collect versioned subdirectories
    candidates: list[tuple[tuple[int, ...], Path]] = []
    if benchmarks_dir.exists():
        for child in benchmarks_dir.iterdir():
            if child.is_dir() and child.name.startswith("v"):
                ver_str = child.name[1:]  # strip the leading 'v'
                ver_tuple = _parse_version_tuple(ver_str)
                candidates.append((ver_tuple, child))

    if not candidates:
        # No versioned subdirs — fall back to flat layout (tests, etc.)
        return benchmarks_dir

    # Sort by version (ascending) and pick the highest one <= target
    candidates.sort(key=lambda c: c[0])
    best = candidates[0][1]  # default to lowest if nothing matches
    for ver_tuple, path in candidates:
        if ver_tuple <= target:
            best = path
        else:
            break

    return best


@dataclass
class BenchmarkResult:
    """Timing results for a single benchmark."""

    name: str
    category: str
    samples_ns: list[int] = field(default_factory=list)

    @property
    def mean_ns(self) -> float:
        return sum(self.samples_ns) / len(self.samples_ns) if self.samples_ns else 0

    @property
    def min_ns(self) -> int:
        return min(self.samples_ns) if self.samples_ns else 0

    @property
    def max_ns(self) -> int:
        return max(self.samples_ns) if self.samples_ns else 0

    @property
    def median_ns(self) -> float:
        if not self.samples_ns:
            return 0
        sorted_samples = sorted(self.samples_ns)
        n = len(sorted_samples)
        if n % 2 == 1:
            return float(sorted_samples[n // 2])
        return (sorted_samples[n // 2 - 1] + sorted_samples[n // 2]) / 2

    @property
    def std_dev_ns(self) -> float:
        if len(self.samples_ns) < 2:
            return 0
        mean = self.mean_ns
        variance = sum((s - mean) ** 2 for s in self.samples_ns) / (len(self.samples_ns) - 1)
        return variance**0.5

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "samples_ns": self.samples_ns,
            "stats": {
                "mean_ns": self.mean_ns,
                "median_ns": self.median_ns,
                "min_ns": self.min_ns,
                "max_ns": self.max_ns,
                "std_dev_ns": self.std_dev_ns,
                "samples": len(self.samples_ns),
            },
        }


def discover_benchmarks(
    benchmarks_dir: Path = BENCHMARKS_DIR,
    category: str | None = None,
    mojo_version: str | None = None,
) -> list[tuple[str, str, Path]]:
    """Discover all .mojo benchmark files.

    When *mojo_version* is provided, the best matching version-specific
    benchmark set is selected automatically (e.g. ``v0.7/`` or ``v0.26/``).

    Returns:
        List of (name, category, path) tuples.
    """
    if mojo_version:
        benchmarks_dir = find_benchmark_set(mojo_version, benchmarks_dir)

    benchmarks = []
    if not benchmarks_dir.exists():
        return benchmarks

    for mojo_file in sorted(benchmarks_dir.rglob("*.mojo")):
        bench_category = mojo_file.parent.name
        bench_name = mojo_file.stem

        if category and bench_category != category:
            continue

        benchmarks.append((bench_name, bench_category, mojo_file))

    return benchmarks


def get_mojo_version(mojo_binary: Path | None = None) -> str:
    """Get the installed Mojo version string.

    Args:
        mojo_binary: Path to a specific mojo binary. If None, uses PATH.
    """
    cmd = str(mojo_binary) if mojo_binary else "mojo"
    try:
        result = subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Output format: "mojo 0.7.0 (af002202)"
        parts = result.stdout.strip().split()
        if len(parts) >= 2:
            return parts[1]
        return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def compile_benchmark(
    mojo_file: Path,
    output_dir: Path,
    mojo_binary: Path | None = None,
) -> Path:
    """Compile a .mojo file into a binary.

    Args:
        mojo_file: Path to the .mojo source file.
        output_dir: Directory to place the compiled binary.
        mojo_binary: Path to a specific mojo binary. If None, uses PATH.

    Returns:
        Path to the compiled binary.

    Raises:
        RuntimeError: If compilation fails.
    """
    cmd = str(mojo_binary) if mojo_binary else "mojo"
    binary_path = output_dir / mojo_file.stem
    result = subprocess.run(
        [cmd, "build", str(mojo_file), "-o", str(binary_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to compile {mojo_file.name}:\n{result.stderr}")
    return binary_path


def _parse_internal_timing(stdout: str) -> int | None:
    """Extract Mojo-side nanosecond timing from benchmark stdout.

    Instrumented benchmarks print a line like ``MOJOMARK_NS 12345678``.
    Returns the integer value, or *None* if the marker is not found.
    """
    for line in stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == TIMING_MARKER:
            try:
                return int(parts[1])
            except ValueError:
                continue
    return None


def run_binary(binary_path: Path) -> int:
    """Run a compiled benchmark binary and return execution time in nanoseconds.

    If the binary is instrumented (prints a ``MOJOMARK_NS`` marker), the
    Mojo-side measurement is used — this excludes process-spawn and
    dynamic-linker overhead, giving a much cleaner signal.  Falls back to
    wall-clock timing when the marker is absent.

    Args:
        binary_path: Path to the compiled binary.

    Returns:
        Execution time in nanoseconds (internal or wall-clock).

    Raises:
        RuntimeError: If the binary fails to execute.
    """
    start = time.perf_counter_ns()
    result = subprocess.run(
        [str(binary_path)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    wall_ns = time.perf_counter_ns() - start

    if result.returncode != 0:
        raise RuntimeError(f"Benchmark {binary_path.name} failed:\n{result.stderr}")

    internal_ns = _parse_internal_timing(result.stdout)
    if internal_ns is not None:
        return internal_ns

    log.debug(
        "%s: no MOJOMARK_NS marker — falling back to wall-clock (%d ns)",
        binary_path.name,
        wall_ns,
    )
    return wall_ns


def run_benchmark(
    mojo_file: Path,
    name: str,
    category: str,
    samples: int = 10,
    warmup: int = 3,
    mojo_binary: Path | None = None,
) -> BenchmarkResult:
    """Compile and run a single benchmark, collecting timing samples.

    Args:
        mojo_file: Path to the .mojo benchmark file.
        name: Benchmark name.
        category: Benchmark category.
        samples: Number of timed executions.
        warmup: Number of warmup executions (not timed).
        mojo_binary: Path to a specific mojo binary. If None, uses PATH.

    Returns:
        BenchmarkResult with timing data.
    """
    result = BenchmarkResult(name=name, category=category)

    with tempfile.TemporaryDirectory(prefix="mojomark_") as tmpdir:
        binary_path = compile_benchmark(mojo_file, Path(tmpdir), mojo_binary=mojo_binary)

        # Warmup runs — let OS caches and CPU settle
        for _ in range(warmup):
            run_binary(binary_path)

        # Timed runs
        for _ in range(samples):
            elapsed_ns = run_binary(binary_path)
            result.samples_ns.append(elapsed_ns)

    return result
