"""Machine fingerprint — capture system info to tag benchmark results."""

import hashlib
import os
import platform
import subprocess


def get_cpu_name() -> str:
    """Get a human-readable CPU model name."""
    system = platform.system()

    if system == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    if system == "Linux":
        try:
            result = subprocess.run(
                ["lscpu"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith("Model name:"):
                        return line.split(":", 1)[1].strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    return platform.processor() or "unknown"


def get_ram_gb() -> float:
    """Get total system RAM in gigabytes."""
    system = platform.system()

    if system == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return int(result.stdout.strip()) / (1024**3)
        except (subprocess.SubprocessError, FileNotFoundError, ValueError):
            pass

    if system == "Linux":
        try:
            result = subprocess.run(
                ["free", "-b"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith("Mem:"):
                        return int(line.split()[1]) / (1024**3)
        except (subprocess.SubprocessError, FileNotFoundError, ValueError):
            pass

    return 0.0


def get_machine_info() -> dict:
    """Capture a machine fingerprint for benchmark result context.

    Returns:
        Dict with cpu, cores, ram_gb, os, arch, and a hostname_hash
        for identifying the same machine across runs without leaking
        the actual hostname.
    """
    hostname = platform.node()
    hostname_hash = hashlib.sha256(hostname.encode()).hexdigest()[:12]

    return {
        "cpu": get_cpu_name(),
        "cores": os.cpu_count() or 0,
        "ram_gb": round(get_ram_gb(), 1),
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "hostname_hash": hostname_hash,
    }


def format_machine_summary(info: dict) -> str:
    """Format machine info into a single-line summary for CLI output.

    Args:
        info: Machine info dict from get_machine_info().

    Returns:
        Human-readable summary string.
    """
    return (
        f"{info['cpu']}, {info['cores']} cores, "
        f"{info['ram_gb']}GB RAM, {info['os']} ({info['arch']})"
    )


def machines_match(a: dict, b: dict) -> bool:
    """Check if two machine fingerprints represent the same machine.

    Compares hostname_hash, cpu, and cores. RAM and OS version can
    change between runs on the same machine, so we don't require
    exact match on those.

    Args:
        a: First machine info dict.
        b: Second machine info dict.

    Returns:
        True if the fingerprints likely represent the same machine.
    """
    return (
        a.get("hostname_hash") == b.get("hostname_hash")
        and a.get("cpu") == b.get("cpu")
        and a.get("cores") == b.get("cores")
    )
