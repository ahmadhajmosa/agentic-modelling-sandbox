import json
from pathlib import Path

from typer.testing import CliRunner

from ams.cli import app
from ams.discovery import guide, overview, schema_document, topic_help
from ams.io import dump_yaml
from ams.templates import (
    CANDIDATE_MODEL_TEMPLATE,
    CANDIDATE_TEMPLATE,
    ENVIRONMENT_TEMPLATE,
    PENSION_EVAL_TEMPLATES,
    PENSION_TOOL_TEMPLATES,
)


runner = CliRunner()


def make_workspace(tmp_path: Path):
    dump_yaml(ENVIRONMENT_TEMPLATE, tmp_path / "environment.yaml")
    dump_yaml(CANDIDATE_TEMPLATE, tmp_path / "candidate.yaml")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/model.py").write_text(CANDIDATE_MODEL_TEMPLATE)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_smoke.py").write_text("def test_ok(): assert True\n")
    for rel, content in PENSION_TOOL_TEMPLATES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    for rel, rows in PENSION_EVAL_TEMPLATES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_overview_explains_core_boundary():
    data = overview()
    assert "external LLM agent" in data["principle"]
    assert "generate the candidate modeling code" in data["ams_does_not"]


def test_decomposition_help_is_non_prescriptive():
    data = topic_help("decomposition")
    assert data["examples_are_prescriptive"] is False
    assert len(data["examples"]) >= 3


def test_candidate_schema_is_real_json_schema():
    data = schema_document("candidate")
    assert data["title"] == "CandidateManifest"
    assert "properties" in data


def test_action_schema_is_discriminated_union():
    data = schema_document("action")
    assert "oneOf" in data or "anyOf" in data


def test_guide_starts_with_init_for_missing_workspace(tmp_path):
    data = guide(tmp_path)
    assert data["stage"] == "uninitialized"


def test_guide_reaches_optimization_plan_after_valid_candidate(tmp_path):
    make_workspace(tmp_path)
    data = guide(tmp_path)
    assert data["stage"] == "optimization_baseline"
    assert data["command"] == "ams optimization-plan --json"


def test_cli_help_json():
    result = runner.invoke(app, ["help", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["abbreviation"] == "AMS"


def test_cli_schema_json():
    result = runner.invoke(app, ["schema", "candidate", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["title"] == "CandidateManifest"


def test_cli_guide_json(tmp_path):
    make_workspace(tmp_path)
    result = runner.invoke(app, ["guide", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["stage"] == "optimization_baseline"


def test_cli_test_alias_runs_tests(tmp_path):
    make_workspace(tmp_path)
    result = runner.invoke(app, ["test", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["action_type"] == "run_tests"
    assert payload["status"] == "success"
