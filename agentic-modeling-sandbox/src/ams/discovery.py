from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from .actions import ActionRequest
from .evaluation import evaluate_candidate, EvaluationError
from .io import load_model
from .observations import ActionObservation
from .optimization import OptimizationError, load_saved_plan
from .schemas import CandidateManifest, EnvironmentManifest, ValidationReport
from .validation import validate_candidate, validate_source_alignment


HELP_TOPICS: dict[str, dict[str, Any]] = {
    "environment": {
        "title": "Environment",
        "summary": "AMS defines the world the external agent operates in.",
        "principles": [
            "environment.yaml is environment-owned and should be treated as immutable by the agent",
            "the environment defines capabilities, hard constraints, evaluation datasets, and acceptance criteria",
            "AMS contains no embedded LLM",
        ],
        "recommended_commands": ["ams state", "ams rules", "ams capabilities", "ams schema environment"],
    },
    "candidate": {
        "title": "Candidate",
        "summary": "candidate.yaml is the agent-owned declaration of the modeling program it created.",
        "principles": [
            "the external agent owns decomposition and code generation",
            "candidate.yaml must declare material LLM boundaries, contracts, validation checks, metrics, and optimization targets",
            "candidate.yaml cannot override environment-owned constraints or held-out evaluation rules",
        ],
        "recommended_commands": ["ams schema candidate", "ams validate --source", "ams inspect-dspy"],
    },
    "actions": {
        "title": "Actions",
        "summary": "Actions are typed requests submitted to the sandbox runtime.",
        "principles": [
            "all actions are validated against a fixed schema",
            "policy determines whether a requested action is allowed",
            "every action produces a structured observation",
        ],
        "recommended_commands": ["ams schema action", "ams act", "ams observations"],
    },
    "decomposition": {
        "title": "Decomposition",
        "summary": "AMS enforces properties of a decomposition but does not prescribe the architecture.",
        "principles": [
            "material LLM boundaries must be explicit",
            "LLM-facing stages require typed inputs and outputs",
            "deterministic calculations should remain independently testable",
            "the whole program requires an end-to-end evaluation contract",
            "examples are guidance only and are not required module graphs",
        ],
        "examples_are_prescriptive": False,
        "examples": [
            "interpret assumptions -> deterministic model -> validate -> explain",
            "retrieve model inputs -> code execution -> reconcile results",
            "classify request -> choose model -> execute -> compare scenarios",
            "parallel specialist modules -> aggregate -> validate",
        ],
        "recommended_commands": ["ams help decomposition --json", "ams inspect-dspy", "ams validate --source"],
    },
    "contracts": {
        "title": "Contracts",
        "summary": "Contracts make LLM-facing behavior and final modeling outputs testable.",
        "principles": [
            "declare explicit inputs and outputs for material LLM boundaries",
            "source-aware validation compares candidate declarations with discovered DSPy boundaries",
            "deterministic model controls should remain executable without an LLM",
        ],
        "recommended_commands": ["ams schema candidate", "ams validate --source"],
    },
    "evaluation": {
        "title": "Evaluation",
        "summary": "AMS owns the evaluation protocol and returns structured fitness observations.",
        "principles": [
            "train and validation data may be used during development",
            "protected held-out test cases require final evaluation",
            "minimum acceptance score is environment-owned",
            "AMS reports case-level feedback for non-protected splits",
        ],
        "recommended_commands": ["ams eval --split validation", "ams rules", "ams help optimization"],
    },
    "optimization": {
        "title": "Optimization",
        "summary": "AMS defines and verifies optimization evidence; the external agent/runtime performs the optimization.",
        "principles": [
            "AMS never invokes an LLM optimizer itself",
            "optimization targets are declared by the candidate",
            "AMS fingerprints datasets and records the validation baseline",
            "held-out test data remains protected until verification",
            "verification requires validation improvement and held-out acceptance",
        ],
        "recommended_commands": ["ams optimization-plan", "ams verify-optimization"],
    },
    "dspy": {
        "title": "DSPy",
        "summary": "AMS is DSPy-aware but does not prescribe a DSPy architecture.",
        "principles": [
            "static AST inspection discovers common DSPy LM boundaries and signatures",
            "candidate source is not imported or executed during inspection",
            "discovered boundaries are compared with candidate.yaml declarations",
            "each material LLM boundary should be independently measurable and optimizable when declared as a target",
        ],
        "recommended_commands": ["ams inspect-dspy --json", "ams validate --source --json"],
    },
}


EXAMPLES: dict[str, dict[str, Any]] = {
    "decomposition": {
        "examples_are_prescriptive": False,
        "patterns": HELP_TOPICS["decomposition"]["examples"],
    },
    "action": {
        "write_file": {"type": "write_file", "path": "src/model.py", "content": "# candidate code\n"},
        "read_file": {"type": "read_file", "path": "src/model.py", "max_chars": 4000},
        "run_tests": {"type": "run_tests", "argv": ["pytest", "-q"]},
        "invoke_capability": {
            "type": "invoke_capability",
            "capability": "calculate_funded_ratio",
            "arguments": {"asset_value": 90.0, "liability_value": 100.0},
        },
        "evaluate_candidate": {"type": "evaluate_candidate", "split": "validation", "final": False},
    },
    "workflow": {
        "steps": [
            "ams state --json",
            "ams rules --json",
            "ams capabilities --json",
            "ams schema candidate --json",
            "write or modify candidate.yaml and source",
            "ams validate --source --json",
            "ams test or ams act with run_tests",
            "ams eval --split validation --json",
            "ams optimization-plan --json",
            "optimize externally",
            "ams verify-optimization --json",
        ]
    },
}


def overview() -> dict[str, Any]:
    return {
        "name": "Agentic Modeling Sandbox",
        "abbreviation": "AMS",
        "principle": "AMS defines the environment; the external LLM agent decides how to act inside it.",
        "ams_does": [
            "expose state, rules, capabilities, schemas, validation, evaluation, and optimization requirements",
            "enforce workspace and execution policy",
            "return structured observations and fitness signals",
        ],
        "ams_does_not": [
            "contain an embedded LLM",
            "generate the candidate modeling code",
            "prescribe a universal DSPy module graph",
            "run an LLM optimizer",
        ],
        "recommended_workflow": EXAMPLES["workflow"]["steps"],
        "machine_readable": "Use --json on discovery and operational commands.",
        "topics": sorted(HELP_TOPICS),
    }


def topic_help(topic: str) -> dict[str, Any]:
    try:
        return HELP_TOPICS[topic]
    except KeyError as exc:
        raise KeyError(f"Unknown help topic '{topic}'. Available: {', '.join(sorted(HELP_TOPICS))}") from exc


def schema_document(name: str) -> dict[str, Any]:
    normalized = name.replace("_", "-").lower()
    if normalized == "environment":
        return EnvironmentManifest.model_json_schema()
    if normalized == "candidate":
        return CandidateManifest.model_json_schema()
    if normalized == "action":
        return TypeAdapter(ActionRequest).json_schema()
    if normalized == "observation":
        return ActionObservation.model_json_schema()
    if normalized == "validation":
        return ValidationReport.model_json_schema()
    if normalized == "evaluation":
        # Evaluation report is currently a stable dict protocol rather than Pydantic model.
        return {
            "$id": "ams/evaluation-v1",
            "type": "object",
            "required": ["schema_version", "environment", "candidate", "split", "case_count", "score", "accepted", "metrics"],
            "properties": {
                "schema_version": {"const": "ams/evaluation-v1"},
                "environment": {"type": "string"},
                "candidate": {"type": "string"},
                "split": {"enum": ["train", "validation", "test"]},
                "case_count": {"type": "integer", "minimum": 0},
                "score": {"type": "number"},
                "minimum_score": {"type": ["number", "null"]},
                "accepted": {"type": "boolean"},
                "metrics": {"type": "array", "items": {"type": "string"}},
                "cases": {"type": "array"},
                "cases_hidden": {"type": "boolean"},
            },
        }
    if normalized in {"optimization-plan", "optimization"}:
        return {
            "$id": "ams/optimization-plan-v1",
            "type": "object",
            "required": ["schema_version", "environment", "candidate", "optimizer_owner", "targets", "baseline", "datasets", "rules"],
            "properties": {
                "schema_version": {"const": "ams/optimization-plan-v1"},
                "environment": {"type": "string"},
                "candidate": {"type": "string"},
                "optimizer_owner": {"const": "external"},
                "targets": {"type": "array"},
                "baseline": {"type": "object"},
                "datasets": {"type": "object"},
                "rules": {"type": "object"},
            },
        }
    raise KeyError(
        f"Unknown schema '{name}'. Available: environment, candidate, action, observation, validation, evaluation, optimization-plan"
    )


def examples_for(topic: str) -> dict[str, Any]:
    try:
        return EXAMPLES[topic]
    except KeyError as exc:
        raise KeyError(f"Unknown examples topic '{topic}'. Available: {', '.join(sorted(EXAMPLES))}") from exc


def guide(workspace: str | Path) -> dict[str, Any]:
    workspace = Path(workspace)
    env_path = workspace / "environment.yaml"
    cand_path = workspace / "candidate.yaml"

    if not env_path.exists():
        return {
            "stage": "uninitialized",
            "status": "blocked",
            "next_action": "Initialize an AMS workspace.",
            "command": f"ams init {workspace}",
            "reason": "environment.yaml is missing.",
        }
    if not cand_path.exists():
        return {
            "stage": "candidate_manifest",
            "status": "blocked",
            "next_action": "Create candidate.yaml using the fixed candidate schema.",
            "command": "ams schema candidate --json",
            "reason": "candidate.yaml is missing.",
        }

    try:
        report = validate_candidate(env_path, cand_path)
    except (ValidationError, FileNotFoundError) as exc:
        return {
            "stage": "candidate_manifest",
            "status": "blocked",
            "next_action": "Repair candidate.yaml so it satisfies the fixed schema.",
            "command": "ams schema candidate --json",
            "reason": str(exc),
        }
    if not report.valid:
        return {
            "stage": "candidate_contract",
            "status": "needs_work",
            "next_action": "Repair candidate declarations and required validation/evaluation metadata.",
            "command": "ams validate --json",
            "issues": [i.model_dump() for i in report.issues],
        }

    source_report = validate_source_alignment(workspace)
    if not source_report.valid:
        return {
            "stage": "source_alignment",
            "status": "needs_work",
            "next_action": "Align candidate source with candidate.yaml declarations.",
            "command": "ams validate --source --json",
            "issues": [i.model_dump() for i in source_report.issues],
        }

    try:
        val = evaluate_candidate(workspace, split="validation", final=False)
    except (EvaluationError, FileNotFoundError, ValidationError) as exc:
        return {
            "stage": "evaluation",
            "status": "needs_work",
            "next_action": "Make the candidate executable against the validation protocol.",
            "command": "ams eval --split validation --json",
            "reason": str(exc),
        }

    if not val["accepted"]:
        return {
            "stage": "evaluation",
            "status": "needs_work",
            "next_action": "Improve the candidate against validation feedback.",
            "command": "ams eval --split validation --json",
            "score": val["score"],
            "minimum_score": val["minimum_score"],
        }

    plan_path = workspace / ".ams" / "optimization-plan.json"
    if not plan_path.exists():
        return {
            "stage": "optimization_baseline",
            "status": "ready",
            "next_action": "Issue and save the external optimization protocol.",
            "command": "ams optimization-plan --json",
            "score": val["score"],
        }

    try:
        plan = load_saved_plan(workspace)
    except OptimizationError as exc:
        return {
            "stage": "optimization_baseline",
            "status": "needs_work",
            "next_action": "Reissue the optimization plan.",
            "command": "ams optimization-plan --json",
            "reason": str(exc),
        }

    return {
        "stage": "external_optimization",
        "status": "ready",
        "next_action": "Optimize the declared LLM-facing targets externally, then submit the candidate for independent verification.",
        "command": "ams verify-optimization --json",
        "targets": [t["id"] for t in plan.get("targets", [])],
        "baseline_validation_score": plan.get("baseline", {}).get("score"),
        "note": "AMS does not perform the LLM optimization.",
    }
