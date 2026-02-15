"""Version manager — install and manage Mojo versions in isolated environments."""

from __future__ import annotations

import subprocess
import venv
from pathlib import Path

MOJOMARK_CACHE = Path.home() / ".mojomark"
VENVS_DIR = MOJOMARK_CACHE / "venvs"
MOJO_INDEX_URL = "https://modular.gateway.scarf.sh/simple/"
PYPI_JSON_URL = "https://pypi.org/pypi/mojo/json"


# -- Version helpers --------------------------------------------------------


def _version_key(version_str: str) -> tuple[int, ...]:
    """Create a sortable tuple from a version string like ``'0.7.0'``."""
    parts: list[int] = []
    for part in version_str.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def get_cache_dir() -> Path:
    """Return the mojomark cache directory, creating it if needed."""
    MOJOMARK_CACHE.mkdir(parents=True, exist_ok=True)
    return MOJOMARK_CACHE


def _venv_dir(version: str) -> Path:
    """Return the venv directory path for a given Mojo version."""
    return VENVS_DIR / f"mojo-{version}"


def _find_mojo_in_venv(venv_path: Path) -> Path | None:
    """Locate the mojo binary inside a venv."""
    # Unix: venv/bin/mojo
    bin_path = venv_path / "bin" / "mojo"
    if bin_path.exists():
        return bin_path
    # Windows: venv/Scripts/mojo.exe
    scripts_path = venv_path / "Scripts" / "mojo.exe"
    if scripts_path.exists():
        return scripts_path
    return None


def is_version_installed(version: str) -> bool:
    """Check if a Mojo version is already cached in a local venv."""
    venv_path = _venv_dir(version)
    if not venv_path.exists():
        return False
    return _find_mojo_in_venv(venv_path) is not None


def install_mojo_version(version: str, on_progress=None) -> Path:
    """Install a specific Mojo version into an isolated venv.

    Args:
        version: Mojo version string (e.g. "0.7.0", "0.26.1").
        on_progress: Optional callback(message: str) for status updates.

    Returns:
        Path to the mojo binary inside the venv.

    Raises:
        RuntimeError: If installation fails.
    """
    venv_path = _venv_dir(version)

    existing = _find_mojo_in_venv(venv_path) if venv_path.exists() else None
    if existing:
        if on_progress:
            on_progress(f"Mojo {version} already cached")
        return existing

    if on_progress:
        on_progress(f"Creating isolated environment for Mojo {version}...")

    venv_path.parent.mkdir(parents=True, exist_ok=True)
    venv.create(str(venv_path), with_pip=True, clear=True)

    pip_path = venv_path / "bin" / "pip"
    if not pip_path.exists():
        pip_path = venv_path / "Scripts" / "pip.exe"

    if on_progress:
        on_progress(f"Installing Mojo {version}...")

    result = subprocess.run(
        [
            str(pip_path),
            "install",
            f"mojo=={version}",
            "--extra-index-url",
            MOJO_INDEX_URL,
            "--quiet",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        import shutil

        shutil.rmtree(venv_path, ignore_errors=True)

        hint = ""
        available = list_available_versions()
        if available:
            if version in available:
                hint = (
                    f"\nNote: version {version} is listed on PyPI but "
                    "failed to install (may not support your platform)."
                )
            else:
                closest = suggest_closest_versions(version, available)
                hint = (
                    f"\nVersion {version} was not found. "
                    f"Closest available: {', '.join(closest)}"
                    "\nRun 'mojomark versions' to see all releases."
                )

        raise RuntimeError(f"Failed to install Mojo {version}:\n{result.stderr.strip()}{hint}")

    mojo_binary = _find_mojo_in_venv(venv_path)
    if mojo_binary is None:
        raise RuntimeError(f"Mojo {version} installed but binary not found in {venv_path}")

    if on_progress:
        on_progress(f"Mojo {version} ready")

    return mojo_binary


def _system_mojo_matches(version: str) -> Path | None:
    """Check if the system-installed ``mojo`` matches *version*.

    Returns the path to the system binary if it matches, otherwise *None*.
    This lets us use pre-installed Mojo versions (e.g. from the old
    ``modular install`` flow) that aren't available on the pip index.
    """
    import shutil

    mojo_path = shutil.which("mojo")
    if mojo_path is None:
        return None

    from mojomark.runner import get_mojo_version

    system_version = get_mojo_version()
    if system_version == version:
        return Path(mojo_path)
    return None


def get_mojo_binary(version: str, on_progress=None) -> Path:
    """Get the path to a Mojo binary for a given version, installing if needed.

    Resolution order:
      1. Already cached in ``~/.mojomark/venvs/`` — instant.
      2. System ``mojo`` on PATH matches the requested version — use it directly.
      3. Install from the pip package index into an isolated venv.

    Args:
        version: Mojo version string.
        on_progress: Optional callback(message: str) for status updates.

    Returns:
        Path to the mojo binary.
    """
    venv_path = _venv_dir(version)
    existing = _find_mojo_in_venv(venv_path) if venv_path.exists() else None
    if existing:
        if on_progress:
            on_progress(f"Mojo {version} already cached")
        return existing

    system_binary = _system_mojo_matches(version)
    if system_binary is not None:
        if on_progress:
            on_progress(f"Using system Mojo {version} ({system_binary})")
        return system_binary

    return install_mojo_version(version, on_progress=on_progress)


def get_latest_available_version() -> str | None:
    """Check PyPI for the latest available Mojo version.

    Returns:
        Version string, or None if the check fails.
    """
    try:
        import json
        import urllib.request

        req = urllib.request.Request(
            PYPI_JSON_URL,
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("info", {}).get("version")
    except Exception:
        return None


def list_available_versions() -> list[str] | None:
    """Fetch all published Mojo versions from PyPI.

    Returns:
        List of version strings sorted newest-first, or *None* on failure.
    """
    try:
        import json
        import urllib.request

        req = urllib.request.Request(
            PYPI_JSON_URL,
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            releases = data.get("releases", {})
            versions = [v for v, files in releases.items() if files]
            return sorted(versions, key=_version_key, reverse=True)
    except Exception:
        return None


def suggest_closest_versions(
    target: str,
    available: list[str],
    n: int = 5,
) -> list[str]:
    """Return the *n* versions from *available* closest to *target*.

    Closeness is measured by numerical distance between version tuples.
    """
    target_key = _version_key(target)

    def distance(v: str) -> float:
        vk = _version_key(v)
        max_len = max(len(target_key), len(vk))
        a = target_key + (0,) * (max_len - len(target_key))
        b = vk + (0,) * (max_len - len(vk))
        return sum(abs(x - y) for x, y in zip(a, b))

    ranked = sorted(available, key=distance)
    return ranked[:n]


def resolve_version_alias(alias: str) -> str:
    """Resolve the special aliases ``current`` and ``latest``.

    Returns:
        A concrete version string.

    Raises:
        RuntimeError: If the alias cannot be resolved.
    """
    lower = alias.lower()

    if lower == "current":
        from mojomark.runner import get_mojo_version

        version = get_mojo_version()
        if version == "unknown":
            raise RuntimeError(
                "Could not detect an installed Mojo version. Make sure 'mojo' is on your PATH."
            )
        return version

    if lower == "latest":
        latest = get_latest_available_version()
        if latest is None:
            raise RuntimeError(
                "Could not determine the latest Mojo version. Check your network connection."
            )
        return latest

    return alias


def list_cached_versions() -> list[str]:
    """List all Mojo versions currently cached in local venvs.

    Returns:
        Sorted list of version strings.
    """
    if not VENVS_DIR.exists():
        return []

    versions = []
    for path in VENVS_DIR.iterdir():
        if path.is_dir() and path.name.startswith("mojo-"):
            version = path.name.removeprefix("mojo-")
            if _find_mojo_in_venv(path):
                versions.append(version)

    return sorted(versions)


def clean_cache() -> list[str]:
    """Remove all cached Mojo venvs.

    Returns:
        List of version strings that were removed.
    """
    import shutil

    versions = list_cached_versions()
    if VENVS_DIR.exists():
        shutil.rmtree(VENVS_DIR)
    return versions
