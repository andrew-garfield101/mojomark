"""mojomark — Mojo Performance Regression Detector."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mojomark")
except PackageNotFoundError:
    __version__ = "0.1.0"
