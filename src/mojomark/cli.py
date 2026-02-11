"""mojomark CLI — Mojo Performance Regression Detector."""

import click
from rich.console import Console
from rich.table import Table

from mojomark.runner import discover_benchmarks, get_mojo_version, run_benchmark
from mojomark.storage import save_results

console = Console()


def format_time(ns: float) -> str:
    """Format nanoseconds into a human-readable string."""
    if ns < 1_000:
        return f"{ns:.0f} ns"
    elif ns < 1_000_000:
        return f"{ns / 1_000:.1f} us"
    elif ns < 1_000_000_000:
        return f"{ns / 1_000_000:.1f} ms"
    else:
        return f"{ns / 1_000_000_000:.2f} s"


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
    console.print(
        f"[bold cyan]mojomark[/bold cyan] — Mojo Performance Regression Detector"
    )
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
