"""Tests for mojomark version manager."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mojomark.versions import (
    _system_mojo_matches,
    _venv_dir,
    _version_key,
    is_version_installed,
    list_cached_versions,
    resolve_version_alias,
    suggest_closest_versions,
)

# ---------------------------------------------------------------------------
# _version_key — sorting helper
# ---------------------------------------------------------------------------


class TestVersionKey:
    def test_simple_version(self):
        assert _version_key("0.7.0") == (0, 7, 0)

    def test_four_part_version(self):
        assert _version_key("0.26.1.0") == (0, 26, 1, 0)

    def test_sorting_order(self):
        versions = ["0.7.0", "0.26.1.0", "24.6.0", "0.8.0"]
        result = sorted(versions, key=_version_key)
        assert result == ["0.7.0", "0.8.0", "0.26.1.0", "24.6.0"]

    def test_non_numeric_part(self):
        # Gracefully handles non-numeric parts
        assert _version_key("1.2.beta") == (1, 2, 0)


# ---------------------------------------------------------------------------
# suggest_closest_versions
# ---------------------------------------------------------------------------


class TestSuggestClosestVersions:
    def test_finds_closest(self):
        available = ["0.5.0", "0.6.0", "0.7.0", "0.8.0", "0.26.1", "24.6.0"]
        result = suggest_closest_versions("0.7.1", available, n=3)
        assert result[0] == "0.7.0"  # closest
        assert len(result) == 3

    def test_exact_match_is_first(self):
        available = ["0.5.0", "0.7.0", "0.8.0"]
        result = suggest_closest_versions("0.7.0", available, n=3)
        assert result[0] == "0.7.0"

    def test_n_larger_than_available(self):
        available = ["0.7.0", "0.8.0"]
        result = suggest_closest_versions("0.7.0", available, n=5)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# resolve_version_alias
# ---------------------------------------------------------------------------


class TestResolveVersionAlias:
    def test_passthrough_normal_version(self):
        assert resolve_version_alias("0.7.0") == "0.7.0"

    def test_current_alias(self):
        with patch("mojomark.runner.get_mojo_version", return_value="0.7.0"):
            assert resolve_version_alias("current") == "0.7.0"

    def test_current_alias_case_insensitive(self):
        with patch("mojomark.runner.get_mojo_version", return_value="0.7.0"):
            assert resolve_version_alias("Current") == "0.7.0"

    def test_current_alias_fails_when_mojo_missing(self):
        with patch("mojomark.runner.get_mojo_version", return_value="unknown"):
            with pytest.raises(RuntimeError, match="Could not detect"):
                resolve_version_alias("current")

    def test_latest_alias(self):
        with patch(
            "mojomark.versions.get_latest_available_version",
            return_value="0.26.1.0",
        ):
            assert resolve_version_alias("latest") == "0.26.1.0"

    def test_latest_alias_fails_on_network_error(self):
        with patch(
            "mojomark.versions.get_latest_available_version",
            return_value=None,
        ):
            with pytest.raises(RuntimeError, match="Could not determine"):
                resolve_version_alias("latest")


# ---------------------------------------------------------------------------
# _system_mojo_matches — use local mojo when version matches
# ---------------------------------------------------------------------------


class TestSystemMojoMatches:
    def test_returns_path_when_version_matches(self):
        with patch("shutil.which", return_value="/usr/local/bin/mojo"):
            with patch("mojomark.runner.get_mojo_version", return_value="0.7.0"):
                result = _system_mojo_matches("0.7.0")
                assert result == Path("/usr/local/bin/mojo")

    def test_returns_none_when_version_differs(self):
        with patch("shutil.which", return_value="/usr/local/bin/mojo"):
            with patch("mojomark.runner.get_mojo_version", return_value="0.7.0"):
                assert _system_mojo_matches("0.26.1.0") is None

    def test_returns_none_when_mojo_not_on_path(self):
        with patch("shutil.which", return_value=None):
            assert _system_mojo_matches("0.7.0") is None


# ---------------------------------------------------------------------------
# _venv_dir
# ---------------------------------------------------------------------------


class TestVenvDir:
    def test_path_includes_version(self):
        path = _venv_dir("0.8.0")
        assert "mojo-0.8.0" in str(path)


# ---------------------------------------------------------------------------
# is_version_installed
# ---------------------------------------------------------------------------


class TestIsVersionInstalled:
    def test_nonexistent_version(self):
        with patch("mojomark.versions.VENVS_DIR", Path("/nonexistent/venvs")):
            assert is_version_installed("99.99.99") is False


# ---------------------------------------------------------------------------
# list_cached_versions
# ---------------------------------------------------------------------------


class TestListCachedVersions:
    def test_empty_cache(self):
        with patch("mojomark.versions.VENVS_DIR", Path("/nonexistent/venvs")):
            assert list_cached_versions() == []

    def test_finds_cached_versions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            venvs = Path(tmpdir)
            # Create a fake cached venv with a mojo binary
            mojo_dir = venvs / "mojo-0.8.0" / "bin"
            mojo_dir.mkdir(parents=True)
            (mojo_dir / "mojo").write_text("fake")

            with patch("mojomark.versions.VENVS_DIR", venvs):
                versions = list_cached_versions()
                assert "0.8.0" in versions
