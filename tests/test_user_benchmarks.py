"""Tests for custom user benchmark features."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from mojomark.cli import main
from mojomark.codegen import (
    SCAFFOLD_TEMPLATE,
    discover_templates,
    validate_template,
)

# ---------------------------------------------------------------------------
# validate_template
# ---------------------------------------------------------------------------


class TestValidateTemplate:
    def test_valid_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.mojo"
            path.write_text(
                '"""Test"""\n# ==MODULE==\n# ==SETUP==\n# ==WORKLOAD==\nvar x = 1\n# KEEP: x int\n'
            )
            errors = validate_template(path)
            assert errors == []

    def test_missing_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.mojo"
            path.write_text("# ==MODULE==\n# ==SETUP==\nvar x = 1\n# KEEP: x int\n")
            errors = validate_template(path)
            assert any("WORKLOAD" in e for e in errors)

    def test_missing_keep(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.mojo"
            path.write_text("# ==WORKLOAD==\nvar x = 1\n")
            errors = validate_template(path)
            assert any("KEEP" in e for e in errors)

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.mojo"
            path.write_text("")
            errors = validate_template(path)
            assert any("empty" in e.lower() for e in errors)

    def test_nonexistent_file(self):
        errors = validate_template(Path("/nonexistent/test.mojo"))
        assert any("not found" in e.lower() for e in errors)

    def test_wrong_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.py"
            path.write_text("# ==WORKLOAD==\nvar x = 1\n# KEEP: x int\n")
            errors = validate_template(path)
            assert any(".mojo" in e for e in errors)

    def test_empty_workload_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.mojo"
            path.write_text("# ==WORKLOAD==\n\n\n# KEEP: x int\n")
            errors = validate_template(path)
            assert any("WORKLOAD" in e for e in errors)


# ---------------------------------------------------------------------------
# discover_templates with extra_dirs
# ---------------------------------------------------------------------------


class TestDiscoverWithUserDirs:
    def test_merges_builtin_and_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            builtin = Path(tmp) / "builtin"
            user = Path(tmp) / "user"

            (builtin / "compute").mkdir(parents=True)
            (user / "custom").mkdir(parents=True)

            (builtin / "compute" / "fib.mojo").write_text("fn main(): pass")
            (user / "custom" / "my_test.mojo").write_text("fn main(): pass")

            result = discover_templates(builtin, extra_dirs=[user])
            names = {r[0] for r in result}
            assert "fib" in names
            assert "my_test" in names

    def test_user_overrides_builtin(self):
        with tempfile.TemporaryDirectory() as tmp:
            builtin = Path(tmp) / "builtin"
            user = Path(tmp) / "user"

            (builtin / "compute").mkdir(parents=True)
            (user / "compute").mkdir(parents=True)

            (builtin / "compute" / "fib.mojo").write_text("builtin version")
            (user / "compute" / "fib.mojo").write_text("user version")

            result = discover_templates(builtin, extra_dirs=[user])
            fib_entries = [r for r in result if r[0] == "fib"]
            assert len(fib_entries) == 1
            assert fib_entries[0][2].read_text() == "user version"

    def test_empty_extra_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            builtin = Path(tmp) / "builtin"
            (builtin / "compute").mkdir(parents=True)
            (builtin / "compute" / "fib.mojo").write_text("fn main(): pass")

            result = discover_templates(builtin, extra_dirs=[])
            assert len(result) == 1

    def test_nonexistent_extra_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            builtin = Path(tmp) / "builtin"
            (builtin / "compute").mkdir(parents=True)
            (builtin / "compute" / "fib.mojo").write_text("fn main(): pass")

            result = discover_templates(builtin, extra_dirs=[Path("/nonexistent")])
            assert len(result) == 1


# ---------------------------------------------------------------------------
# scaffold template
# ---------------------------------------------------------------------------


class TestScaffoldTemplate:
    def test_scaffold_has_required_sections(self):
        content = SCAFFOLD_TEMPLATE.format(name="test", category="custom")
        assert "# ==MODULE==" in content
        assert "# ==SETUP==" in content
        assert "# ==WORKLOAD==" in content
        assert "# KEEP:" in content

    def test_scaffold_passes_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.mojo"
            content = SCAFFOLD_TEMPLATE.format(name="test", category="custom")
            path.write_text(content)
            errors = validate_template(path)
            assert errors == []


# ---------------------------------------------------------------------------
# CLI: add command
# ---------------------------------------------------------------------------


class TestAddCommand:
    def test_creates_template(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["add", "my_bench"])
            assert result.exit_code == 0
            assert "Created" in result.output
            assert Path("benchmarks/custom/my_bench.mojo").exists()

    def test_creates_with_category(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["add", "matrix_inv", "--category", "compute"])
            assert result.exit_code == 0
            assert Path("benchmarks/compute/matrix_inv.mojo").exists()

    def test_refuses_overwrite(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("benchmarks/custom").mkdir(parents=True)
            Path("benchmarks/custom/existing.mojo").write_text("existing")
            result = runner.invoke(main, ["add", "existing"])
            assert "already exists" in result.output

    def test_custom_directory(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["add", "test_bench", "--dir", "my_benches"])
            assert result.exit_code == 0
            assert Path("my_benches/custom/test_bench.mojo").exists()


# ---------------------------------------------------------------------------
# CLI: validate command
# ---------------------------------------------------------------------------


class TestValidateCommand:
    def test_valid_file(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.mojo").write_text("# ==WORKLOAD==\nvar x = 1\n# KEEP: x int\n")
            result = runner.invoke(main, ["validate", "test.mojo"])
            assert result.exit_code == 0
            assert "valid" in result.output.lower()

    def test_invalid_file(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("bad.mojo").write_text("just some code\n")
            result = runner.invoke(main, ["validate", "bad.mojo"])
            assert result.exit_code == 1
