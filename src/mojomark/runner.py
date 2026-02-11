"""Benchmark runner — discovers, compiles, and executes Mojo benchmarks."""

import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

BENCHMARKS_DIR = Path(__file__).parent.parent.parent / "benchmarks"


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
) -> list[tuple[str, str, Path]]:
    """Discover all .mojo benchmark files.

    Returns:
        List of (name, category, path) tuples.
    """
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


def get_mojo_version() -> str:
    """Get the installed Mojo version string."""
    try:
        result = subprocess.run(
            ["mojo", "--version"],
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


def compile_benchmark(mojo_file: Path, output_dir: Path) -> Path:
    """Compile a .mojo file into a binary.

    Args:
        mojo_file: Path to the .mojo source file.
        output_dir: Directory to place the compiled binary.

    Returns:
        Path to the compiled binary.

    Raises:
        RuntimeError: If compilation fails.
    """
    binary_path = output_dir / mojo_file.stem
    result = subprocess.run(
        ["mojo", "build", str(mojo_file), "-o", str(binary_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to compile {mojo_file.name}:\n{result.stderr}")
    return binary_path


def run_binary(binary_path: Path) -> int:
    """Run a compiled benchmark binary and return execution time in nanoseconds.

    Args:
        binary_path: Path to the compiled binary.

    Returns:
        Wall-clock execution time in nanoseconds.

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
    elapsed_ns = time.perf_counter_ns() - start

    if result.returncode != 0:
        raise RuntimeError(f"Benchmark {binary_path.name} failed:\n{result.stderr}")
    return elapsed_ns


def run_benchmark(
    mojo_file: Path,
    name: str,
    category: str,
    samples: int = 10,
    warmup: int = 3,
) -> BenchmarkResult:
    """Compile and run a single benchmark, collecting timing samples.

    Args:
        mojo_file: Path to the .mojo benchmark file.
        name: Benchmark name.
        category: Benchmark category.
        samples: Number of timed executions.
        warmup: Number of warmup executions (not timed).

    Returns:
        BenchmarkResult with timing data.
    """
    result = BenchmarkResult(name=name, category=category)

    with tempfile.TemporaryDirectory(prefix="mojomark_") as tmpdir:
        binary_path = compile_benchmark(mojo_file, Path(tmpdir))

        # Warmup runs — let OS caches and CPU settle
        for _ in range(warmup):
            run_binary(binary_path)

        # Timed runs
        for _ in range(samples):
            elapsed_ns = run_binary(binary_path)
            result.samples_ns.append(elapsed_ns)

    return result
