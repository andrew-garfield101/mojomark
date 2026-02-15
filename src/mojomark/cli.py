"""mojomark CLI — Mojo Performance Regression Detector."""

import sys

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from mojomark.compare import Status, Thresholds, compare_results, summarize_diffs
from mojomark.config import (
    CONFIG_FILENAME,
    DEFAULT_CONFIG_TEMPLATE,
    MojomarkConfig,
    load_config,
    merge_cli_overrides,
)
from mojomark.machine import format_machine_summary, get_machine_info
from mojomark.report import (
    format_time,
    generate_comparison_html,
    generate_comparison_markdown,
    generate_single_run_html,
    generate_single_run_markdown,
    save_report,
)
from mojomark.runner import discover_benchmarks, get_mojo_version, run_benchmark
from mojomark.storage import (
    find_results_for_version,
    list_result_files,
    load_results,
    save_results,
)
from mojomark.versions import (
    clean_cache,
    get_latest_available_version,
    get_mojo_binary,
    list_available_versions,
    list_cached_versions,
    resolve_version_alias,
)

console = Console()

VERBOSITY_QUIET = 0
VERBOSITY_NORMAL = 1
VERBOSITY_VERBOSE = 2

_verbosity: int = VERBOSITY_NORMAL


def _info(msg: str) -> None:
    """Print a message at normal verbosity or above."""
    if _verbosity >= VERBOSITY_NORMAL:
        console.print(msg)


def _detail(msg: str) -> None:
    """Print a message only in verbose mode."""
    if _verbosity >= VERBOSITY_VERBOSE:
        console.print(msg)


def _load_cfg() -> MojomarkConfig:
    """Load the project config, printing a note if a file is found."""
    cfg = load_config()
    if cfg.config_path:
        _detail(f"  [dim]Config: {cfg.config_path}[/dim]")
    return cfg


def _thresholds_from_cfg(cfg: MojomarkConfig) -> Thresholds:
    """Build a Thresholds object from the merged config."""
    return Thresholds(
        stable=cfg.threshold_stable,
        warning=cfg.threshold_warning,
        improved=cfg.threshold_improved,
    )


def _make_progress() -> Progress:
    """Create a Rich progress bar for benchmark runs."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    )


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="mojomark")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output — tables and verdicts only.")
@click.option("--verbose", "-V", is_flag=True, help="Extra diagnostic output.")
@click.pass_context
def main(ctx: click.Context, quiet: bool, verbose: bool):
    """mojomark — Mojo Performance Regression Detector."""
    global _verbosity
    if quiet:
        _verbosity = VERBOSITY_QUIET
    elif verbose:
        _verbosity = VERBOSITY_VERBOSE
    else:
        _verbosity = VERBOSITY_NORMAL

    ctx.ensure_object(dict)
    ctx.obj["verbosity"] = _verbosity


# ---------------------------------------------------------------------------
# init command
# ---------------------------------------------------------------------------


@main.command()
@click.option("--force", is_flag=True, help="Overwrite existing config file.")
def init(force: bool):
    """Create a default mojomark.toml configuration file.

    Generates a commented config file in the current directory with
    all available settings and their default values.

    Examples:

        mojomark init

        mojomark init --force
    """
    from pathlib import Path

    target = Path.cwd() / CONFIG_FILENAME
    if target.exists() and not force:
        console.print(f"[yellow]{CONFIG_FILENAME} already exists.[/yellow]")
        console.print("[dim]Use --force to overwrite.[/dim]")
        return

    target.write_text(DEFAULT_CONFIG_TEMPLATE)
    console.print(f"[green]✓[/green] Created {CONFIG_FILENAME}")
    _info("[dim]Edit the file to customize benchmark settings and thresholds.[/dim]")


# ---------------------------------------------------------------------------
# run command
# ---------------------------------------------------------------------------


@main.command()
@click.option("--category", "-c", default=None, help="Run only benchmarks in this category.")
@click.option("--samples", "-s", default=None, type=int, help="Number of timed samples.")
@click.option("--warmup", "-w", default=None, type=int, help="Number of warmup runs.")
def run(category: str | None, samples: int | None, warmup: int | None):
    """Run benchmarks against the current Mojo version."""
    cfg = _load_cfg()
    merge_cli_overrides(cfg, samples=samples, warmup=warmup)

    mojo_version = get_mojo_version()
    _info("[bold cyan]mojomark[/bold cyan] — Mojo Performance Regression Detector")
    _info(f"  Mojo version: [bold]{mojo_version}[/bold]")
    _info(f"  Samples: {cfg.samples} | Warmup: {cfg.warmup}")
    _info("")

    benchmarks = discover_benchmarks(category=category)
    if not benchmarks:
        console.print("[yellow]No benchmarks found.[/yellow]")
        return

    _info(f"Running {len(benchmarks)} benchmark(s)...\n")

    results = []
    if _verbosity >= VERBOSITY_NORMAL:
        with _make_progress() as progress:
            task = progress.add_task("Starting...", total=len(benchmarks))
            for name, bench_category, mojo_file in benchmarks:
                label = f"{bench_category}/{name}"
                progress.update(task, description=f"Running {label}")
                try:
                    result = run_benchmark(
                        mojo_file=mojo_file,
                        name=name,
                        category=bench_category,
                        samples=cfg.samples,
                        warmup=cfg.warmup,
                        mojo_version=mojo_version,
                    )
                    results.append(result)
                    _detail(f"    [green]✓[/green] {label:30s} {format_time(result.mean_ns)}")
                except RuntimeError as e:
                    progress.console.print(f"  [red]FAILED:[/red] {label} — {e}")
                progress.advance(task)
    else:
        for name, bench_category, mojo_file in benchmarks:
            label = f"{bench_category}/{name}"
            try:
                result = run_benchmark(
                    mojo_file=mojo_file,
                    name=name,
                    category=bench_category,
                    samples=cfg.samples,
                    warmup=cfg.warmup,
                    mojo_version=mojo_version,
                )
                results.append(result)
            except RuntimeError as e:
                console.print(f"  [red]FAILED:[/red] {label} — {e}")

    if not results:
        console.print("[red]All benchmarks failed.[/red]")
        return

    table = Table(title="Benchmark Results", show_lines=False)
    table.add_column("Category", style="dim", no_wrap=True)
    table.add_column("Benchmark", style="bold", no_wrap=True)
    table.add_column("Mean", justify="right", style="cyan", no_wrap=True)
    table.add_column("Median", justify="right", no_wrap=True)
    table.add_column("Min", justify="right", style="green", no_wrap=True)
    table.add_column("Max", justify="right", style="red", no_wrap=True)
    table.add_column("Std Dev", justify="right", style="dim", no_wrap=True)

    for r in results:
        table.add_row(
            r.category,
            r.name,
            format_time(r.mean_ns),
            format_time(r.median_ns),
            format_time(r.min_ns),
            format_time(r.max_ns),
            format_time(r.std_dev_ns),
        )

    console.print(table)

    filepath = save_results(results, mojo_version)
    _info(f"\n[dim]Results saved → {filepath}[/dim]")


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------


@main.command(name="list")
@click.option("--category", "-c", default=None, help="Filter by category.")
def list_benchmarks(category: str | None):
    """List available benchmarks."""
    benchmarks = discover_benchmarks(category=category)
    if not benchmarks:
        console.print("[yellow]No benchmarks found.[/yellow]")
        return

    table = Table(title="Available Benchmarks")
    table.add_column("Category", style="dim")
    table.add_column("Benchmark", style="bold")
    table.add_column("File", style="dim")

    for name, bench_category, path in benchmarks:
        table.add_row(bench_category, name, str(path.relative_to(path.parent.parent)))

    console.print(table)


# ---------------------------------------------------------------------------
# compare command
# ---------------------------------------------------------------------------

_threshold_options = [
    click.option(
        "--threshold-stable",
        type=float,
        default=None,
        help="Max |delta|%% for STABLE (default: from config or 3.0).",
    ),
    click.option(
        "--threshold-warning",
        type=float,
        default=None,
        help="Min delta%% for REGRESSION (default: from config or 10.0).",
    ),
    click.option(
        "--threshold-improved",
        type=float,
        default=None,
        help="Max delta%% for IMPROVED (default: from config or -5.0).",
    ),
]


def _add_threshold_options(func):
    """Apply shared threshold CLI options to a command."""
    for option in reversed(_threshold_options):
        func = option(func)
    return func


@main.command()
@click.argument("base_version")
@click.argument("target_version")
@_add_threshold_options
def compare(
    base_version: str,
    target_version: str,
    threshold_stable: float | None,
    threshold_warning: float | None,
    threshold_improved: float | None,
):
    """Compare benchmark results between two Mojo versions.

    BASE_VERSION is the older/reference version.
    TARGET_VERSION is the newer version to evaluate.

    Exits with code 1 if any regressions are detected.

    Examples:

        mojomark compare 0.7.0 0.8.0

        mojomark compare 0.7.0 0.8.0 --threshold-stable 5.0
    """
    cfg = _load_cfg()
    merge_cli_overrides(
        cfg,
        threshold_stable=threshold_stable,
        threshold_warning=threshold_warning,
        threshold_improved=threshold_improved,
    )
    thresholds = _thresholds_from_cfg(cfg)

    _info(
        f"[bold cyan]mojomark[/bold cyan] — Comparing "
        f"[bold]{base_version}[/bold] -> [bold]{target_version}[/bold]"
    )
    _info("")

    base_file = find_results_for_version(base_version)
    if base_file is None:
        console.print(f"[red]No results found for Mojo {base_version}[/red]")
        console.print("[dim]Run 'mojomark history' to see available results.[/dim]")
        return

    target_file = find_results_for_version(target_version)
    if target_file is None:
        console.print(f"[red]No results found for Mojo {target_version}[/red]")
        console.print("[dim]Run 'mojomark history' to see available results.[/dim]")
        return

    base_data = load_results(base_file)
    target_data = load_results(target_file)

    diffs = compare_results(base_data, target_data, thresholds=thresholds)
    if not diffs:
        console.print("[yellow]No matching benchmarks found between the two runs.[/yellow]")
        return

    has_regressions = _print_comparison_table(base_version, target_version, diffs, thresholds)

    if has_regressions:
        sys.exit(1)


# ---------------------------------------------------------------------------
# history command
# ---------------------------------------------------------------------------


@main.command()
def history():
    """Show all stored benchmark results."""
    result_files = list_result_files()
    if not result_files:
        console.print("[yellow]No stored results found.[/yellow]")
        console.print("[dim]Run 'mojomark run' to generate results.[/dim]")
        return

    table = Table(title="Stored Results")
    table.add_column("Version", style="bold", no_wrap=True)
    table.add_column("Timestamp", no_wrap=True)
    table.add_column("Benchmarks", justify="right")
    table.add_column("File", style="dim")

    for filepath in result_files:
        data = load_results(filepath)
        table.add_row(
            data["mojo_version"],
            data["timestamp"][:19].replace("T", " "),
            str(len(data["benchmarks"])),
            filepath.name,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["markdown", "html", "both"]),
    default=None,
    help="Output format (default: from config or both).",
)
@click.option("--version", "-v", "version", default=None, help="Mojo version to report on.")
@click.option(
    "--compare-versions",
    "-c",
    nargs=2,
    default=None,
    help="Two versions to compare: BASE TARGET.",
)
@click.option("--output", "-o", "output_dir", default=None, help="Custom output directory.")
def report(
    fmt: str | None,
    version: str | None,
    compare_versions: tuple[str, str] | None,
    output_dir: str | None,
):
    """Generate Markdown and/or HTML reports from benchmark results.

    By default, generates a report from the most recent result.
    Use --compare-versions to generate a comparison report.

    Examples:

        mojomark report

        mojomark report --format markdown

        mojomark report --compare-versions 0.7.0 0.8.0

        mojomark report -v 0.8.0 -f html
    """
    from pathlib import Path

    from mojomark.report import REPORTS_DIR

    cfg = _load_cfg()
    merge_cli_overrides(cfg, fmt=fmt, output_dir=output_dir)

    report_fmt = cfg.report_format
    reports_dir = Path(cfg.report_output_dir) if cfg.report_output_dir else REPORTS_DIR
    generated: list[Path] = []

    if compare_versions:
        base_ver, target_ver = compare_versions

        base_file = find_results_for_version(base_ver)
        if base_file is None:
            console.print(f"[red]No results found for Mojo {base_ver}[/red]")
            console.print("[dim]Run 'mojomark history' to see available results.[/dim]")
            return

        target_file = find_results_for_version(target_ver)
        if target_file is None:
            console.print(f"[red]No results found for Mojo {target_ver}[/red]")
            console.print("[dim]Run 'mojomark history' to see available results.[/dim]")
            return

        base_data = load_results(base_file)
        target_data = load_results(target_file)

        diffs = compare_results(base_data, target_data)
        if not diffs:
            console.print("[yellow]No matching benchmarks found between versions.[/yellow]")
            return

        timestamp = _report_timestamp()

        if report_fmt in ("markdown", "both"):
            md = generate_comparison_markdown(base_data, target_data, diffs)
            fname = f"{timestamp}_compare_{base_ver}_vs_{target_ver}.md"
            path = save_report(md, fname, reports_dir)
            generated.append(path)

        if report_fmt in ("html", "both"):
            html = generate_comparison_html(base_data, target_data, diffs)
            path = save_report(
                html, f"{timestamp}_compare_{base_ver}_vs_{target_ver}.html", reports_dir
            )
            generated.append(path)

    else:
        if version:
            result_file = find_results_for_version(version)
            if result_file is None:
                console.print(f"[red]No results found for Mojo {version}[/red]")
                console.print("[dim]Run 'mojomark history' to see available results.[/dim]")
                return
        else:
            result_files = list_result_files()
            if not result_files:
                console.print("[yellow]No stored results found.[/yellow]")
                console.print("[dim]Run 'mojomark run' first to generate results.[/dim]")
                return
            result_file = result_files[0]

        result_data = load_results(result_file)
        mojo_ver = result_data["mojo_version"]
        timestamp = _report_timestamp()

        if report_fmt in ("markdown", "both"):
            md = generate_single_run_markdown(result_data)
            path = save_report(md, f"{timestamp}_mojo-{mojo_ver}.md", reports_dir)
            generated.append(path)

        if report_fmt in ("html", "both"):
            html = generate_single_run_html(result_data)
            path = save_report(html, f"{timestamp}_mojo-{mojo_ver}.html", reports_dir)
            generated.append(path)

    console.print("[bold cyan]mojomark[/bold cyan] — Report generated")
    for path in generated:
        console.print(f"  [green]✓[/green] {path}")


def _report_timestamp() -> str:
    """Generate a timestamp string for report filenames."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------


@main.command()
def status():
    """Show current Mojo version, latest available, and stored baselines."""
    console.print("[bold cyan]mojomark[/bold cyan] — Status\n")

    cfg = load_config()
    if cfg.config_path:
        console.print(f"  Config:   [dim]{cfg.config_path}[/dim]")

    machine = get_machine_info()
    console.print(f"  Machine:  [bold]{format_machine_summary(machine)}[/bold]")

    installed = get_mojo_version()
    if installed == "unknown":
        console.print("  Installed Mojo:  [red]not found[/red]")
    else:
        console.print(f"  Installed Mojo:  [bold]{installed}[/bold]")

    with console.status("[dim]Checking latest version...[/dim]"):
        latest = get_latest_available_version()
    if latest:
        if installed != "unknown" and installed == latest:
            console.print(f"  Latest stable:   [green]{latest} (you're current)[/green]")
        else:
            console.print(f"  Latest stable:   [yellow]{latest}[/yellow]")
    else:
        console.print("  Latest stable:   [dim]could not check[/dim]")

    cached = list_cached_versions()
    if cached:
        console.print(f"\n  Cached installs:  {', '.join(cached)}")

    result_files = list_result_files()
    if result_files:
        console.print("\n  Stored baselines:")
        for filepath in result_files:
            data = load_results(filepath)
            ver = data["mojo_version"]
            ts = data["timestamp"][:19].replace("T", " ")
            n = len(data["benchmarks"])
            console.print(f"    {ver}  →  {n} benchmarks  ({ts})")
    else:
        console.print("\n  [dim]No stored baselines. Run 'mojomark run' to create one.[/dim]")

    if latest and installed != "unknown" and installed != latest:
        console.print(
            f"\n  [dim]Upgrade:[/dim] "
            f"pip install mojo=={latest} "
            f"--extra-index-url https://modular.gateway.scarf.sh/simple/"
        )
        console.print("  [dim]Then run:[/dim] mojomark run")


# ---------------------------------------------------------------------------
# versions command
# ---------------------------------------------------------------------------


@main.command()
def versions():
    """Show all available Mojo versions from the package index.

    Displays every published release with markers for the currently installed
    version and any versions already cached locally.

    Examples:

        mojomark versions
    """
    from mojomark.runner import get_mojo_version

    console.print("[bold cyan]mojomark[/bold cyan] — Mojo Versions\n")

    installed = get_mojo_version()
    cached = set(list_cached_versions())

    with console.status("[dim]Fetching available versions...[/dim]"):
        available = list_available_versions()
        latest = get_latest_available_version()

    if installed != "unknown":
        console.print(f"  Installed:  [bold]{installed}[/bold]")
    else:
        console.print("  Installed:  [red]not found[/red]")

    if latest:
        console.print(f"  Latest:     [bold green]{latest}[/bold green]")

    if cached:
        console.print(f"  Cached:     {', '.join(sorted(cached))}")

    if available is None:
        console.print("\n  [red]Could not fetch version list (check your network).[/red]")
        return

    console.print(f"\n  [bold]{len(available)}[/bold] published release(s):\n")

    row: list[str] = []
    for v in available:
        label = v
        markers: list[str] = []
        if v == installed:
            markers.append("installed")
        if v in cached:
            markers.append("cached")
        if v == latest:
            markers.append("latest")

        if markers:
            label = f"[bold]{v}[/bold] [dim]({', '.join(markers)})[/dim]"

        row.append(label)
        if len(row) == 5:
            console.print("    " + "   ".join(row))
            row = []
    if row:
        console.print("    " + "   ".join(row))

    console.print(
        "\n  [dim]Tip: mojomark regression current latest[/dim]"
        "\n  [dim]     mojomark regression 0.7.0 0.26.1[/dim]"
    )


# ---------------------------------------------------------------------------
# doctor command
# ---------------------------------------------------------------------------


@main.command()
def doctor():
    """Check system requirements and diagnose common issues.

    Verifies that all dependencies are available and the mojomark
    environment is correctly configured.

    Examples:

        mojomark doctor
    """
    import platform
    import shutil

    console.print("[bold cyan]mojomark[/bold cyan] — Doctor\n")
    checks_passed = 0
    checks_failed = 0

    def _pass(msg: str) -> None:
        nonlocal checks_passed
        console.print(f"  [green]✓[/green] {msg}")
        checks_passed += 1

    def _fail(msg: str, hint: str = "") -> None:
        nonlocal checks_failed
        console.print(f"  [red]✗[/red] {msg}")
        if hint:
            console.print(f"    [dim]{hint}[/dim]")
        checks_failed += 1

    py_version = platform.python_version()
    py_tuple = tuple(int(x) for x in py_version.split(".")[:2])
    if py_tuple >= (3, 10):
        _pass(f"Python {py_version}")
    else:
        _fail(f"Python {py_version}", "Python 3.10+ is required.")

    mojo_path = shutil.which("mojo")
    if mojo_path:
        version = get_mojo_version()
        _pass(f"Mojo {version} ({mojo_path})")
    else:
        _fail("Mojo not found on PATH", "Install Mojo: pip install mojo")

    cfg = load_config()
    if cfg.config_path:
        _pass(f"Config: {cfg.config_path}")
    else:
        _pass(f"Config: using defaults (no {CONFIG_FILENAME} found)")

    benchmarks = discover_benchmarks()
    if benchmarks:
        categories = len({b[1] for b in benchmarks})
        _pass(f"Benchmarks: {len(benchmarks)} templates in {categories} categories")
    else:
        _fail("No benchmark templates found", "Check benchmarks/templates/ directory.")

    from mojomark.storage import RESULTS_DIR

    try:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        test_file = RESULTS_DIR / ".doctor_test"
        test_file.write_text("ok")
        test_file.unlink()
        _pass(f"Results dir: {RESULTS_DIR}")
    except OSError as e:
        _fail(f"Results dir not writable: {e}")

    with console.status("[dim]Checking network...[/dim]"):
        latest = get_latest_available_version()
    if latest:
        _pass(f"Network: PyPI reachable (latest Mojo: {latest})")
    else:
        _fail("Network: could not reach PyPI", "Check your internet connection.")

    console.print()
    if checks_failed == 0:
        console.print(
            f"  [bold green]All {checks_passed} checks passed.[/bold green] "
            "mojomark is ready to go."
        )
    else:
        console.print(
            f"  [bold yellow]{checks_passed} passed, {checks_failed} failed.[/bold yellow]"
        )

    console.print(
        "\n  [dim]Shell completion: "
        'eval "$(_MOJOMARK_COMPLETE=zsh_source mojomark)"[/dim]'
        "\n  [dim]Add this to your .zshrc for persistent tab-completion.[/dim]"
    )


# ---------------------------------------------------------------------------
# regression command
# ---------------------------------------------------------------------------


def _run_benchmarks_with_version(
    version: str,
    benchmarks: list,
    samples: int,
    warmup: int,
) -> list:
    """Install a Mojo version and run all benchmarks against it.

    Returns:
        List of BenchmarkResult objects (may be shorter than benchmarks
        if some fail to compile on this version).
    """

    def progress(msg):
        _info(f"  [dim]{msg}[/dim]")

    mojo_binary = get_mojo_binary(version, on_progress=progress)

    actual = get_mojo_version(mojo_binary)
    _info(f"  Mojo {actual} ready\n")

    results = []
    if _verbosity >= VERBOSITY_NORMAL:
        with _make_progress() as prog:
            task = prog.add_task("Starting...", total=len(benchmarks))
            for name, bench_category, mojo_file in benchmarks:
                label = f"{bench_category}/{name}"
                prog.update(task, description=f"Running {label}")
                try:
                    result = run_benchmark(
                        mojo_file=mojo_file,
                        name=name,
                        category=bench_category,
                        samples=samples,
                        warmup=warmup,
                        mojo_binary=mojo_binary,
                        mojo_version=version,
                    )
                    results.append(result)
                    prog.console.print(
                        f"    [green]✓[/green] {label:30s} {format_time(result.mean_ns)}"
                    )
                except RuntimeError as e:
                    prog.console.print(f"    [red]✗[/red] {label:30s} FAILED — {e}")
                prog.advance(task)
    else:
        for name, bench_category, mojo_file in benchmarks:
            label = f"{bench_category}/{name}"
            try:
                result = run_benchmark(
                    mojo_file=mojo_file,
                    name=name,
                    category=bench_category,
                    samples=samples,
                    warmup=warmup,
                    mojo_binary=mojo_binary,
                    mojo_version=version,
                )
                results.append(result)
            except RuntimeError as e:
                console.print(f"    [red]✗[/red] {label:30s} FAILED — {e}")

    return results


def _print_comparison_table(base_ver, target_ver, diffs, thresholds=None):
    """Print a Rich comparison table, summary, and verdict.

    Returns:
        True if regressions were detected.
    """
    table = Table(
        title=f"Regression Report: Mojo {base_ver} → {target_ver}",
        show_lines=False,
    )
    table.add_column("Category", style="dim", no_wrap=True)
    table.add_column("Benchmark", style="bold", no_wrap=True)
    table.add_column(base_ver, justify="right", no_wrap=True)
    table.add_column(target_ver, justify="right", no_wrap=True)
    table.add_column("Delta", justify="right", no_wrap=True)
    table.add_column("Status", justify="center", no_wrap=True)

    t = thresholds or Thresholds()

    for d in diffs:
        if d.delta_pct <= t.improved:
            delta_str = f"[bold green]{d.delta_pct:+.1f}%[/bold green]"
        elif abs(d.delta_pct) < t.stable:
            delta_str = f"[green]{d.delta_pct:+.1f}%[/green]"
        elif d.delta_pct >= t.warning:
            delta_str = f"[bold red]{d.delta_pct:+.1f}%[/bold red]"
        else:
            delta_str = f"[yellow]{d.delta_pct:+.1f}%[/yellow]"

        table.add_row(
            d.category,
            d.name,
            format_time(d.base_mean_ns),
            format_time(d.target_mean_ns),
            delta_str,
            d.status.indicator,
        )

    console.print()
    console.print(table)

    summary = summarize_diffs(diffs)
    parts = []
    if summary[Status.IMPROVED]:
        parts.append(f"[bold green]{summary[Status.IMPROVED]} improved[/bold green]")
    if summary[Status.STABLE]:
        parts.append(f"[green]{summary[Status.STABLE]} stable[/green]")
    if summary[Status.WARNING]:
        parts.append(f"[yellow]{summary[Status.WARNING]} warning[/yellow]")
    if summary[Status.REGRESSION]:
        parts.append(f"[bold red]{summary[Status.REGRESSION]} regression[/bold red]")

    console.print(f"\n  Summary: {', '.join(parts)}")

    has_regressions = summary[Status.REGRESSION] > 0
    if has_regressions:
        console.print(
            f"\n  [bold red]FAIL: {summary[Status.REGRESSION]} regression(s) detected[/bold red]"
        )
    else:
        console.print("\n  [bold green]PASS: No regressions detected[/bold green]")

    _info(
        f"\n  [dim]Thresholds: "
        f">> >{abs(t.improved):.0f}% faster | "
        f"OK <{t.stable:.0f}% change | "
        f"!! {t.stable:.0f}-{t.warning:.0f}% slower | "
        f"XX >{t.warning:.0f}% slower[/dim]"
    )

    return has_regressions


@main.command()
@click.argument("base_version", metavar="BASE")
@click.argument("target_version", metavar="TARGET")
@click.option("--category", "-c", default=None, help="Run only benchmarks in this category.")
@click.option("--samples", "-s", default=None, type=int, help="Number of timed samples.")
@click.option("--warmup", "-w", default=None, type=int, help="Number of warmup runs.")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["markdown", "html", "both", "none"]),
    default=None,
    help="Report format (default: from config or both).",
)
@_add_threshold_options
def regression(
    base_version: str,
    target_version: str,
    category: str | None,
    samples: int | None,
    warmup: int | None,
    fmt: str | None,
    threshold_stable: float | None,
    threshold_warning: float | None,
    threshold_improved: float | None,
):
    """Run a full regression assessment between two Mojo versions.

    Installs both versions into isolated environments, benchmarks each,
    and compares results back-to-back on the same machine.

    Use the special aliases ``current`` (your installed version) and
    ``latest`` (newest release on the package index) instead of explicit
    version numbers.

    Exits with code 1 if any regressions are detected, making this
    command suitable for CI pipelines.

    Examples:

        mojomark regression current latest

        mojomark regression 0.7.0 0.26.1

        mojomark regression 0.7.0 0.26.1 --threshold-stable 5.0

        mojomark regression 0.7.0 0.26.1 --category compute --samples 20
    """
    cfg = _load_cfg()
    merge_cli_overrides(
        cfg,
        samples=samples,
        warmup=warmup,
        fmt=fmt,
        threshold_stable=threshold_stable,
        threshold_warning=threshold_warning,
        threshold_improved=threshold_improved,
    )
    thresholds = _thresholds_from_cfg(cfg)

    try:
        base_version = resolve_version_alias(base_version)
        target_version = resolve_version_alias(target_version)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        return

    if base_version == target_version:
        console.print(
            f"[yellow]Base and target are the same version ({base_version}). "
            "Nothing to compare.[/yellow]"
        )
        return

    machine = get_machine_info()

    _info("[bold cyan]mojomark[/bold cyan] — Regression Assessment\n")
    _info(f"  Machine:  {format_machine_summary(machine)}")
    _info(f"  Base:     Mojo {base_version}")
    _info(f"  Target:   Mojo {target_version}")
    _info(f"  Samples:  {cfg.samples} | Warmup: {cfg.warmup}")
    _info("")

    benchmarks = discover_benchmarks(category=category)

    if not benchmarks:
        console.print("[yellow]No benchmarks found.[/yellow]")
        return

    _info(f"  Benchmarks: {len(benchmarks)} templates\n")

    if _verbosity >= VERBOSITY_NORMAL:
        console.rule(f"[bold]Phase 1 — Mojo {base_version}[/bold]")
    try:
        base_results = _run_benchmarks_with_version(
            base_version, benchmarks, cfg.samples, cfg.warmup
        )
    except RuntimeError as e:
        console.print(f"\n[red]Failed to set up Mojo {base_version}:[/red] {e}")
        return

    if not base_results:
        console.print(f"[red]All benchmarks failed on Mojo {base_version}.[/red]")
        return

    base_path = save_results(base_results, base_version)
    _info(f"\n  [dim]Saved → {base_path}[/dim]")

    if _verbosity >= VERBOSITY_NORMAL:
        console.print()
        console.rule(f"[bold]Phase 2 — Mojo {target_version}[/bold]")
    try:
        target_results = _run_benchmarks_with_version(
            target_version, benchmarks, cfg.samples, cfg.warmup
        )
    except RuntimeError as e:
        console.print(f"\n[red]Failed to set up Mojo {target_version}:[/red] {e}")
        return

    if not target_results:
        console.print(f"[red]All benchmarks failed on Mojo {target_version}.[/red]")
        return

    target_path = save_results(target_results, target_version)
    _info(f"\n  [dim]Saved → {target_path}[/dim]")

    if _verbosity >= VERBOSITY_NORMAL:
        console.print()
        console.rule("[bold]Regression Report[/bold]")

    base_data = load_results(base_path)
    target_data = load_results(target_path)

    diffs = compare_results(base_data, target_data, thresholds=thresholds)
    if not diffs:
        console.print("[yellow]No matching benchmarks to compare.[/yellow]")
        return

    has_regressions = _print_comparison_table(base_version, target_version, diffs, thresholds)

    report_fmt = cfg.report_format
    if report_fmt != "none":
        from mojomark.report import REPORTS_DIR

        reports_dir = REPORTS_DIR
        timestamp = _report_timestamp()
        generated = []

        if report_fmt in ("markdown", "both"):
            md = generate_comparison_markdown(base_data, target_data, diffs)
            fname = f"{timestamp}_regression_{base_version}_vs_{target_version}.md"
            path = save_report(md, fname, reports_dir)
            generated.append(path)

        if report_fmt in ("html", "both"):
            html = generate_comparison_html(base_data, target_data, diffs)
            fname = f"{timestamp}_regression_{base_version}_vs_{target_version}.html"
            path = save_report(html, fname, reports_dir)
            generated.append(path)

        _info("")
        for path in generated:
            _info(f"  [green]✓[/green] {path}")

    if has_regressions:
        sys.exit(1)


# ---------------------------------------------------------------------------
# clean command
# ---------------------------------------------------------------------------


@main.command()
@click.confirmation_option(prompt="Remove all cached Mojo installations?")
def clean():
    """Remove cached Mojo installations from ~/.mojomark."""
    removed = clean_cache()
    if removed:
        console.print(f"[green]Removed {len(removed)} cached version(s):[/green]")
        for v in removed:
            console.print(f"  Mojo {v}")
    else:
        console.print("[dim]No cached installations to remove.[/dim]")
