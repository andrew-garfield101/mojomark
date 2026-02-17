# mojomark

[![CI](https://github.com/andrew-garfield101/mojomark/actions/workflows/ci.yml/badge.svg)](https://github.com/andrew-garfield101/mojomark/actions/workflows/ci.yml)

A performance regression detector for the [Mojo](https://www.modular.com/mojo) programming language.

Run standardized benchmarks across Mojo versions, track results over time, and detect performance regressions automatically.

## Why?

As Mojo evolves rapidly, compiler changes can introduce performance regressions (or improvements!) that go unnoticed. `mojomark` provides a repeatable, automated way to measure and compare Mojo's performance across versions, with machine fingerprinting, internal nanosecond timing, and a template based code generation system that produces version-correct benchmarks from a single source of truth.

## Quick Start

### Prerequisites

- Python 3.10+
- Mojo installed (system or pip managed)

### Install

```bash
pip install mojomark
```

Or install from source for development:

```bash
git clone https://github.com/andrew-garfield101/mojomark.git
cd mojomark
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure (Optional)

```bash
mojomark init
```

This creates a `mojomark.toml` in your project with default settings. Edit it to customize benchmark parameters and regression thresholds:

```toml
[benchmark]
samples = 10
warmup = 3

[thresholds]
stable = 3.0       # |delta| < 3%  →  OK
warning = 10.0     # delta >= 10%  →  XX REGRESSION
improved = -5.0    # delta <= -5%  →  >> improved

[report]
format = "both"    # markdown | html | both | none

[benchmarks]
# user_dir = "benchmarks"   # directory for custom user benchmarks
```

CLI flags always override config file values.

### Check Your Environment

```bash
mojomark doctor   
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
mojomark regression current latest --threshold-stable 5.0 --threshold-warning 15.0
```

Both `regression` and `compare` exit with code 1 if any regressions are detected, making them suitable for CI pipelines.

### Performance Trends

```bash
mojomark trend                                     # all benchmarks, bar chart view
mojomark trend --compact                           # sparkline table view
mojomark trend --category compute                  # filter by category
mojomark trend --benchmark fibonacci               # single benchmark
mojomark trend --versions 0.7.0,0.26.1.0           # specific versions
mojomark trend --export csv --output trends.csv    # export for external analysis
```

### Custom Benchmarks

Create your own benchmarks alongside the built-in suite:

```bash
mojomark add my_workload                        # scaffolds benchmarks/custom/my_workload.mojo
mojomark add matrix_inv --category compute       # custom category
mojomark add my_test --dir ~/my_benchmarks       # custom directory
mojomark validate benchmarks/custom/my_workload.mojo  # check template structure
```

Edit the scaffolded `.mojo` file to add your workload, then run:

```bash
mojomark run --category custom
```

User benchmarks are automatically discovered from `./benchmarks/` (or a custom path in `mojomark.toml`):

```toml
[benchmarks]
user_dir = "benchmarks"   # relative to mojomark.toml
```

Templates require three sections: `# ==WORKLOAD==` (the code to measure), `# KEEP: varname type` (prevents dead code elimination), and optionally `# ==SETUP==` and `# ==MODULE==` for initialization. User templates override built-in ones with the same category/name.

### Compare, Report, Manage

```bash
mojomark compare 0.7.0 0.26.1.0
mojomark history
mojomark report
mojomark report --format html
mojomark report --compare-versions 0.7.0 0.26.1.0
mojomark clean
```

### Output Control

Every command supports `--quiet` and `--verbose` flags:

```bash
mojomark --quiet regression current latest
mojomark --verbose run                         
mojomark -q compare 0.7.0 0.26.1.0             
```

### Shell Completion

Enable tab-completion for Zsh (add to `.zshrc` for persistence):

```bash
eval "$(_MOJOMARK_COMPLETE=zsh_source mojomark)"
```

For Bash:

```bash
eval "$(_MOJOMARK_COMPLETE=bash_source mojomark)"
```

## Benchmark Categories

| Category        | Benchmarks                                          | What It Measures                                              |
|-----------------|-----------------------------------------------------|---------------------------------------------------------------|
| **collections** | dict_ops                                            | Hash table insert/lookup, hashing overhead                    |
| **compute**     | fibonacci, matrix_mul, sorting                      | CPU-bound algorithms, loop optimization, recursion            |
| **io**          | file_read, file_write                               | Sequential I/O throughput, syscall overhead, buffering        |
| **memory**      | allocation, struct_ops                               | Heap allocation, struct creation, field access, ownership     |
| **simd**        | dot_product, explicit_vectorize, mandelbrot, vector_math | Vectorized ops, explicit SIMD, floating-point throughput |
| **strings**     | concat, search                                      | String building, byte-level traversal, substring search       |

## How It Works

1. **Template-based code generation** — Each benchmark is a single `.mojo` template in `benchmarks/templates/` with `{{TOKEN}}` markers and `{{#MODERN}}`/`{{#LEGACY}}` conditional blocks. The codegen module renders version-correct source for any Mojo release from a single file — no duplicated benchmarks across versions.

2. **Version profiles** — Three profiles (`modern` ≥0.26, `transitional` 0.25.x, `legacy` <0.25) define token mappings (`List`↔`DynamicVector`, `append`↔`push_back`, `comptime`↔`alias`, etc.) and select the appropriate timing harness.

3. **Dual timing harnesses** — Modern versions use Mojo's stdlib `benchmark.run[]` with `keep()` and `black_box()` for statistically rigorous, anti-optimized measurement. Legacy versions use `time.now()` with dead-code-elimination barriers. Both emit a `MOJOMARK_NS` marker that the Python harness parses.

4. **Machine fingerprinting** — Every result is tagged with CPU model, core count, RAM, OS, and architecture to ensure comparisons are only meaningful on the same hardware.

5. **Automatic version management** — `mojomark` discovers, downloads, and caches multiple Mojo versions in isolated virtual environments under `~/.mojomark/`. It also detects system-installed Mojo for legacy versions.

6. **Regression classification** — Deltas are classified as improved (`>>`), stable (`OK`), warning (`!!`), or regression (`XX`) with configurable thresholds.

7. **Reports** — Generates both Markdown and HTML reports with full statistics (mean, median, min, max, std dev).

Python never enters the measurement window all timing is pure Mojo.

## CLI Commands

| Command      | Description                                                     |
|--------------|-----------------------------------------------------------------|
| `run`        | Run benchmarks against the current Mojo version                 |
| `regression` | Full regression assessment between two versions (run + compare) |
| `compare`    | Compare previously stored results for two versions              |
| `trend`      | Show performance trends across all stored versions              |
| `report`     | Generate Markdown/HTML reports                                  |
| `add`        | Scaffold a new custom benchmark template                        |
| `validate`   | Check a template file for required structure                    |
| `doctor`     | Check system requirements and diagnose common issues            |
| `status`     | Show current version, latest available, cached installations    |
| `versions`   | List all published Mojo versions from the package index         |
| `history`    | Show stored benchmark result files                              |
| `list`       | List available benchmark templates (built-in + user)            |
| `init`       | Create a default `mojomark.toml` configuration file             |
| `clean`      | Remove cached Mojo installations from ~/.mojomark               |

## Project Structure

```
mojomark/
├── src/mojomark/
│   ├── cli.py             # Click-based CLI commands
│   ├── config.py          # Configuration loading (mojomark.toml)
│   ├── codegen.py         # Template rendering and version profiles
│   ├── runner.py          # Benchmark discovery, compilation, execution
│   ├── compare.py         # Result diffing and regression classification
│   ├── report.py          # Markdown and HTML report generation
│   ├── storage.py         # JSON result persistence
│   ├── machine.py         # Hardware/OS fingerprinting
│   ├── versions.py        # Mojo version management and caching
│   └── templates/         # Version-neutral benchmark templates (shipped with package)
│       ├── collections/   # dict_ops
│       ├── compute/       # fibonacci, matrix_mul, sorting
│       ├── io/            # file_read, file_write
│       ├── memory/        # allocation, struct_ops
│       ├── simd/          # dot_product, explicit_vectorize, mandelbrot, vector_math
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

  PASS: No regressions detected

  Thresholds: >> >5% faster | OK <3% change | !! 3-10% slower | XX >10% slower
```

## License

MIT
