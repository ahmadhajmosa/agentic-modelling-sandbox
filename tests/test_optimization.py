from pathlib import Path

import pytest

from ams.io import dump_yaml
from ams.optimization import (
    OptimizationError,
    optimization_plan,
    save_optimization_plan,
    verify_optimization,
)
from ams.templates import (
    CANDIDATE_MODEL_TEMPLATE,
    CANDIDATE_TEMPLATE,
    ENVIRONMENT_TEMPLATE,
    PENSION_EVAL_TEMPLATES,
    PENSION_TOOL_TEMPLATES,
)


def make_workspace(tmp_path: Path):
    dump_yaml(ENVIRONMENT_TEMPLATE, tmp_path / "environment.yaml")
    dump_yaml(CANDIDATE_TEMPLATE, tmp_path / "candidate.yaml")
    for rel, content in PENSION_TOOL_TEMPLATES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src/model.py").write_text(CANDIDATE_MODEL_TEMPLATE)
    for rel, rows in PENSION_EVAL_TEMPLATES.items():
        import json
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_plan_identifies_external_targets_and_baseline(tmp_path):
    make_workspace(tmp_path)
    plan = optimization_plan(tmp_path)
    assert plan["optimizer_owner"] == "external"
    assert plan["targets"][0]["id"] == "example_interpreter"
    assert plan["baseline"]["score"] == 1.0
    assert plan["datasets"]["test"]["protected"] is True
    assert "path" not in plan["datasets"]["test"]


def test_plan_can_be_saved(tmp_path):
    make_workspace(tmp_path)
    plan = optimization_plan(tmp_path)
    out = save_optimization_plan(tmp_path, plan)
    assert out.exists()


def regress_candidate(tmp_path: Path):
    """Keep the declared DSPy boundary intact but make predict wrong."""
    (tmp_path / "src/model.py").write_text(
        CANDIDATE_MODEL_TEMPLATE
        + "\n\ndef predict(asset_value: float, liability_value: float) -> dict:\n"
        "    return {'funded_ratio': 0.0, 'validation_passed': False}\n"
    )


def test_verification_accepts_maintained_baseline(tmp_path):
    make_workspace(tmp_path)
    save_optimization_plan(tmp_path, optimization_plan(tmp_path))
    report = verify_optimization(tmp_path)
    assert report["validation_delta"] == 0
    assert report["improved_on_validation"] is False
    assert report["accepted"] is True
    assert report["held_out"]["cases_hidden"] is True


def test_verification_rejects_regression(tmp_path):
    make_workspace(tmp_path)
    save_optimization_plan(tmp_path, optimization_plan(tmp_path))
    regress_candidate(tmp_path)
    report = verify_optimization(tmp_path)
    assert report["validation_delta"] < 0
    assert report["improved_on_validation"] is False
    assert report["accepted"] is False


def test_verification_detects_dataset_tampering(tmp_path):
    make_workspace(tmp_path)
    save_optimization_plan(tmp_path, optimization_plan(tmp_path))
    with (tmp_path / "evals/test.jsonl").open("a") as f:
        f.write('{"id":"tamper","input":{"asset_value":1,"liability_value":1},"expected":{"funded_ratio":1}}\\n')
    with pytest.raises(OptimizationError, match="Protected test dataset changed"):
        verify_optimization(tmp_path)
