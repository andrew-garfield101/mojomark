# mojomark

[![CI](https://github.com/andrew-garfield101/mojomark/actions/workflows/ci.yml/badge.svg)](https://github.com/andrew-garfield101/mojomark/actions/workflows/ci.yml)

A performance regression detector for the [Mojo](https://www.modular.com/mojo) programming language.

Run standardized benchmarks across Mojo versions, track results over time, and detect performance regressions automatically.

## Why?

As Mojo evolves rapidly, compiler changes can introduce performance regressions (or improvements!) that go unnoticed. `mojomark` provides a repeatable, automated way to measure and compare Mojo's performance across versions — with machine fingerprinting, internal nanosecond timing, and a template-based code generation system that produces version-correct benchmarks from a single source of truth.

## Quick Start

### Prerequisites

- Python 3.10+
- Mojo installed (system or pip managed)

### Install

```bash
cd mojomark
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Check Your Environment

```bash
mojomark status
mojomark versions
```

### Run Benchmarks

```bash
mojomark run
mojomark run --category compute
mojomark run --samples 20 --warmup 5
```

### Regression Testing

```bash
mojomark regression current latest
mojomark regression 0.7.0 0.26.1.0
mojomark regression 0.7.0 0.26.1.0 --category compute --samples 20
```

### Compare, Report, Manage

```bash
mojomark compare 0.7.0 0.26.1.0
mojomark history
mojomark report
mojomark report --format html
mojomark report --compare-versions 0.7.0 0.26.1.0
mojomark clean
```

## Benchmark Categories

| Category    | Benchmarks                           | What It Measures                                          |
|-------------|--------------------------------------|-----------------------------------------------------------|
| **compute** | fibonacci, matrix_mul, sorting       | CPU-bound algorithms, loop optimization, recursion        |
| **memory**  | allocation, struct_ops               | Heap allocation, struct creation, field access, ownership |
| **simd**    | dot_product, mandelbrot, vector_math | Vectorized operations, floating-point throughput          |
| **strings** | concat, search                       | String building, byte-level traversal, substring search   |

## How It Works

1. **Template-based code generation** — Each benchmark is a single `.mojo` template in `benchmarks/templates/` with `{{TOKEN}}` markers and `{{#MODERN}}`/`{{#LEGACY}}` conditional blocks. The codegen module renders version-correct source for any Mojo release from a single file — no duplicated benchmarks across versions.

2. **Version profiles** — Three profiles (`modern` ≥0.26, `transitional` 0.25.x, `legacy` <0.25) define token mappings (`List`↔`DynamicVector`, `append`↔`push_back`, `comptime`↔`alias`, etc.) and select the appropriate timing harness.

3. **Dual timing harnesses** — Modern versions use Mojo's stdlib `benchmark.run[]` with `keep()` and `black_box()` for statistically rigorous, anti-optimized measurement. Legacy versions use `time.now()` with dead-code-elimination barriers. Both emit a `MOJOMARK_NS` marker that the Python harness parses.

4. **Machine fingerprinting** — Every result is tagged with CPU model, core count, RAM, OS, and architecture to ensure comparisons are only meaningful on the same hardware.

5. **Automatic version management** — `mojomark` discovers, downloads, and caches multiple Mojo versions in isolated virtual environments under `~/.mojomark/`. It also detects system-installed Mojo for legacy versions.

6. **Regression classification** — Deltas are classified as improved (`>>`), stable (`OK`), warning (`!!`), or regression (`XX`) with configurable thresholds.

7. **Reports** — Generates both Markdown and HTML reports with full statistics (mean, median, min, max, std dev).

Python never enters the measurement window — all timing is pure Mojo.

## CLI Commands

| Command      | Description                                                     |
|--------------|-----------------------------------------------------------------|
| `run`        | Run benchmarks against the current Mojo version                 |
| `regression` | Full regression assessment between two versions (run + compare) |
| `compare`    | Compare previously stored results for two versions              |
| `report`     | Generate Markdown/HTML reports                                  |
| `status`     | Show current version, latest available, cached installations    |
| `versions`   | List all published Mojo versions from the package index         |
| `history`    | Show stored benchmark result files                              |
| `list`       | List available benchmark templates                              |
| `clean`      | Remove cached Mojo installations from ~/.mojomark               |

## Project Structure

```
mojomark/
├── src/mojomark/
│   ├── cli.py             # Click-based CLI commands
│   ├── codegen.py         # Template rendering and version profiles
│   ├── runner.py          # Benchmark discovery, compilation, execution
│   ├── compare.py         # Result diffing and regression classification
│   ├── report.py          # Markdown and HTML report generation
│   ├── storage.py         # JSON result persistence
│   ├── machine.py         # Hardware/OS fingerprinting
│   └── versions.py        # Mojo version management and caching
├── benchmarks/
│   └── templates/         # Version-neutral benchmark templates
│       ├── compute/       # fibonacci, matrix_mul, sorting
│       ├── memory/        # allocation, struct_ops
│       ├── simd/          # dot_product, mandelbrot, vector_math
│       └── strings/       # concat, search
├── results/               # Stored benchmark results (git-ignored)
├── reports/               # Generated reports (git-ignored)
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
│ compute  │ fibonacci   │  22.5 ms │  22.4 ms │  -0.2% │   OK   │
│ compute  │ matrix_mul  │ 851.6 us │ 835.1 us │  -1.9% │   OK   │
│ compute  │ sorting     │   2.7 ms │   2.9 ms │  +7.5% │   !!   │
│ memory   │ allocation  │   1.9 ms │   1.0 ms │ -45.8% │   >>   │
│ memory   │ struct_ops  │ 149.3 us │  98.6 us │ -34.0% │   >>   │
│ simd     │ dot_product │   6.9 ms │   6.4 ms │  -8.1% │   >>   │
│ simd     │ mandelbrot  │  22.9 ms │  18.5 ms │ -19.1% │   >>   │
│ simd     │ vector_math │   1.4 ms │ 971.2 us │ -32.8% │   >>   │
│ strings  │ concat      │ 419.7 ms │ 680.3 us │ -99.8% │   >>   │
│ strings  │ search      │  37.1 ms │ 244.3 us │ -99.3% │   >>   │
└──────────┴─────────────┴──────────┴──────────┴────────┴────────┘

  Summary: 7 improved, 2 stable, 1 warning
```

## License

MIT
