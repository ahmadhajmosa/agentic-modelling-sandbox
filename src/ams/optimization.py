from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dspy_inspector import inspect_candidate
from .evaluation import evaluate_candidate, EvaluationError
from .io import load_model
from .schemas import CandidateManifest, EnvironmentManifest
from .validation import validate_source_alignment


class OptimizationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _dataset_fingerprints(workspace: Path, env: EnvironmentManifest) -> dict[str, dict[str, str]]:
    result = {}
    for split in ("train", "validation", "test"):
        rel = getattr(env.evaluation.datasets, split)
        p = (workspace / rel).resolve()
        result[split] = {"path": rel, "sha256": _sha256(p)}
    return result


def optimization_plan(workspace: str | Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    env = load_model(workspace / "environment.yaml", EnvironmentManifest)
    cand = load_model(workspace / "candidate.yaml", CandidateManifest)
    source_report = validate_source_alignment(workspace)
    if not source_report.valid:
        raise OptimizationError("Candidate must pass source-aware validation before an optimization plan can be issued.")

    inspection = inspect_candidate(workspace)
    discovered = {b["id"]: b for b in inspection["boundaries"]}
    targets = []
    for module in cand.decomposition.llm_modules:
        if module.optimization_target:
            if module.id not in cand.optimization.targets:
                raise OptimizationError(f"Optimization target '{module.id}' is not listed in optimization.targets")
            targets.append({
                "id": module.id,
                "implementation": discovered.get(module.id, {}).get("implementation", module.implementation),
                "metric": module.evaluation_metric or cand.evaluation.module_metrics.get(module.id),
                "signature": discovered.get(module.id, {}).get("signature"),
            })

    baseline = evaluate_candidate(workspace, split="validation", final=False)
    fingerprints = _dataset_fingerprints(workspace, env)
    plan = {
        "schema_version": "ams/optimization-plan-v1",
        "environment": env.environment.name,
        "candidate": cand.candidate_name,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "optimizer_owner": "external",
        "targets": targets,
        "end_to_end_metric": cand.evaluation.end_to_end_metric,
        "baseline": {
            "split": "validation",
            "score": baseline["score"],
            "accepted": baseline["accepted"],
        },
        "datasets": {
            "train": fingerprints["train"],
            "validation": fingerprints["validation"],
            "test": {
                "protected": env.evaluation.protect_test_split,
                "sha256": fingerprints["test"]["sha256"],
            },
        },
        "rules": {
            "ams_runs_no_llm_optimizer": True,
            "external_agent_or_runtime_performs_optimization": True,
            "validation_is_available_during_optimization": True,
            "test_is_protected_until_verification": env.evaluation.protect_test_split,
            "candidate_must_preserve_environment_dataset_fingerprints": True,
        },
    }
    return plan


def save_optimization_plan(workspace: str | Path, plan: dict[str, Any]) -> Path:
    workspace = Path(workspace).resolve()
    out = workspace / ".ams" / "optimization-plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return out


def load_saved_plan(workspace: str | Path) -> dict[str, Any]:
    p = Path(workspace).resolve() / ".ams" / "optimization-plan.json"
    if not p.exists():
        raise OptimizationError("No saved optimization plan. Run 'ams optimization-plan' first.")
    return json.loads(p.read_text(encoding="utf-8"))


def verify_optimization(workspace: str | Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    env = load_model(workspace / "environment.yaml", EnvironmentManifest)
    plan = load_saved_plan(workspace)

    current = _dataset_fingerprints(workspace, env)
    for split in ("train", "validation"):
        expected = plan["datasets"][split]["sha256"]
        if current[split]["sha256"] != expected:
            raise OptimizationError(f"{split} dataset changed after optimization plan issuance")
    if current["test"]["sha256"] != plan["datasets"]["test"]["sha256"]:
        raise OptimizationError("Protected test dataset changed after optimization plan issuance")

    source_report = validate_source_alignment(workspace)
    if not source_report.valid:
        raise OptimizationError("Optimized candidate fails source-aware validation.")

    validation = evaluate_candidate(workspace, split="validation", final=False)
    held_out = evaluate_candidate(workspace, split="test", final=True)
    baseline = float(plan["baseline"]["score"])
    delta = float(validation["score"]) - baseline

    return {
        "schema_version": "ams/optimization-verification-v1",
        "environment": env.environment.name,
        "candidate": plan["candidate"],
        "baseline_validation_score": baseline,
        "candidate_validation_score": validation["score"],
        "validation_delta": delta,
        # Acceptance is non-regression plus held-out acceptance, so a candidate
        # already at a perfect baseline can still be verified. Improvement is
        # reported separately as evidence rather than used as the gate.
        "improved_on_validation": delta > 0,
        "held_out": {
            "score": held_out["score"],
            "minimum_score": held_out["minimum_score"],
            "accepted": held_out["accepted"],
            "cases_hidden": held_out.get("cases_hidden", False),
        },
        "accepted": bool(delta >= 0 and held_out["accepted"]),
        "dataset_integrity": "verified",
    }
