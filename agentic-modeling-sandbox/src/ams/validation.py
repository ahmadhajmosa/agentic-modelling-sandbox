from __future__ import annotations

from pathlib import Path
from pydantic import ValidationError

from .io import load_model
from .schemas import (
    CandidateManifest,
    EnvironmentManifest,
    ValidationIssue,
    ValidationReport,
)


def validate_candidate(environment_path: str | Path, candidate_path: str | Path) -> ValidationReport:
    issues: list[ValidationIssue] = []

    try:
        env = load_model(environment_path, EnvironmentManifest)
    except ValidationError as exc:
        return ValidationReport(
            valid=False,
            issues=[ValidationIssue(severity="error", rule="ENVIRONMENT_SCHEMA", message=str(exc))],
        )

    try:
        cand = load_model(candidate_path, CandidateManifest)
    except ValidationError as exc:
        return ValidationReport(
            valid=False,
            issues=[ValidationIssue(severity="error", rule="CANDIDATE_SCHEMA", message=str(exc))],
        )

    dc = env.constraints.decomposition
    llm_modules = cand.decomposition.llm_modules

    if dc.require_explicit_llm_boundaries and not llm_modules:
        issues.append(ValidationIssue(
            severity="warning",
            rule="EXPLICIT_LLM_BOUNDARIES",
            message="No LLM-facing modules were declared. This is valid only if the candidate is fully deterministic.",
            location="decomposition.llm_modules",
        ))

    if dc.require_typed_contracts:
        for module in llm_modules:
            if not module.inputs or not module.outputs:
                issues.append(ValidationIssue(
                    severity="error",
                    rule="LLM_TYPED_CONTRACT",
                    message=f"LLM module '{module.id}' must declare at least one typed input and output.",
                    location=f"decomposition.llm_modules.{module.id}",
                ))

    if dc.require_end_to_end_contract and not cand.evaluation.end_to_end_metric.strip():
        issues.append(ValidationIssue(
            severity="error",
            rule="END_TO_END_METRIC",
            message="Candidate must declare an end-to-end evaluation metric.",
            location="evaluation.end_to_end_metric",
        ))

    for module in llm_modules:
        if not module.evaluation_metric and module.id not in cand.evaluation.module_metrics:
            issues.append(ValidationIssue(
                severity="error",
                rule="LLM_MODULE_EVALUATION",
                message=f"Material LLM module '{module.id}' has no independent evaluation metric.",
                location=f"decomposition.llm_modules.{module.id}",
            ))

    required = set(env.constraints.validation.required_checks)
    proposed = set(cand.validation.checks)
    missing = sorted(required - proposed)
    for check in missing:
        issues.append(ValidationIssue(
            severity="error",
            rule="REQUIRED_VALIDATION_CHECK",
            message=f"Required environment validation check is missing: {check}",
            location="validation.checks",
        ))

    declared_caps = {c.name for c in env.capabilities}
    # For V0.1 capabilities are discoverable but candidate does not yet redeclare usage.

    valid = not any(i.severity == "error" for i in issues)
    return ValidationReport(
        valid=valid,
        issues=issues,
        summary={
            "environment": env.environment.name,
            "candidate": cand.candidate_name,
            "capabilities_available": len(declared_caps),
            "llm_modules_declared": len(llm_modules),
            "required_checks": len(required),
        },
    )


def validate_source_alignment(workspace: str | Path) -> ValidationReport:
    """Validate candidate declarations against statically discovered DSPy source.

    This performs AST inspection only; it never imports or executes candidate code.
    """
    from .dspy_inspector import inspect_candidate

    workspace = Path(workspace)
    base = validate_candidate(workspace / "environment.yaml", workspace / "candidate.yaml")
    issues = list(base.issues)

    try:
        cand = load_model(workspace / "candidate.yaml", CandidateManifest)
        inspection = inspect_candidate(workspace)
    except (ValidationError, FileNotFoundError) as exc:
        issues.append(ValidationIssue(
            severity="error",
            rule="DSPY_INSPECTION",
            message=str(exc),
        ))
        return ValidationReport(valid=False, issues=issues)

    for err in inspection["parse_errors"]:
        issues.append(ValidationIssue(
            severity="error",
            rule="SOURCE_PARSE_ERROR",
            message=err["error"],
            location=err["file"],
        ))

    declared = {m.id: m for m in cand.decomposition.llm_modules}
    discovered = {m["id"]: m for m in inspection["boundaries"]}

    for module_id, module in declared.items():
        found = discovered.get(module_id)
        if found is None:
            issues.append(ValidationIssue(
                severity="error",
                rule="DECLARED_LLM_BOUNDARY_NOT_FOUND",
                message=f"Declared LLM module '{module_id}' was not found in candidate source.",
                location=f"decomposition.llm_modules.{module_id}",
            ))
            continue
        if module.implementation:
            declared_impl = module.implementation.split(".")[-1]
            discovered_impl = found["implementation"].split(".")[-1]
            if declared_impl != discovered_impl:
                issues.append(ValidationIssue(
                    severity="error",
                    rule="LLM_IMPLEMENTATION_MISMATCH",
                    message=f"LLM module '{module_id}' declares '{module.implementation}' but source uses '{found['implementation']}'.",
                    location=f"{found['file']}:{found['line']}",
                ))

    for module_id, found in discovered.items():
        if module_id not in declared:
            issues.append(ValidationIssue(
                severity="error",
                rule="UNDECLARED_LLM_BOUNDARY",
                message=f"DSPy LLM boundary '{module_id}' exists in source but is not declared in candidate.yaml.",
                location=f"{found['file']}:{found['line']}",
            ))

    signatures = {s["name"]: s for s in inspection["signatures"]}
    for module_id, found in discovered.items():
        sig_name = found.get("signature")
        if sig_name and sig_name in signatures:
            sig = signatures[sig_name]
            if not sig["inputs"] or not sig["outputs"]:
                issues.append(ValidationIssue(
                    severity="error",
                    rule="DSPY_SIGNATURE_UNTYPED",
                    message=f"DSPy signature '{sig_name}' used by '{module_id}' must expose InputField and OutputField declarations.",
                    location=f"{sig['file']}:{sig['line']}",
                ))

    optimization_targets = set(cand.optimization.targets)
    for module_id, module in declared.items():
        if module.optimization_target and module_id not in optimization_targets:
            issues.append(ValidationIssue(
                severity="error",
                rule="OPTIMIZATION_TARGET_MISSING",
                message=f"LLM module '{module_id}' is marked optimization_target but is absent from optimization.targets.",
                location="optimization.targets",
            ))

    valid = not any(i.severity == "error" for i in issues)
    return ValidationReport(
        valid=valid,
        issues=issues,
        summary={
            **base.summary,
            "source_files_scanned": inspection["files_scanned"],
            "dspy_boundaries_discovered": len(inspection["boundaries"]),
            "dspy_signatures_discovered": len(inspection["signatures"]),
        },
    )
