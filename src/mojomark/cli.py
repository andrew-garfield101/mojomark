"""mojomark CLI — Mojo Performance Regression Detector."""

import click
from rich.console import Console
from rich.table import Table

from mojomark.compare import Status, compare_results, summarize_diffs
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


@click.group()
@click.version_option(package_name="mojomark")
def main():
    """mojomark — Mojo Performance Regression Detector."""
    pass


@main.command()
@click.option("--category", "-c", default=None, help="Run only benchmarks in this category.")
@click.option("--samples", "-s", default=10, help="Number of timed samples per benchmark.")
@click.option("--warmup", "-w", default=3, help="Number of warmup runs per benchmark.")
def run(category: str | None, samples: int, warmup: int):
    """Run benchmarks against the current Mojo version."""
    mojo_version = get_mojo_version()
    console.print("[bold cyan]mojomark[/bold cyan] — Mojo Performance Regression Detector")
    console.print(f"  Mojo version: [bold]{mojo_version}[/bold]")
    console.print(f"  Samples: {samples} | Warmup: {warmup}")
    console.print()

    benchmarks = discover_benchmarks(category=category)
    if not benchmarks:
        console.print("[yellow]No benchmarks found.[/yellow]")
        return

    console.print(f"Running {len(benchmarks)} benchmark(s)...\n")

    results = []
    for name, bench_category, mojo_file in benchmarks:
        label = f"{bench_category}/{name}"
        with console.status(f"[bold green]Running {label}...[/bold green]"):
            try:
                result = run_benchmark(
                    mojo_file=mojo_file,
                    name=name,
                    category=bench_category,
                    samples=samples,
                    warmup=warmup,
                )
                results.append(result)
            except RuntimeError as e:
                console.print(f"  [red]FAILED:[/red] {label} — {e}")

    if not results:
        console.print("[red]All benchmarks failed.[/red]")
        return

    # Display results table
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

    # Save results
    filepath = save_results(results, mojo_version)
    console.print(f"\n[dim]Results saved → {filepath}[/dim]")


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


@main.command()
@click.argument("base_version")
@click.argument("target_version")
def compare(base_version: str, target_version: str):
    """Compare benchmark results between two Mojo versions.

    BASE_VERSION is the older/reference version.
    TARGET_VERSION is the newer version to evaluate.

    Examples:
        mojomark compare 0.7.0 0.8.0
    """
    console.print(
        f"[bold cyan]mojomark[/bold cyan] — Comparing "
        f"[bold]{base_version}[/bold] -> [bold]{target_version}[/bold]"
    )
    console.print()

    # Find result files for each version
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

    diffs = compare_results(base_data, target_data)
    if not diffs:
        console.print("[yellow]No matching benchmarks found between the two runs.[/yellow]")
        return

    # Build comparison table
    table = Table(
        title=f"Comparison: Mojo {base_version} -> {target_version}",
        show_lines=False,
    )
    table.add_column("Category", style="dim", no_wrap=True)
    table.add_column("Benchmark", style="bold", no_wrap=True)
    table.add_column(base_version, justify="right", no_wrap=True)
    table.add_column(target_version, justify="right", no_wrap=True)
    table.add_column("Delta", justify="right", no_wrap=True)
    table.add_column("Status", justify="center", no_wrap=True)

    for d in diffs:
        # Color the delta based on direction
        if d.delta_pct <= -5:
            delta_str = f"[bold green]{d.delta_pct:+.1f}%[/bold green]"
        elif d.delta_pct < 3:
            delta_str = f"[green]{d.delta_pct:+.1f}%[/green]"
        elif d.delta_pct < 10:
            delta_str = f"[yellow]{d.delta_pct:+.1f}%[/yellow]"
        else:
            delta_str = f"[bold red]{d.delta_pct:+.1f}%[/bold red]"

        table.add_row(
            d.category,
            d.name,
            format_time(d.base_mean_ns),
            format_time(d.target_mean_ns),
            delta_str,
            d.status.indicator,
        )

    console.print(table)

    # Print summary
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
    console.print(
        "\n  [dim]Thresholds: "
        ">> >5% faster | OK <3% change | !! 3-10% slower | XX >10% slower[/dim]"
    )


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


@main.command()
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["markdown", "html", "both"]),
    default="both",
    help="Output format (default: both).",
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
    fmt: str,
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

    reports_dir = Path(output_dir) if output_dir else REPORTS_DIR
    generated: list[Path] = []

    if compare_versions:
        # --- Comparison report ---
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

        if fmt in ("markdown", "both"):
            md = generate_comparison_markdown(base_data, target_data, diffs)
            fname = f"{timestamp}_compare_{base_ver}_vs_{target_ver}.md"
            path = save_report(md, fname, reports_dir)
            generated.append(path)

        if fmt in ("html", "both"):
            html = generate_comparison_html(base_data, target_data, diffs)
            path = save_report(
                html, f"{timestamp}_compare_{base_ver}_vs_{target_ver}.html", reports_dir
            )
            generated.append(path)

    else:
        # --- Single run report ---
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
            result_file = result_files[0]  # Most recent

        result_data = load_results(result_file)
        mojo_ver = result_data["mojo_version"]
        timestamp = _report_timestamp()

        if fmt in ("markdown", "both"):
            md = generate_single_run_markdown(result_data)
            path = save_report(md, f"{timestamp}_mojo-{mojo_ver}.md", reports_dir)
            generated.append(path)

        if fmt in ("html", "both"):
            html = generate_single_run_html(result_data)
            path = save_report(html, f"{timestamp}_mojo-{mojo_ver}.html", reports_dir)
            generated.append(path)

    # Print summary
    console.print("[bold cyan]mojomark[/bold cyan] — Report generated")
    for path in generated:
        console.print(f"  [green]✓[/green] {path}")


def _report_timestamp() -> str:
    """Generate a timestamp string for report filenames."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")


# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------


@main.command()
def status():
    """Show current Mojo version, latest available, and stored baselines."""
    console.print("[bold cyan]mojomark[/bold cyan] — Status\n")

    # Machine info
    machine = get_machine_info()
    console.print(f"  Machine:  [bold]{format_machine_summary(machine)}[/bold]")

    # Installed version
    installed = get_mojo_version()
    if installed == "unknown":
        console.print("  Installed Mojo:  [red]not found[/red]")
    else:
        console.print(f"  Installed Mojo:  [bold]{installed}[/bold]")

    # Latest available
    with console.status("[dim]Checking latest version...[/dim]"):
        latest = get_latest_available_version()
    if latest:
        if installed != "unknown" and installed == latest:
            console.print(f"  Latest stable:   [green]{latest} (you're current)[/green]")
        else:
            console.print(f"  Latest stable:   [yellow]{latest}[/yellow]")
    else:
        console.print("  Latest stable:   [dim]could not check[/dim]")

    # Cached versions
    cached = list_cached_versions()
    if cached:
        console.print(f"\n  Cached installs:  {', '.join(cached)}")

    # Stored results
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

    # Upgrade hint
    if latest and installed != "unknown" and installed != latest:
        console.print(
            f"\n  [dim]Upgrade:[/dim] "
            f"pip install mojo=={latest} "
            f"--extra-index-url https://modular.gateway.scarf.sh/simple/"
        )
        console.print("  [dim]Then run:[/dim] mojomark run")


# ---------------------------------------------------------------------------
# Versions command
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

    # Display in rows of 5 with markers
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
# Regression command (run --compare)
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
        console.print(f"  [dim]{msg}[/dim]")

    mojo_binary = get_mojo_binary(version, on_progress=progress)

    # Verify the version matches
    actual = get_mojo_version(mojo_binary)
    console.print(f"  Mojo {actual} ready\n")

    results = []
    for name, bench_category, mojo_file in benchmarks:
        label = f"{bench_category}/{name}"
        with console.status(f"  [bold green]Running {label}...[/bold green]"):
            try:
                result = run_benchmark(
                    mojo_file=mojo_file,
                    name=name,
                    category=bench_category,
                    samples=samples,
                    warmup=warmup,
                    mojo_binary=mojo_binary,
                )
                results.append(result)
                console.print(f"    [green]✓[/green] {label:30s} {format_time(result.mean_ns)}")
            except RuntimeError as e:
                console.print(f"    [red]✗[/red] {label:30s} FAILED — {e}")

    return results


def _print_comparison_table(base_ver, target_ver, diffs):
    """Print a Rich comparison table and summary."""
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

    for d in diffs:
        if d.delta_pct <= -5:
            delta_str = f"[bold green]{d.delta_pct:+.1f}%[/bold green]"
        elif d.delta_pct < 3:
            delta_str = f"[green]{d.delta_pct:+.1f}%[/green]"
        elif d.delta_pct < 10:
            delta_str = f"[yellow]{d.delta_pct:+.1f}%[/yellow]"
        else:
            delta_str = f"[bold red]{d.delta_pct:+.1f}%[/bold red]"

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


@main.command()
@click.argument("base_version", metavar="BASE")
@click.argument("target_version", metavar="TARGET")
@click.option("--category", "-c", default=None, help="Run only benchmarks in this category.")
@click.option("--samples", "-s", default=10, help="Number of timed samples per benchmark.")
@click.option("--warmup", "-w", default=3, help="Number of warmup runs per benchmark.")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["markdown", "html", "both", "none"]),
    default="both",
    help="Report format (default: both).",
)
def regression(
    base_version: str,
    target_version: str,
    category: str | None,
    samples: int,
    warmup: int,
    fmt: str,
):
    """Run a full regression assessment between two Mojo versions.

    Installs both versions into isolated environments, benchmarks each,
    and compares results back-to-back on the same machine.

    Use the special aliases ``current`` (your installed version) and
    ``latest`` (newest release on the package index) instead of explicit
    version numbers.

    Examples:

        mojomark regression current latest

        mojomark regression 0.7.0 0.26.1

        mojomark regression 0.7.0 0.26.1 --category compute --samples 20
    """
    # Resolve aliases like "current" and "latest"
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

    console.print("[bold cyan]mojomark[/bold cyan] — Regression Assessment\n")
    console.print(f"  Machine:  {format_machine_summary(machine)}")
    console.print(f"  Base:     Mojo {base_version}")
    console.print(f"  Target:   Mojo {target_version}")
    console.print(f"  Samples:  {samples} | Warmup: {warmup}")
    console.print()

    benchmarks = discover_benchmarks(category=category)
    if not benchmarks:
        console.print("[yellow]No benchmarks found.[/yellow]")
        return

    console.print(f"  {len(benchmarks)} benchmark(s) to run\n")

    # --- Phase 1: Benchmark base version ---
    console.rule(f"[bold]Phase 1 — Mojo {base_version}[/bold]")
    try:
        base_results = _run_benchmarks_with_version(base_version, benchmarks, samples, warmup)
    except RuntimeError as e:
        console.print(f"\n[red]Failed to set up Mojo {base_version}:[/red] {e}")
        return

    if not base_results:
        console.print(f"[red]All benchmarks failed on Mojo {base_version}.[/red]")
        return

    base_path = save_results(base_results, base_version)
    console.print(f"\n  [dim]Saved → {base_path}[/dim]")

    # --- Phase 2: Benchmark target version ---
    console.print()
    console.rule(f"[bold]Phase 2 — Mojo {target_version}[/bold]")
    try:
        target_results = _run_benchmarks_with_version(target_version, benchmarks, samples, warmup)
    except RuntimeError as e:
        console.print(f"\n[red]Failed to set up Mojo {target_version}:[/red] {e}")
        return

    if not target_results:
        console.print(f"[red]All benchmarks failed on Mojo {target_version}.[/red]")
        return

    target_path = save_results(target_results, target_version)
    console.print(f"\n  [dim]Saved → {target_path}[/dim]")

    # --- Phase 3: Compare ---
    console.print()
    console.rule("[bold]Regression Report[/bold]")

    base_data = load_results(base_path)
    target_data = load_results(target_path)

    diffs = compare_results(base_data, target_data)
    if not diffs:
        console.print("[yellow]No matching benchmarks to compare.[/yellow]")
        return

    _print_comparison_table(base_version, target_version, diffs)

    # --- Phase 4: Generate reports ---
    if fmt != "none":
        from mojomark.report import REPORTS_DIR

        timestamp = _report_timestamp()
        generated = []

        if fmt in ("markdown", "both"):
            md = generate_comparison_markdown(base_data, target_data, diffs)
            fname = f"{timestamp}_regression_{base_version}_vs_{target_version}.md"
            path = save_report(md, fname, REPORTS_DIR)
            generated.append(path)

        if fmt in ("html", "both"):
            html = generate_comparison_html(base_data, target_data, diffs)
            fname = f"{timestamp}_regression_{base_version}_vs_{target_version}.html"
            path = save_report(html, fname, REPORTS_DIR)
            generated.append(path)

        console.print()
        for path in generated:
            console.print(f"  [green]✓[/green] {path}")


# ---------------------------------------------------------------------------
# Clean command
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
