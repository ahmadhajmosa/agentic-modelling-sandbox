from __future__ import annotations

from pathlib import Path


class WorkspacePolicyError(ValueError):
    pass


def resolve_workspace_path(workspace: Path, relative_path: str) -> Path:
    root = workspace.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorkspacePolicyError(f"Path escapes workspace: {relative_path}") from exc
    return candidate


def is_under_allowed_write_path(workspace: Path, relative_path: str, allowed_roots: list[str]) -> bool:
    candidate = resolve_workspace_path(workspace, relative_path)
    root = workspace.resolve()
    for allowed in allowed_roots:
        allowed_path = (root / allowed).resolve()
        if candidate == allowed_path or allowed_path in candidate.parents:
            return True
    return False


def write_workspace_file(
    workspace: Path,
    relative_path: str,
    content: str,
    allowed_roots: list[str],
    max_file_bytes: int,
) -> Path:
    encoded = content.encode("utf-8")
    if len(encoded) > max_file_bytes:
        raise WorkspacePolicyError(
            f"File exceeds max_file_bytes={max_file_bytes}: {relative_path}"
        )
    if not is_under_allowed_write_path(workspace, relative_path, allowed_roots):
        raise WorkspacePolicyError(
            f"Write path is not allowed: {relative_path}; allowed roots: {allowed_roots}"
        )
    target = resolve_workspace_path(workspace, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def read_workspace_file(workspace: Path, relative_path: str, max_chars: int) -> str:
    target = resolve_workspace_path(workspace, relative_path)
    if not target.is_file():
        raise FileNotFoundError(relative_path)
    text = target.read_text(encoding="utf-8")
    return text[:max_chars]
