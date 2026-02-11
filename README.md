# mojomark

[![CI](https://github.com/andrew-garfield101/mojomark/actions/workflows/ci.yml/badge.svg)](https://github.com/andrew-garfield101/mojomark/actions/workflows/ci.yml)

A performance regression detector for the [Mojo](https://www.modular.com/mojo) programming language.

Run standardized benchmarks across Mojo versions, track results over time, and detect performance regressions automatically.

## Why?

As Mojo evolves rapidly, compiler changes can introduce performance regressions (or improvements!) that go unnoticed. `mojomark` provides a repeatable, automated way to measure and compare Mojo's performance across versions.

## Quick Start

### Prerequisites

- Python 3.10+
- Mojo installed and on your PATH

### Install

```bash
cd mojomark
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run Benchmarks

```bash
# Run all benchmarks against current Mojo version
mojomark run

# Run specific category
mojomark run --category compute

# List available benchmarks
mojomark list
```

### Compare Results

```bash
# Compare two versions
mojomark compare 0.7.0 0.8.0
```

### Generate Reports

```bash
# Generate Markdown + HTML reports from the latest run
mojomark report

# HTML only
mojomark report --format html

# Comparison report between two versions
mojomark report --compare-versions 0.7.0 0.8.0

# Custom output directory
mojomark report -o ./my-reports
```

## Benchmark Categories

| Category | What It Measures |
|----------|-----------------|
| **compute** | CPU-bound algorithms (fibonacci, sorting, matrix multiplication) |
| **memory** | Allocation patterns, struct operations, copy/move semantics |
| **simd** | Vectorized operations, SIMD throughput, dot products |
| **strings** | String manipulation, concatenation, substring search |

## How It Works

1. Each benchmark is a standalone `.mojo` file that self-times using Mojo's native `time.now()` high-resolution timer
2. The Python CLI harness discovers, compiles, and runs each benchmark as a subprocess
3. Benchmarks output structured JSON with timing statistics
4. Results are stored as JSON files tagged with Mojo version and timestamp
5. The `compare` command diffs results across versions and flags regressions

Python never enters the measurement window — all timing is pure Mojo.

## Project Structure

```
mojomark/
├── src/mojomark/       # Python CLI harness
├── benchmarks/         # Mojo benchmark files
│   ├── compute/
│   ├── memory/
│   ├── simd/
│   └── strings/
├── results/            # Stored benchmark results (git-tracked)
├── reports/            # Generated comparison reports
└── tests/              # Python test suite
```

## License

MIT
