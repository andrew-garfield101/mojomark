"""Tests for mojomark CLI commands and UX features."""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from mojomark.cli import main

# ---------------------------------------------------------------------------
# Verbosity flags
# ---------------------------------------------------------------------------


class TestVerbosityFlags:
    def test_quiet_flag_accepted(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--quiet", "--help"])
        assert result.exit_code == 0

    def test_verbose_flag_accepted(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--verbose", "--help"])
        assert result.exit_code == 0

    def test_version_flag(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "mojomark" in result.output.lower() or "version" in result.output.lower()


# ---------------------------------------------------------------------------
# init command
# ---------------------------------------------------------------------------


class TestInitCommand:
    def test_creates_config_file(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert "Created" in result.output
            assert Path("mojomark.toml").exists()

    def test_refuses_overwrite_without_force(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("mojomark.toml").write_text("existing")
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert "already exists" in result.output

    def test_force_overwrites(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("mojomark.toml").write_text("old content")
            result = runner.invoke(main, ["init", "--force"])
            assert result.exit_code == 0
            assert "Created" in result.output
            content = Path("mojomark.toml").read_text()
            assert "[benchmark]" in content


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------


class TestListCommand:
    def test_lists_benchmarks(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "Available Benchmarks" in result.output

    def test_category_filter(self):
        runner = CliRunner()
        result = runner.invoke(main, ["list", "--category", "compute"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# history command
# ---------------------------------------------------------------------------


class TestHistoryCommand:
    def test_shows_message_when_no_results(self, tmp_path):
        runner = CliRunner()
        with patch("mojomark.cli.list_result_files", return_value=[]):
            result = runner.invoke(main, ["history"])
            assert result.exit_code == 0
            assert "No stored results" in result.output


# ---------------------------------------------------------------------------
# doctor command
# ---------------------------------------------------------------------------


class TestDoctorCommand:
    def test_runs_all_checks(self):
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0
        assert "Python" in result.output
        assert "Benchmarks" in result.output
        assert "Results dir" in result.output

    def test_shows_completion_tip(self):
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "completion" in result.output.lower()

    def test_checks_mojo(self):
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "Mojo" in result.output


# ---------------------------------------------------------------------------
# compare command — exit codes
# ---------------------------------------------------------------------------


class TestCompareExitCode:
    def _make_result_data(self, version, benchmarks):
        return {
            "mojo_version": version,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "benchmarks": [
                {
                    "name": name,
                    "category": cat,
                    "samples_ns": [],
                    "stats": {
                        "mean_ns": mean,
                        "median_ns": mean,
                        "min_ns": mean,
                        "max_ns": mean,
                        "std_dev_ns": 0,
                        "samples": 1,
                    },
                }
                for name, cat, mean in benchmarks
            ],
        }

    def test_exits_0_when_no_regressions(self, tmp_path):
        base_data = self._make_result_data("0.7.0", [("fib", "compute", 100)])
        target_data = self._make_result_data("0.8.0", [("fib", "compute", 99)])

        base_file = tmp_path / "base.json"
        target_file = tmp_path / "target.json"

        import json

        base_file.write_text(json.dumps(base_data))
        target_file.write_text(json.dumps(target_data))

        runner = CliRunner()
        with (
            patch("mojomark.cli.find_results_for_version") as mock_find,
            patch("mojomark.cli.load_results") as mock_load,
        ):
            mock_find.side_effect = lambda v: base_file if v == "0.7.0" else target_file
            mock_load.side_effect = lambda f: base_data if f == base_file else target_data

            result = runner.invoke(main, ["compare", "0.7.0", "0.8.0"])
            assert result.exit_code == 0
            assert "PASS" in result.output

    def test_exits_1_when_regressions_detected(self, tmp_path):
        base_data = self._make_result_data("0.7.0", [("fib", "compute", 100)])
        target_data = self._make_result_data("0.8.0", [("fib", "compute", 200)])

        base_file = tmp_path / "base.json"
        target_file = tmp_path / "target.json"

        import json

        base_file.write_text(json.dumps(base_data))
        target_file.write_text(json.dumps(target_data))

        runner = CliRunner()
        with (
            patch("mojomark.cli.find_results_for_version") as mock_find,
            patch("mojomark.cli.load_results") as mock_load,
        ):
            mock_find.side_effect = lambda v: base_file if v == "0.7.0" else target_file
            mock_load.side_effect = lambda f: base_data if f == base_file else target_data

            result = runner.invoke(main, ["compare", "0.7.0", "0.8.0"])
            assert result.exit_code == 1
            assert "FAIL" in result.output
