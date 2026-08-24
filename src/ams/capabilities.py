from __future__ import annotations

import importlib
import inspect
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .schemas import Capability, EnvironmentManifest


class CapabilityError(RuntimeError):
    pass


@contextmanager
def _workspace_import_path(workspace: Path):
    workspace = workspace.resolve()
    value = str(workspace)
    inserted = value not in sys.path
    if inserted:
        sys.path.insert(0, value)
    try:
        yield
    finally:
        if inserted and value in sys.path:
            sys.path.remove(value)


def get_capability(manifest: EnvironmentManifest, name: str) -> Capability:
    matches = [cap for cap in manifest.capabilities if cap.name == name]
    if not matches:
        raise CapabilityError(f"Capability '{name}' is not declared by this environment.")
    if len(matches) > 1:
        raise CapabilityError(f"Capability '{name}' is declared more than once.")
    return matches[0]


def load_declared_callable(workspace: Path, capability: Capability):
    try:
        module_name, attr_name = capability.callable.split(":", 1)
    except ValueError as exc:
        raise CapabilityError(
            f"Capability '{capability.name}' has invalid callable '{capability.callable}'. Expected module:function."
        ) from exc

    # Environment-owned modules are loaded from the workspace. The calling agent
    # cannot choose arbitrary import targets; only manifest-declared callables are accepted.
    with _workspace_import_path(workspace):
        try:
            module = importlib.import_module(module_name)
            fn = getattr(module, attr_name)
        except (ImportError, AttributeError) as exc:
            raise CapabilityError(
                f"Could not load declared capability '{capability.name}' from '{capability.callable}': {exc}"
            ) from exc
    if not callable(fn):
        raise CapabilityError(f"Declared target '{capability.callable}' is not callable.")
    return fn


def validate_arguments(fn, arguments: dict[str, Any]) -> None:
    try:
        inspect.signature(fn).bind(**arguments)
    except TypeError as exc:
        raise CapabilityError(f"Capability arguments do not match callable signature: {exc}") from exc


def invoke_capability(
    workspace: Path,
    manifest: EnvironmentManifest,
    name: str,
    arguments: dict[str, Any],
) -> tuple[Capability, Any]:
    capability = get_capability(manifest, name)
    fn = load_declared_callable(workspace, capability)
    validate_arguments(fn, arguments)
    try:
        result = fn(**arguments)
    except Exception as exc:  # capability implementation error is returned as an observation
        raise CapabilityError(f"Capability '{name}' failed: {type(exc).__name__}: {exc}") from exc

    try:
        json.dumps(result)
    except TypeError as exc:
        raise CapabilityError(
            f"Capability '{name}' returned a non-JSON-serializable result of type {type(result).__name__}."
        ) from exc
    return capability, result


def describe_capability(workspace: Path, capability: Capability) -> dict[str, Any]:
    data = capability.model_dump()
    try:
        fn = load_declared_callable(workspace, capability)
        sig = inspect.signature(fn)
        data["runtime_signature"] = str(sig)
        data["available"] = True
    except CapabilityError as exc:
        data["runtime_signature"] = None
        data["available"] = False
        data["load_error"] = str(exc)
    return data
