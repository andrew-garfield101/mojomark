"""Benchmark runner — discovers, compiles, and executes Mojo benchmarks.

Templates are rendered into version-specific ``.mojo`` files by the
``codegen`` module before compilation.
"""

import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

TIMING_MARKER = "MOJOMARK_NS"

BENCHMARKS_DIR = Path(__file__).parent / "templates"


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
    benchmarks_dir: Path | None = None,
    category: str | None = None,
    extra_dirs: list[Path] | None = None,
) -> list[tuple[str, str, Path]]:
    """Discover benchmark templates.

    Scans the built-in templates directory and any extra directories
    for ``.mojo`` template files.  User templates override built-in
    ones with the same category/name.

    Args:
        benchmarks_dir: Override the templates directory (useful for tests).
        category: If given, only return templates in this category.
        extra_dirs: Additional directories to scan (user benchmarks).

    Returns:
        List of (name, category, path) tuples.
    """
    from mojomark.codegen import TEMPLATES_DIR, discover_templates

    return discover_templates(
        benchmarks_dir or TEMPLATES_DIR,
        category,
        extra_dirs=extra_dirs,
    )


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
    mojo_version: str | None = None,
) -> BenchmarkResult:
    """Compile and run a single benchmark, collecting timing samples.

    When *mojo_version* is provided the *mojo_file* is treated as a
    **template**: it is rendered into version-specific ``.mojo`` source
    before compilation.  Without a version, the file is compiled directly.

    Args:
        mojo_file: Path to the .mojo benchmark (or template) file.
        name: Benchmark name.
        category: Benchmark category.
        samples: Number of timed executions.
        warmup: Number of warmup executions (not timed).
        mojo_binary: Path to a specific mojo binary. If None, uses PATH.
        mojo_version: Target Mojo version for template rendering.

    Returns:
        BenchmarkResult with timing data.
    """
    result = BenchmarkResult(name=name, category=category)

    with tempfile.TemporaryDirectory(prefix="mojomark_") as tmpdir:
        tmpdir_path = Path(tmpdir)

        if mojo_version:
            from mojomark.codegen import render_to_file

            actual_mojo_file = render_to_file(mojo_file, tmpdir_path, mojo_version)
        else:
            actual_mojo_file = mojo_file

        binary_path = compile_benchmark(actual_mojo_file, tmpdir_path, mojo_binary=mojo_binary)

        for _ in range(warmup):
            run_binary(binary_path)

        for _ in range(samples):
            elapsed_ns = run_binary(binary_path)
            result.samples_ns.append(elapsed_ns)

    return result
