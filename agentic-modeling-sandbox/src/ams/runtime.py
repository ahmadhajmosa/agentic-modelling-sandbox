from __future__ import annotations

import os
import subprocess
import time
import uuid
from pathlib import Path

from pydantic import TypeAdapter

from .actions import ActionRequest, EvaluateCandidateAction, InvokeCapabilityAction, ReadFileAction, RunCommandAction, RunTestsAction, WriteFileAction
from .history import append_observation
from .io import load_model
from .observations import ActionObservation, PolicyDecision
from .schemas import EnvironmentManifest
from .workspace import WorkspacePolicyError, read_workspace_file, write_workspace_file
from .capabilities import CapabilityError, invoke_capability
from .evaluation import EvaluationError, EvaluationPolicyError, evaluate_candidate
from .integrity import snapshot, verify_and_restore

ACTION_ADAPTER = TypeAdapter(ActionRequest)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    suffix = f"\n...[truncated {len(value) - limit} chars]"
    return value[: max(0, limit - len(suffix))] + suffix


def _observation(action_type: str, status: str, rule: str, message: str, **kwargs) -> ActionObservation:
    return ActionObservation(
        action_id=str(uuid.uuid4()),
        action_type=action_type,
        status=status,
        policy=PolicyDecision(allowed=status not in {"denied"}, rule=rule, message=message),
        **kwargs,
    )


def _command_allowed(argv: list[str], allowed_commands: list[str]) -> bool:
    executable = Path(argv[0]).name
    return executable in set(allowed_commands)


def _run_subprocess(workspace: Path, argv: list[str], env_manifest: EnvironmentManifest) -> ActionObservation:
    constraints = env_manifest.constraints.execution
    if not _command_allowed(argv, constraints.allowed_commands):
        return _observation(
            "run_command",
            "denied",
            "COMMAND_ALLOWLIST",
            f"Command '{argv[0]}' is not allowed; allowed commands: {constraints.allowed_commands}",
        )

    # An allowlisted interpreter can write outside allowed_write_paths, so
    # environment-owned files are snapshotted and restored if the command
    # changes them.
    before = snapshot(workspace, constraints.allowed_write_paths)
    observation = _execute_subprocess(workspace, argv, constraints)
    restored = verify_and_restore(workspace, before, constraints.allowed_write_paths)
    if restored:
        return _observation(
            "run_command",
            "denied",
            "ENVIRONMENT_INTEGRITY",
            "Command modified environment-owned files outside allowed_write_paths; "
            f"the changes were reverted: {restored}",
            exit_code=observation.exit_code,
            stdout=observation.stdout,
            stderr=observation.stderr,
            elapsed_ms=observation.elapsed_ms,
            data={
                "argv": argv,
                "restored_paths": restored,
                "allowed_write_paths": constraints.allowed_write_paths,
            },
        )
    return observation


def _execute_subprocess(workspace: Path, argv: list[str], constraints) -> ActionObservation:
    started = time.monotonic()
    # The candidate workspace is put on PYTHONPATH so subprocess tests can import
    # the candidate's own source roots (e.g. `from src.model import ...`).
    workspace_root = str(workspace.resolve())
    inherited = os.environ.get("PYTHONPATH", "")
    clean_env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.pathsep.join([workspace_root, inherited]) if inherited else workspace_root,
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    try:
        proc = subprocess.run(
            argv,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=constraints.timeout_seconds,
            shell=False,
            env=clean_env,
        )
        elapsed = int((time.monotonic() - started) * 1000)
        return _observation(
            "run_command",
            "success" if proc.returncode == 0 else "error",
            "COMMAND_ALLOWLIST",
            "Command allowed by local execution policy.",
            exit_code=proc.returncode,
            stdout=_truncate(proc.stdout, constraints.max_output_chars),
            stderr=_truncate(proc.stderr, constraints.max_output_chars),
            elapsed_ms=elapsed,
            data={
                "argv": argv,
                "network_policy": "declared_disabled_not_os_enforced" if not constraints.network else "allowed",
            },
        )
    except FileNotFoundError:
        # An allowlisted executable that is not installed is reported as an
        # observation; the protocol always answers with an observation.
        return _observation(
            "run_command",
            "error",
            "COMMAND_NOT_FOUND",
            f"Executable '{argv[0]}' is allowed by policy but was not found on PATH.",
            elapsed_ms=int((time.monotonic() - started) * 1000),
            data={"argv": argv},
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return _observation(
            "run_command",
            "timeout",
            "COMMAND_TIMEOUT",
            f"Command exceeded timeout of {constraints.timeout_seconds}s.",
            stdout=_truncate(stdout, constraints.max_output_chars),
            stderr=_truncate(stderr, constraints.max_output_chars),
            elapsed_ms=elapsed,
            data={"argv": argv},
        )


def execute_action(workspace: str | Path, raw_action: dict) -> ActionObservation:
    workspace = Path(workspace)
    action = ACTION_ADAPTER.validate_python(raw_action)
    env_manifest = load_model(workspace / "environment.yaml", EnvironmentManifest)
    constraints = env_manifest.constraints.execution

    if isinstance(action, WriteFileAction):
        try:
            target = write_workspace_file(
                workspace,
                action.path,
                action.content,
                constraints.allowed_write_paths,
                constraints.max_file_bytes,
            )
            obs = _observation(
                action.type,
                "success",
                "WRITE_PATH_POLICY",
                "Write allowed by workspace policy.",
                artifacts_changed=[str(target.relative_to(workspace.resolve()))],
                data={"bytes_written": len(action.content.encode('utf-8'))},
            )
        except WorkspacePolicyError as exc:
            obs = _observation(action.type, "denied", "WRITE_PATH_POLICY", str(exc))

    elif isinstance(action, ReadFileAction):
        try:
            limit = min(action.max_chars or constraints.max_output_chars, constraints.max_output_chars)
            content = read_workspace_file(workspace, action.path, limit)
            obs = _observation(
                action.type,
                "success",
                "WORKSPACE_READ",
                "Read allowed inside workspace.",
                data={"path": action.path, "content": content},
            )
        except (WorkspacePolicyError, FileNotFoundError) as exc:
            obs = _observation(action.type, "denied", "WORKSPACE_READ", str(exc))

    elif isinstance(action, RunTestsAction):
        obs = _run_subprocess(workspace, action.argv, env_manifest)
        obs.action_type = action.type

    elif isinstance(action, RunCommandAction):
        obs = _run_subprocess(workspace, action.argv, env_manifest)

    elif isinstance(action, EvaluateCandidateAction):
        started = time.monotonic()
        try:
            report = evaluate_candidate(workspace, split=action.split, final=action.final)
            elapsed = int((time.monotonic() - started) * 1000)
            obs = _observation(
                action.type,
                "success",
                "EVALUATION_PROTOCOL",
                "Candidate evaluated under the environment-defined protocol.",
                elapsed_ms=elapsed,
                data=report,
            )
        except EvaluationError as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            obs = _observation(
                action.type,
                "denied" if isinstance(exc, EvaluationPolicyError) else "error",
                "EVALUATION_PROTOCOL",
                str(exc),
                elapsed_ms=elapsed,
                data={"split": action.split, "final": action.final},
            )

    elif isinstance(action, InvokeCapabilityAction):
        started = time.monotonic()
        try:
            capability, result = invoke_capability(
                workspace, env_manifest, action.capability, action.arguments
            )
            elapsed = int((time.monotonic() - started) * 1000)
            obs = _observation(
                action.type,
                "success",
                "CAPABILITY_REGISTRY",
                "Capability invocation allowed because it is declared by the environment.",
                elapsed_ms=elapsed,
                data={
                    "capability": capability.name,
                    "callable": capability.callable,
                    "deterministic": capability.deterministic,
                    "arguments": action.arguments,
                    "result": result,
                },
            )
        except CapabilityError as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            obs = _observation(
                action.type,
                "denied" if "not declared" in str(exc) else "error",
                "CAPABILITY_REGISTRY",
                str(exc),
                elapsed_ms=elapsed,
                data={"capability": action.capability, "arguments": action.arguments},
            )

    else:  # pragma: no cover
        raise TypeError(f"Unsupported action: {type(action)}")

    append_observation(workspace, obs)
    return obs
