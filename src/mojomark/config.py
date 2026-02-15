"""Configuration management — load and merge mojomark settings.

Loads settings from ``mojomark.toml`` with the following precedence:

    CLI flags  >  mojomark.toml  >  built-in defaults

The config file is discovered by walking up from the current working
directory, similar to how Git finds ``.git``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

log = logging.getLogger(__name__)

CONFIG_FILENAME = "mojomark.toml"

DEFAULT_CONFIG_TEMPLATE = """\
# mojomark configuration
# https://github.com/andrew-garfield101/mojomark

[benchmark]
samples = 10
warmup = 3

[thresholds]
# Percentage change boundaries for regression classification.
# Positive = slower, negative = faster.
stable = 3.0       # |delta| < stable  →  OK
warning = 10.0     # delta >= warning   →  XX REGRESSION
improved = -5.0    # delta <= improved  →  >> improved

[report]
format = "both"    # markdown | html | both | none
# output_dir = "reports"
"""


@dataclass
class MojomarkConfig:
    """Merged configuration from defaults, file, and CLI overrides."""

    samples: int = 10
    warmup: int = 3
    threshold_stable: float = 3.0
    threshold_warning: float = 10.0
    threshold_improved: float = -5.0
    report_format: str = "both"
    report_output_dir: str | None = None
    config_path: Path | None = field(default=None, repr=False)


def find_config_file(start: Path | None = None) -> Path | None:
    """Walk up from *start* looking for ``mojomark.toml``.

    Args:
        start: Directory to begin searching from (defaults to cwd).

    Returns:
        Path to the config file, or None if not found.
    """
    directory = (start or Path.cwd()).resolve()

    for parent in [directory, *directory.parents]:
        candidate = parent / CONFIG_FILENAME
        if candidate.is_file():
            return candidate

    return None


def _load_toml(path: Path) -> dict:
    """Parse a TOML file and return the raw dict."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_config(config_path: Path | None = None) -> MojomarkConfig:
    """Load configuration from a TOML file.

    Args:
        config_path: Explicit path to a config file. If None,
            searches for ``mojomark.toml`` by walking up from cwd.

    Returns:
        A fully populated MojomarkConfig.
    """
    cfg = MojomarkConfig()

    path = config_path or find_config_file()
    if path is None:
        return cfg

    log.debug("Loading config from %s", path)

    try:
        data = _load_toml(path)
    except Exception as e:
        log.warning("Failed to parse %s: %s", path, e)
        return cfg

    cfg.config_path = path

    benchmark = data.get("benchmark", {})
    if "samples" in benchmark:
        cfg.samples = int(benchmark["samples"])
    if "warmup" in benchmark:
        cfg.warmup = int(benchmark["warmup"])

    thresholds = data.get("thresholds", {})
    if "stable" in thresholds:
        cfg.threshold_stable = float(thresholds["stable"])
    if "warning" in thresholds:
        cfg.threshold_warning = float(thresholds["warning"])
    if "improved" in thresholds:
        cfg.threshold_improved = float(thresholds["improved"])

    report = data.get("report", {})
    if "format" in report:
        cfg.report_format = str(report["format"])
    if "output_dir" in report:
        cfg.report_output_dir = str(report["output_dir"])

    return cfg


def merge_cli_overrides(
    cfg: MojomarkConfig,
    *,
    samples: int | None = None,
    warmup: int | None = None,
    fmt: str | None = None,
    output_dir: str | None = None,
    threshold_stable: float | None = None,
    threshold_warning: float | None = None,
    threshold_improved: float | None = None,
) -> MojomarkConfig:
    """Apply CLI flag overrides on top of a loaded config.

    Only non-None values override the config. This preserves the
    precedence chain: CLI flags > config file > defaults.

    Returns:
        The same config object, mutated in place.
    """
    if samples is not None:
        cfg.samples = samples
    if warmup is not None:
        cfg.warmup = warmup
    if fmt is not None:
        cfg.report_format = fmt
    if output_dir is not None:
        cfg.report_output_dir = output_dir
    if threshold_stable is not None:
        cfg.threshold_stable = threshold_stable
    if threshold_warning is not None:
        cfg.threshold_warning = threshold_warning
    if threshold_improved is not None:
        cfg.threshold_improved = threshold_improved
    return cfg
