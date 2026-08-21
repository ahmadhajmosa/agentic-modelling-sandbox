"""Agentic Modeling Sandbox (AMS)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("agentic-modeling-sandbox")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0.dev0"
