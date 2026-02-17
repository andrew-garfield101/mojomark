"""Tests for the configuration management system."""

import tempfile
from pathlib import Path

from mojomark.config import (
    CONFIG_FILENAME,
    DEFAULT_CONFIG_TEMPLATE,
    MojomarkConfig,
    find_config_file,
    load_config,
    merge_cli_overrides,
)

# ---------------------------------------------------------------------------
# MojomarkConfig defaults
# ---------------------------------------------------------------------------


class TestMojomarkConfigDefaults:
    def test_default_samples(self):
        cfg = MojomarkConfig()
        assert cfg.samples == 10

    def test_default_warmup(self):
        cfg = MojomarkConfig()
        assert cfg.warmup == 3

    def test_default_thresholds(self):
        cfg = MojomarkConfig()
        assert cfg.threshold_stable == 3.0
        assert cfg.threshold_warning == 10.0
        assert cfg.threshold_improved == -5.0

    def test_default_report_format(self):
        cfg = MojomarkConfig()
        assert cfg.report_format == "both"

    def test_default_output_dir_is_none(self):
        cfg = MojomarkConfig()
        assert cfg.report_output_dir is None

    def test_default_config_path_is_none(self):
        cfg = MojomarkConfig()
        assert cfg.config_path is None


# ---------------------------------------------------------------------------
# find_config_file
# ---------------------------------------------------------------------------


class TestFindConfigFile:
    def test_finds_config_in_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir).resolve() / CONFIG_FILENAME
            config_path.write_text("[benchmark]\nsamples = 5\n")
            result = find_config_file(Path(tmpdir))
            assert result == config_path

    def test_finds_config_in_parent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir).resolve() / CONFIG_FILENAME
            config_path.write_text("[benchmark]\nsamples = 5\n")

            child = Path(tmpdir) / "subdir"
            child.mkdir()

            result = find_config_file(child)
            assert result == config_path

    def test_finds_config_in_grandparent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir).resolve() / CONFIG_FILENAME
            config_path.write_text("[benchmark]\nsamples = 5\n")

            grandchild = Path(tmpdir) / "a" / "b"
            grandchild.mkdir(parents=True)

            result = find_config_file(grandchild)
            assert result == config_path

    def test_returns_none_when_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_config_file(Path(tmpdir))
            assert result is None


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = load_config(config_path=Path(tmpdir) / "nonexistent.toml")
            assert cfg.samples == 10
            assert cfg.warmup == 3
            assert cfg.config_path is None

    def test_loads_benchmark_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / CONFIG_FILENAME
            config_path.write_text("[benchmark]\nsamples = 25\nwarmup = 8\n")
            cfg = load_config(config_path=config_path)
            assert cfg.samples == 25
            assert cfg.warmup == 8

    def test_loads_threshold_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / CONFIG_FILENAME
            config_path.write_text("[thresholds]\nstable = 5.0\nwarning = 15.0\nimproved = -8.0\n")
            cfg = load_config(config_path=config_path)
            assert cfg.threshold_stable == 5.0
            assert cfg.threshold_warning == 15.0
            assert cfg.threshold_improved == -8.0

    def test_loads_report_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / CONFIG_FILENAME
            config_path.write_text('[report]\nformat = "html"\noutput_dir = "./out"\n')
            cfg = load_config(config_path=config_path)
            assert cfg.report_format == "html"
            assert cfg.report_output_dir == "./out"

    def test_partial_config_preserves_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / CONFIG_FILENAME
            config_path.write_text("[benchmark]\nsamples = 50\n")
            cfg = load_config(config_path=config_path)
            assert cfg.samples == 50
            assert cfg.warmup == 3
            assert cfg.threshold_stable == 3.0
            assert cfg.report_format == "both"

    def test_records_config_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / CONFIG_FILENAME
            config_path.write_text("[benchmark]\nsamples = 5\n")
            cfg = load_config(config_path=config_path)
            assert cfg.config_path == config_path

    def test_handles_malformed_toml_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / CONFIG_FILENAME
            config_path.write_text("this is [not valid toml {{{{")
            cfg = load_config(config_path=config_path)
            assert cfg.samples == 10

    def test_default_template_is_valid_toml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / CONFIG_FILENAME
            config_path.write_text(DEFAULT_CONFIG_TEMPLATE)
            cfg = load_config(config_path=config_path)
            assert cfg.samples == 10
            assert cfg.warmup == 3
            assert cfg.threshold_stable == 3.0
            assert cfg.threshold_warning == 10.0
            assert cfg.threshold_improved == -5.0
            assert cfg.report_format == "both"

    def test_empty_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / CONFIG_FILENAME
            config_path.write_text("")
            cfg = load_config(config_path=config_path)
            assert cfg.samples == 10


# ---------------------------------------------------------------------------
# merge_cli_overrides
# ---------------------------------------------------------------------------


class TestMergeCliOverrides:
    def test_none_values_preserve_config(self):
        cfg = MojomarkConfig(samples=25, warmup=8)
        merge_cli_overrides(cfg, samples=None, warmup=None)
        assert cfg.samples == 25
        assert cfg.warmup == 8

    def test_explicit_values_override(self):
        cfg = MojomarkConfig(samples=25, warmup=8)
        merge_cli_overrides(cfg, samples=50, warmup=1)
        assert cfg.samples == 50
        assert cfg.warmup == 1

    def test_partial_override(self):
        cfg = MojomarkConfig(samples=25, warmup=8)
        merge_cli_overrides(cfg, samples=50)
        assert cfg.samples == 50
        assert cfg.warmup == 8

    def test_threshold_overrides(self):
        cfg = MojomarkConfig()
        merge_cli_overrides(cfg, threshold_stable=1.0, threshold_warning=5.0)
        assert cfg.threshold_stable == 1.0
        assert cfg.threshold_warning == 5.0
        assert cfg.threshold_improved == -5.0

    def test_format_override(self):
        cfg = MojomarkConfig(report_format="both")
        merge_cli_overrides(cfg, fmt="html")
        assert cfg.report_format == "html"

    def test_output_dir_override(self):
        cfg = MojomarkConfig()
        merge_cli_overrides(cfg, output_dir="/tmp/reports")
        assert cfg.report_output_dir == "/tmp/reports"

    def test_returns_same_object(self):
        cfg = MojomarkConfig()
        result = merge_cli_overrides(cfg, samples=99)
        assert result is cfg

    def test_full_precedence_chain(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / CONFIG_FILENAME
            config_path.write_text("[benchmark]\nsamples = 25\nwarmup = 8\n")

            cfg = load_config(config_path=config_path)
            assert cfg.samples == 25
            assert cfg.warmup == 8

            merge_cli_overrides(cfg, samples=99)
            assert cfg.samples == 99
            assert cfg.warmup == 8


# ---------------------------------------------------------------------------
# User benchmarks dir
# ---------------------------------------------------------------------------


class TestUserBenchmarksDir:
    def test_default_is_none(self):
        cfg = MojomarkConfig()
        assert cfg.user_benchmarks_dir is None

    def test_loads_from_toml(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / CONFIG_FILENAME
            config_path.write_text('[benchmarks]\nuser_dir = "my_benches"\n')
            cfg = load_config(config_path=config_path)
            assert cfg.user_benchmarks_dir == "my_benches"

    def test_absent_section_keeps_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / CONFIG_FILENAME
            config_path.write_text("[benchmark]\nsamples = 5\n")
            cfg = load_config(config_path=config_path)
            assert cfg.user_benchmarks_dir is None
