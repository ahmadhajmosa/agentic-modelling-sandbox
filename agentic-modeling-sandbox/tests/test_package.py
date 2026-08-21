from importlib.metadata import version

import ams


def test_version_matches_installed_package_metadata():
    """__version__ must not drift from the version declared in pyproject.toml."""
    assert ams.__version__ == version("agentic-modeling-sandbox")
