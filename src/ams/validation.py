from __future__ import annotations

import re
from pathlib import Path
from pydantic import ValidationError

from .io import load_model
from .schemas import (
    CandidateManifest,
    EnvironmentManifest,
    ValidationIssue,
    ValidationReport,
)


_CONTROL_FLOW_SPLIT = re.compile(r"\s*(?:->|,|\+|\|)\s*")
_COMPONENT_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _control_flow_ids(control_flow: str) -> list[str]:
    text = control_flow.strip()
    if not text:
        return []
    if "->" not in text and "," not in text and "+" not in text and "|" not in text:
        return [text] if _COMPONENT_ID.fullmatch(text) else []
    return [part for part in _CONTROL_FLOW_SPLIT.split(text) if part]


def _declared_name(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(":", 1)[-1].split(".")[-1]


def _signature_issue_location(signature: dict) -> str:
    return f"{signature['file']}:{signature['line']}"


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
    deterministic_components = cand.decomposition.deterministic_components

    if not llm_modules and not deterministic_components:
        issues.append(ValidationIssue(
            severity="error",
            rule="DECOMPOSITION_COMPONENTS_MISSING",
            message="Candidate must declare at least one LLM module or deterministic component.",
            location="decomposition",
        ))

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
        for component in deterministic_components:
            if not component.signature or not component.inputs or not component.outputs:
                issues.append(ValidationIssue(
                    severity="error",
                    rule="DETERMINISTIC_TYPED_CONTRACT",
                    message=(
                        f"Deterministic component '{component.id}' must declare a DSPy signature "
                        "plus at least one typed input and output."
                    ),
                    location=f"decomposition.deterministic_components.{component.id}",
                ))

    if dc.deterministic_calculations_testable:
        for component in deterministic_components:
            if not component.implementation:
                issues.append(ValidationIssue(
                    severity="error",
                    rule="DETERMINISTIC_MODULE_DECLARATION",
                    message=(
                        f"Deterministic component '{component.id}' must declare the DSPy module "
                        "implementation that owns the calculation."
                    ),
                    location=f"decomposition.deterministic_components.{component.id}",
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

    declared_components = {m.id for m in llm_modules} | {c.id for c in deterministic_components}
    for stage in _control_flow_ids(cand.decomposition.control_flow):
        if stage not in declared_components:
            issues.append(ValidationIssue(
                severity="error",
                rule="CONTROL_FLOW_UNKNOWN_COMPONENT",
                message=f"control_flow references undeclared component '{stage}'.",
                location="decomposition.control_flow",
            ))

    valid = not any(i.severity == "error" for i in issues)
    return ValidationReport(
        valid=valid,
        issues=issues,
        summary={
            "environment": env.environment.name,
            "candidate": cand.candidate_name,
            "capabilities_available": len(declared_caps),
            "llm_modules_declared": len(llm_modules),
            "deterministic_components_declared": len(deterministic_components),
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
        env = load_model(workspace / "environment.yaml", EnvironmentManifest)
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
    if env.constraints.decomposition.require_typed_contracts:
        for sig_name, sig in signatures.items():
            if not sig["inputs"] or not sig["outputs"]:
                issues.append(ValidationIssue(
                    severity="error",
                    rule="DSPY_SIGNATURE_UNTYPED",
                    message=(
                        f"DSPy signature '{sig_name}' must expose InputField and "
                        "OutputField declarations."
                    ),
                    location=_signature_issue_location(sig),
                ))

    for module_id, found in discovered.items():
        sig_name = found.get("signature")
        if sig_name and sig_name in signatures:
            _check_declared_signature_contract(
                issues=issues,
                component_id=module_id,
                declared_inputs=declared[module_id].inputs if module_id in declared else [],
                declared_outputs=declared[module_id].outputs if module_id in declared else [],
                signature=signatures[sig_name],
                location=f"decomposition.llm_modules.{module_id}",
            )

    dspy_modules = {m["name"]: m for m in inspection["modules"]}
    dspy_modules_by_id = {m["id"]: m for m in inspection["modules"]}
    declared_deterministic_module_names: set[str] = set()
    for component in cand.decomposition.deterministic_components:
        implementation_name = _declared_name(component.implementation)
        found = (
            dspy_modules.get(implementation_name)
            if implementation_name
            else dspy_modules_by_id.get(component.id)
        ) or dspy_modules_by_id.get(component.id)
        if found is None:
            issues.append(ValidationIssue(
                severity="error",
                rule="DECLARED_DSPY_MODULE_NOT_FOUND",
                message=(
                    f"Declared deterministic component '{component.id}' was not found as a "
                    "dspy.Module in candidate source."
                ),
                location=f"decomposition.deterministic_components.{component.id}",
            ))
            continue

        declared_deterministic_module_names.add(found["name"])
        if not found.get("has_forward"):
            issues.append(ValidationIssue(
                severity="error",
                rule="DSPY_MODULE_FORWARD_MISSING",
                message=(
                    f"Deterministic component '{component.id}' maps to dspy.Module "
                    f"'{found['name']}', but that module does not define forward()."
                ),
                location=f"{found['file']}:{found['line']}",
            ))

        declared_signature = _declared_name(component.signature)
        source_signature = found.get("signature")
        if declared_signature:
            if declared_signature not in signatures:
                issues.append(ValidationIssue(
                    severity="error",
                    rule="DECLARED_DSPY_SIGNATURE_NOT_FOUND",
                    message=(
                        f"Deterministic component '{component.id}' declares signature "
                        f"'{component.signature}', but it was not found in candidate source."
                    ),
                    location=f"decomposition.deterministic_components.{component.id}",
                ))
                continue
            if source_signature and _declared_name(source_signature) != declared_signature:
                issues.append(ValidationIssue(
                    severity="error",
                    rule="DSPY_MODULE_SIGNATURE_MISMATCH",
                    message=(
                        f"Deterministic component '{component.id}' declares signature "
                        f"'{component.signature}', but source binds '{source_signature}'."
                    ),
                    location=f"{found['file']}:{found['line']}",
                ))
            if not source_signature:
                issues.append(ValidationIssue(
                    severity="error",
                    rule="DSPY_MODULE_SIGNATURE_NOT_BOUND",
                    message=(
                        f"Deterministic component '{component.id}' declares signature "
                        f"'{component.signature}', but its dspy.Module does not bind a signature."
                    ),
                    location=f"{found['file']}:{found['line']}",
                ))
            _check_declared_signature_contract(
                issues=issues,
                component_id=component.id,
                declared_inputs=component.inputs,
                declared_outputs=component.outputs,
                signature=signatures[declared_signature],
                location=f"decomposition.deterministic_components.{component.id}",
            )

    boundary_owner_classes = {
        found["owner_class"] for found in discovered.values() if found.get("owner_class")
    }
    for found in inspection["modules"]:
        if found["name"] in boundary_owner_classes:
            continue
        if found["name"] not in declared_deterministic_module_names:
            issues.append(ValidationIssue(
                severity="error",
                rule="UNDECLARED_DSPY_MODULE",
                message=(
                    f"DSPy module '{found['name']}' exists in source but is not declared "
                    "as a deterministic component."
                ),
                location=f"{found['file']}:{found['line']}",
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
            "dspy_modules_discovered": len(inspection["modules"]),
        },
    )


def _check_declared_signature_contract(
    *,
    issues: list[ValidationIssue],
    component_id: str,
    declared_inputs,
    declared_outputs,
    signature: dict,
    location: str,
) -> None:
    actual_inputs = set(signature["inputs"])
    actual_outputs = set(signature["outputs"])
    expected_inputs = {field.name for field in declared_inputs}
    expected_outputs = {field.name for field in declared_outputs}
    if expected_inputs and expected_inputs != actual_inputs:
        issues.append(ValidationIssue(
            severity="error",
            rule="DSPY_SIGNATURE_INPUT_MISMATCH",
            message=(
                f"Component '{component_id}' declares inputs {sorted(expected_inputs)} "
                f"but DSPy signature '{signature['name']}' exposes {sorted(actual_inputs)}."
            ),
            location=location,
        ))
    if expected_outputs and expected_outputs != actual_outputs:
        issues.append(ValidationIssue(
            severity="error",
            rule="DSPY_SIGNATURE_OUTPUT_MISMATCH",
            message=(
                f"Component '{component_id}' declares outputs {sorted(expected_outputs)} "
                f"but DSPy signature '{signature['name']}' exposes {sorted(actual_outputs)}."
            ),
            location=location,
        ))
