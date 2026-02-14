# mojomark

[![CI](https://github.com/andrew-garfield101/mojomark/actions/workflows/ci.yml/badge.svg)](https://github.com/andrew-garfield101/mojomark/actions/workflows/ci.yml)

A performance regression detector for the [Mojo](https://www.modular.com/mojo) programming language.

Run standardized benchmarks across Mojo versions, track results over time, and detect performance regressions automatically.

## Why?

As Mojo evolves rapidly, compiler changes can introduce performance regressions (or improvements!) that go unnoticed. `mojomark` provides a repeatable, automated way to measure and compare Mojo's performance across versions — with machine fingerprinting, internal nanosecond timing, and version-specific benchmark sets that account for API changes between releases.

## Quick Start

### Prerequisites

- Python 3.10+
- Mojo installed (system or pip-managed)

### Install

```bash
cd mojomark
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Check Your Environment

```bash
# See current Mojo version, latest available, and cached installations
mojomark status

# See all published Mojo versions from the package index
mojomark versions
```

### Run Benchmarks

```bash
# Run all benchmarks against your current Mojo version
mojomark run

# Run a specific category
mojomark run --category compute

# Customize sample count and warmup
mojomark run --samples 20 --warmup 5
```

### Regression Testing

```bash
# Compare current installed version against the latest available
mojomark regression current latest

# Compare two specific versions
mojomark regression 0.7.0 0.26.1.0

# mojomark will automatically install versions it doesn't have cached
```

### Compare Stored Results

```bash
# Compare previously stored results for two versions
mojomark compare 0.7.0 0.26.1.0

# View run history
mojomark history
```

### Generate Reports

```bash
# Generate Markdown + HTML reports from the latest run
mojomark report

# HTML only
mojomark report --format html

# Comparison report between two versions
mojomark report --compare-versions 0.7.0 0.26.1.0

# Custom output directory
mojomark report -o ./my-reports
```

### Manage Installations

```bash
# Remove all cached Mojo installations
mojomark clean
```

## Benchmark Categories

| Category    | Benchmarks                          | What It Measures                                          |
|-------------|-------------------------------------|-----------------------------------------------------------|
| **compute** | fibonacci, matrix_mul, sorting      | CPU-bound algorithms, loop optimization, recursion        |
| **memory**  | allocation, struct_ops              | Heap allocation, struct creation, field access, ownership |
| **simd**    | dot_product, mandelbrot, vector_math| Vectorized operations, floating-point throughput          |
| **strings** | concat, search                      | String building, byte-level traversal, substring search   |

## How It Works

1. **Version-aware benchmark discovery** — Benchmarks live in version-specific directories (`benchmarks/v0.7/`, `benchmarks/v0.26/`) to account for API changes between Mojo releases. The runner automatically selects the right benchmark set for the target version.

2. **Internal nanosecond timing** — Each `.mojo` benchmark self-times its hot loop using Mojo's native high-resolution timer (`time.now()` or `time.perf_counter_ns()`). Setup code is excluded from measurement. Benchmarks emit a `MOJOMARK_NS` marker that the Python harness parses.

3. **Machine fingerprinting** — Every result is tagged with CPU model, core count, RAM, OS, and architecture. This ensures comparisons are only meaningful on the same hardware.

4. **Automatic version management** — `mojomark` can discover, download, and cache multiple Mojo versions in isolated virtual environments under `~/.mojomark/`. It also detects system-installed Mojo for legacy versions.

5. **Regression classification** — Deltas are classified as improved (`>>`), stable (`OK`), warning (`!!`), or regression (`XX`) with configurable thresholds.

6. **Reports** — Generates both Markdown and HTML reports with full statistics (mean, median, min, max, std dev).

Python never enters the measurement window — all timing is pure Mojo.

## CLI Commands

| Command      | Description                                                    |
|--------------|----------------------------------------------------------------|
| `run`        | Run benchmarks against the current Mojo version                |
| `regression` | Full regression assessment between two versions (run + compare)|
| `compare`    | Compare previously stored results for two versions             |
| `report`     | Generate Markdown/HTML reports                                 |
| `status`     | Show current version, latest available, cached installations   |
| `versions`   | List all published Mojo versions from the package index        |
| `history`    | Show stored benchmark result files                             |
| `clean`      | Remove cached Mojo installations from ~/.mojomark              |

## Project Structure

```
mojomark/
├── src/mojomark/          # Python CLI harness
│   ├── cli.py             # Click-based CLI commands
│   ├── runner.py           # Benchmark discovery, compilation, execution
│   ├── compare.py          # Result diffing and regression classification
│   ├── report.py           # Markdown and HTML report generation
│   ├── storage.py          # JSON result persistence
│   ├── machine.py          # Hardware/OS fingerprinting
│   └── versions.py         # Mojo version management and caching
├── benchmarks/
│   ├── v0.7/              # Benchmarks for Mojo ≤0.7.x (DynamicVector, etc.)
│   │   ├── compute/
│   │   ├── memory/
│   │   ├── simd/
│   │   └── strings/
│   └── v0.26/             # Benchmarks for Mojo ≥0.26.x (List, comptime, etc.)
│       ├── compute/
│       ├── memory/
│       ├── simd/
│       └── strings/
├── results/               # Stored benchmark results (git-ignored)
├── reports/               # Generated comparison reports (git-ignored)
└── tests/                 # Python test suite
```

## Example Output

```
mojomark — Regression Assessment

  Machine:  Apple M1 Max, 10 cores, 32.0GB RAM, Darwin 23.6.0 (arm64)
  Base:     Mojo 0.7.0
  Target:   Mojo 0.26.1.0

             Regression Report: Mojo 0.7.0 → 0.26.1.0
┏━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ Category ┃ Benchmark   ┃    0.7.0 ┃ 0.26.1.0 ┃  Delta ┃ Status ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ compute  │ fibonacci   │  27.2 ms │  27.9 ms │  +2.4% │   OK   │
│ memory   │ allocation  │   1.8 ms │   1.2 ms │ -33.6% │   >>   │
│ memory   │ struct_ops  │ 143.1 us │  95.6 us │ -33.2% │   >>   │
│ simd     │ vector_math │   1.6 ms │   1.1 ms │ -33.1% │   >>   │
│ strings  │ concat      │ 421.2 ms │ 792.0 us │ -99.8% │   >>   │
│ strings  │ search      │  36.5 ms │ 278.9 us │ -99.2% │   >>   │
└──────────┴─────────────┴──────────┴──────────┴────────┴────────┘

  Summary: 5 improved, 1 stable, 3 warning, 1 regression
```

## License

MIT
