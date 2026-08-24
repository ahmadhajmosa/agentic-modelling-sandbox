from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import load_model
from .schemas import CandidateManifest, EnvironmentManifest


class EvaluationError(RuntimeError):
    pass


class EvaluationPolicyError(EvaluationError):
    """Raised when the environment's evaluation protocol refuses the request."""


HELD_OUT_LEDGER = "heldout-access.json"


def _consume_held_out_budget(workspace: Path, limit: int | None) -> dict[str, Any]:
    """Record one access to the protected split and enforce the environment's cap."""
    path = workspace / '.ams' / HELD_OUT_LEDGER
    ledger = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'used': 0, 'accesses': []}
    if limit is not None and ledger['used'] >= limit:
        raise EvaluationPolicyError(
            f"Protected held-out budget exhausted: {ledger['used']} of {limit} final "
            "evaluations already used. The held-out split is not available for tuning."
        )
    ledger['used'] += 1
    ledger['accesses'].append(datetime.now(timezone.utc).isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2), encoding='utf-8')
    return {
        'used': ledger['used'],
        'limit': limit,
        'remaining': None if limit is None else limit - ledger['used'],
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise EvaluationError(f"Evaluation dataset not found: {path}")
    rows=[]
    for i,line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise EvaluationError(f"Invalid JSONL at {path}:{i}: {exc}") from exc
    return rows


def _load_entrypoint(workspace: Path, entrypoint: str):
    if ':' not in entrypoint:
        raise EvaluationError("Candidate artifacts.entrypoint must use 'relative/path.py:function'")
    rel, fn_name = entrypoint.split(':', 1)
    target=(workspace / rel).resolve()
    root=workspace.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise EvaluationError("Candidate entrypoint escapes workspace") from exc
    if not target.exists():
        raise EvaluationError(f"Candidate entrypoint file not found: {rel}")
    module_name=f"ams_candidate_{abs(hash(str(target)))}"
    spec=importlib.util.spec_from_file_location(module_name, target)
    if spec is None or spec.loader is None:
        raise EvaluationError(f"Unable to load candidate entrypoint: {rel}")
    module=importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(workspace))
    try:
        spec.loader.exec_module(module)
    finally:
        try: sys.path.remove(str(workspace))
        except ValueError: pass
    fn=getattr(module, fn_name, None)
    if not callable(fn):
        raise EvaluationError(f"Entrypoint function '{fn_name}' not found in {rel}")
    return fn


def _load_executable_checks(workspace: Path, env: EnvironmentManifest) -> dict[str, Any]:
    """Load the environment-owned validation checks AMS runs itself."""
    from .capabilities import _workspace_import_path

    checks: dict[str, Any] = {}
    declared = env.constraints.validation.executable_checks
    if not declared:
        return checks
    with _workspace_import_path(workspace):
        for name, target in declared.items():
            if ':' not in target:
                raise EvaluationError(
                    f"Executable check '{name}' must use 'module:function', got '{target}'"
                )
            module_name, attr = target.split(':', 1)
            try:
                fn = getattr(importlib.import_module(module_name), attr)
            except (ImportError, AttributeError) as exc:
                raise EvaluationError(f"Could not load executable check '{name}' from '{target}': {exc}") from exc
            if not callable(fn):
                raise EvaluationError(f"Executable check '{name}' target '{target}' is not callable.")
            checks[name] = fn
    return checks


def _run_executable_checks(checks: dict[str, Any], inputs: dict, output: dict) -> dict[str, bool]:
    """Run each environment check against the candidate's actual output."""
    results: dict[str, bool] = {}
    for name, fn in checks.items():
        try:
            outcome = fn(inputs, output)
        except Exception:  # a check that cannot evaluate the output has not passed
            results[name] = False
            continue
        results[name] = bool(outcome.get('passed')) if isinstance(outcome, dict) else bool(outcome)
    return results


def _score_value(actual: Any, expected: Any, tol: float = 1e-6) -> float:
    if isinstance(expected, bool):
        return 1.0 if actual is expected else 0.0
    if isinstance(expected, (int,float)) and isinstance(actual, (int,float)):
        scale=max(1.0, abs(float(expected)))
        err=abs(float(actual)-float(expected))/scale
        # Inside tolerance is full credit; beyond it the score degrades with the error.
        return 1.0 if err <= tol else max(0.0, 1.0-err)
    return 1.0 if actual == expected else 0.0


def _flatten_expected_scores(result: dict[str,Any], expected: dict[str,Any]):
    scores=[]
    for key, exp in expected.items():
        if key not in result:
            scores.append(0.0)
        else:
            scores.append(_score_value(result[key], exp))
    return scores


def evaluate_candidate(workspace: str|Path, split: str='validation', final: bool=False) -> dict[str,Any]:
    workspace=Path(workspace)
    env=load_model(workspace/'environment.yaml', EnvironmentManifest)
    cand=load_model(workspace/'candidate.yaml', CandidateManifest)
    protected = split == 'test' and env.evaluation.protect_test_split
    if protected and not final:
        raise EvaluationPolicyError("Protected test split requires final=true")
    if not cand.artifacts.entrypoint:
        raise EvaluationError("candidate.yaml must declare artifacts.entrypoint for evaluation")
    budget = _consume_held_out_budget(workspace, env.evaluation.max_final_evaluations) if protected else None
    dataset_path=getattr(env.evaluation.datasets, split)
    rows=_load_jsonl(workspace/dataset_path)
    fn=_load_entrypoint(workspace, cand.artifacts.entrypoint)
    checks=_load_executable_checks(workspace, env)

    case_results=[]
    aggregate=[]
    for idx,row in enumerate(rows):
        case_id=row.get('id', f'{split}-{idx}')
        inputs=row.get('input', {})
        expected=row.get('expected', {})
        if not isinstance(inputs, dict) or not isinstance(expected, dict):
            raise EvaluationError(f"Case {case_id} must contain object input and expected fields")
        try:
            output=fn(**inputs)
            if not isinstance(output, dict):
                output={"result": output}
            field_scores=_flatten_expected_scores(output, expected)
            numerical=sum(field_scores)/len(field_scores) if field_scores else 1.0
            contract=sum(1.0 for k in expected if k in output)/len(expected) if expected else 1.0
            # Environment-owned checks are authoritative. Only when the environment
            # declares none does the candidate's self-reported flag count.
            check_results=_run_executable_checks(checks, inputs, output)
            if check_results:
                validation=sum(check_results.values())/len(check_results)
            elif 'validation_passed' in expected:
                validation=1.0 if output.get('validation_passed') == expected['validation_passed'] else 0.0
            else:
                validation=1.0
            metric_values={
                'numerical_accuracy': numerical,
                'contract_compliance': contract,
                'validation_compliance': validation,
            }
            selected=[metric_values[m] for m in env.evaluation.metrics if m in metric_values]
            score=sum(selected)/len(selected) if selected else numerical
            aggregate.append(score)
            case={"id":case_id,"score":score,"metrics":metric_values,"status":"success"}
            if check_results:
                case["checks"]=check_results
            case_results.append(case)
        except Exception as exc:
            aggregate.append(0.0)
            case_results.append({"id":case_id,"score":0.0,"status":"error","error":str(exc)})

    overall=sum(aggregate)/len(aggregate) if aggregate else 0.0
    accepted=env.evaluation.minimum_score is None or overall >= env.evaluation.minimum_score
    report={
        'schema_version':'ams/evaluation-v1',
        'environment':env.environment.name,
        'candidate':cand.candidate_name,
        'split':split,
        'case_count':len(rows),
        'score':overall,
        'minimum_score':env.evaluation.minimum_score,
        'accepted':accepted,
        'metrics':env.evaluation.metrics,
    }
    if not protected:
        report['cases']=case_results
    else:
        report['cases_hidden']=True
        report['held_out_budget']=budget
    return report
