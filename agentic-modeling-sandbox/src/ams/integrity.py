"""Environment-owned file integrity for subprocess execution.

An allowlisted interpreter (``python``) can write anywhere the AMS process can,
so ``allowed_write_paths`` cannot be *enforced* against a subprocess without OS
level isolation. This module makes such writes detectable and reversible: the
environment-owned files are snapshotted before execution, verified afterwards,
and restored if the subprocess changed them.

This covers environment-owned state inside the workspace (``environment.yaml``,
``tools/``, ``evals/``, ``.ams/``). Writes elsewhere on the host filesystem still
require an isolated backend (container/VM) to contain.
"""

from __future__ import annotations

from pathlib import Path

from .workspace import is_under_allowed_write_path


# Transient build/cache artifacts are produced by legitimate test runs and are
# not part of the environment's owned state.
EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    ".venv",
}


def protected_files(workspace: Path, allowed_roots: list[str]) -> list[Path]:
    """Every workspace file the agent is not permitted to write."""
    root = workspace.resolve()
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
            continue
        if is_under_allowed_write_path(root, str(rel), allowed_roots):
            continue
        found.append(path)
    return found


def snapshot(workspace: Path, allowed_roots: list[str]) -> dict[str, bytes]:
    """Capture environment-owned file contents so they can be restored."""
    root = workspace.resolve()
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in protected_files(root, allowed_roots)
    }


def verify_and_restore(
    workspace: Path,
    before: dict[str, bytes],
    allowed_roots: list[str],
) -> list[str]:
    """Undo any change a subprocess made to environment-owned files.

    Returns the workspace-relative paths that were modified, deleted, or added.
    """
    root = workspace.resolve()
    after = snapshot(root, allowed_roots)
    changed: list[str] = []

    for rel, content in before.items():
        if after.get(rel) != content:
            changed.append(rel)
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

    for rel in after:
        if rel not in before:
            changed.append(rel)
            (root / rel).unlink()

    return sorted(changed)
