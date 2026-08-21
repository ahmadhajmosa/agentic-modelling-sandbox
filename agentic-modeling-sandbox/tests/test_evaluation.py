from pathlib import Path
import json

import pytest
from typer.testing import CliRunner

from ams.cli import app
from ams.evaluation import (
    EvaluationError,
    EvaluationPolicyError,
    _score_value,
    evaluate_candidate,
)
from ams.history import load_observations
from ams.io import dump_yaml
from ams.runtime import execute_action
from ams.templates import (
    ENVIRONMENT_TEMPLATE,
    CANDIDATE_TEMPLATE,
    PENSION_TOOL_TEMPLATES,
    PENSION_EVAL_TEMPLATES,
    CANDIDATE_MODEL_TEMPLATE,
)


def setup_workspace(tmp_path: Path):
    dump_yaml(ENVIRONMENT_TEMPLATE, tmp_path / "environment.yaml")
    dump_yaml(CANDIDATE_TEMPLATE, tmp_path / "candidate.yaml")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    for rel, content in PENSION_TOOL_TEMPLATES.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    (tmp_path / "src/model.py").write_text(CANDIDATE_MODEL_TEMPLATE, encoding="utf-8")
    for rel, rows in PENSION_EVAL_TEMPLATES.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(json.dumps(r)+"\n" for r in rows), encoding="utf-8")


def test_validation_evaluation_returns_fitness(tmp_path):
    setup_workspace(tmp_path)
    report = evaluate_candidate(tmp_path, split="validation")
    assert report["score"] == pytest.approx(1.0)
    assert report["accepted"] is True
    assert len(report["cases"]) == 2


def test_protected_test_requires_final(tmp_path):
    setup_workspace(tmp_path)
    with pytest.raises(EvaluationError, match="Protected test split"):
        evaluate_candidate(tmp_path, split="test")


def test_protected_test_hides_case_details(tmp_path):
    setup_workspace(tmp_path)
    report = evaluate_candidate(tmp_path, split="test", final=True)
    assert report["accepted"] is True
    assert report["cases_hidden"] is True
    assert "cases" not in report


def test_candidate_cannot_self_certify_validation(tmp_path):
    setup_workspace(tmp_path)
    # Wrong answer, but the candidate claims its own validation passed.
    (tmp_path / "src/model.py").write_text(
        CANDIDATE_MODEL_TEMPLATE
        + "\n\ndef predict(asset_value: float, liability_value: float) -> dict:\n"
        "    return {'funded_ratio': 0.5, 'validation_passed': True}\n",
        encoding="utf-8",
    )
    report = evaluate_candidate(tmp_path, split="validation")
    for case in report["cases"]:
        assert case["metrics"]["validation_compliance"] == 0.0, case
        assert case["checks"]["funded_ratio_reconciles"] is False


def test_honest_candidate_passes_executable_checks(tmp_path):
    setup_workspace(tmp_path)
    report = evaluate_candidate(tmp_path, split="validation")
    assert report["score"] == pytest.approx(1.0)
    for case in report["cases"]:
        assert case["checks"]["funded_ratio_reconciles"] is True


def test_heldout_report_exposes_remaining_budget(tmp_path):
    setup_workspace(tmp_path)
    report = evaluate_candidate(tmp_path, split="test", final=True)
    assert report["held_out_budget"] == {"used": 1, "limit": 3, "remaining": 2}


def test_heldout_budget_is_exhaustible(tmp_path):
    setup_workspace(tmp_path)
    for _ in range(3):
        evaluate_candidate(tmp_path, split="test", final=True)
    with pytest.raises(EvaluationPolicyError, match="budget"):
        evaluate_candidate(tmp_path, split="test", final=True)


def test_visible_splits_do_not_consume_heldout_budget(tmp_path):
    setup_workspace(tmp_path)
    for _ in range(5):
        evaluate_candidate(tmp_path, split="validation")
    report = evaluate_candidate(tmp_path, split="test", final=True)
    assert report["held_out_budget"]["used"] == 1


def test_exhausted_budget_is_denied_through_the_action_protocol(tmp_path):
    setup_workspace(tmp_path)
    for _ in range(3):
        evaluate_candidate(tmp_path, split="test", final=True)
    obs = execute_action(tmp_path, {"type": "evaluate_candidate", "split": "test", "final": True})
    assert obs.status == "denied"
    assert obs.policy.rule == "EVALUATION_PROTOCOL"
    assert "budget" in obs.policy.message


def test_bad_candidate_gets_lower_reward(tmp_path):
    setup_workspace(tmp_path)
    (tmp_path / "src/model.py").write_text(
        "def predict(asset_value, liability_value):\n    return {'funded_ratio': 0.0, 'validation_passed': False}\n",
        encoding="utf-8",
    )
    report = evaluate_candidate(tmp_path, split="validation")
    assert report["score"] < 0.85
    assert report["accepted"] is False


def test_evaluate_action_records_observation(tmp_path):
    setup_workspace(tmp_path)
    obs = execute_action(tmp_path, {"type": "evaluate_candidate", "split": "validation"})
    assert obs.status == "success"
    assert obs.data["score"] == pytest.approx(1.0)
    history = (tmp_path / ".ams/history.jsonl").read_text(encoding="utf-8")
    assert "evaluate_candidate" in history


def test_cli_eval(tmp_path):
    setup_workspace(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["eval", str(tmp_path), "--split", "validation", "--json"])
    assert result.exit_code == 0
    assert '"score": 1.0' in result.stdout


def test_cli_eval_records_observation(tmp_path):
    setup_workspace(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["eval", str(tmp_path), "--split", "validation", "--json"])
    assert result.exit_code == 0
    history = load_observations(tmp_path)
    assert [o["action_type"] for o in history] == ["evaluate_candidate"]
    assert history[0]["data"]["score"] == pytest.approx(1.0)


def test_cli_eval_records_observation_for_rejected_candidate(tmp_path):
    setup_workspace(tmp_path)
    (tmp_path / "src/model.py").write_text(
        "def predict(asset_value, liability_value):\n    return {'funded_ratio': 0.0, 'validation_passed': False}\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(app, ["eval", str(tmp_path), "--split", "validation", "--json"])
    assert result.exit_code == 1
    history = load_observations(tmp_path)
    assert history[-1]["action_type"] == "evaluate_candidate"
    assert history[-1]["data"]["accepted"] is False


def test_value_inside_tolerance_scores_full_credit():
    # 100.00005 is a relative error of 5e-7, inside the 1e-6 default tolerance.
    assert _score_value(100.00005, 100.0) == pytest.approx(1.0)


def test_score_never_rewards_a_larger_error():
    # A more accurate answer must never score worse than a less accurate one.
    actuals = [100.0, 100.00001, 100.00005, 100.0001, 100.001, 100.1, 150.0, 200.0]
    scores = [_score_value(a, 100.0) for a in actuals]
    assert scores == sorted(scores, reverse=True), dict(zip(actuals, scores))
