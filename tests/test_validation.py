import copy
from pathlib import Path

from ams.io import dump_yaml
from ams.templates import ENVIRONMENT_TEMPLATE, CANDIDATE_TEMPLATE
from ams.validation import validate_candidate


def setup_workspace(tmp_path: Path, candidate=None):
    dump_yaml(ENVIRONMENT_TEMPLATE, tmp_path / "environment.yaml")
    dump_yaml(candidate or CANDIDATE_TEMPLATE, tmp_path / "candidate.yaml")


def test_valid_candidate_passes(tmp_path):
    setup_workspace(tmp_path)
    report = validate_candidate(tmp_path / "environment.yaml", tmp_path / "candidate.yaml")
    assert report.valid


def test_missing_required_validation_check_fails(tmp_path):
    candidate = copy.deepcopy(CANDIDATE_TEMPLATE)
    candidate["validation"]["checks"] = []
    setup_workspace(tmp_path, candidate)
    report = validate_candidate(tmp_path / "environment.yaml", tmp_path / "candidate.yaml")
    assert not report.valid
    assert any(i.rule == "REQUIRED_VALIDATION_CHECK" for i in report.issues)


def test_missing_llm_metric_fails(tmp_path):
    candidate = copy.deepcopy(CANDIDATE_TEMPLATE)
    candidate["decomposition"]["llm_modules"][0]["evaluation_metric"] = None
    candidate["evaluation"]["module_metrics"] = {}
    setup_workspace(tmp_path, candidate)
    report = validate_candidate(tmp_path / "environment.yaml", tmp_path / "candidate.yaml")
    assert not report.valid
    assert any(i.rule == "LLM_MODULE_EVALUATION" for i in report.issues)


def test_deterministic_component_requires_typed_dspy_contract(tmp_path):
    candidate = copy.deepcopy(CANDIDATE_TEMPLATE)
    component = candidate["decomposition"]["deterministic_components"][0]
    component["signature"] = None
    component["inputs"] = []
    setup_workspace(tmp_path, candidate)
    report = validate_candidate(tmp_path / "environment.yaml", tmp_path / "candidate.yaml")
    assert not report.valid
    assert any(i.rule == "DETERMINISTIC_TYPED_CONTRACT" for i in report.issues)


def test_control_flow_references_declared_components(tmp_path):
    candidate = copy.deepcopy(CANDIDATE_TEMPLATE)
    candidate["decomposition"]["control_flow"] = "example_interpreter -> ghost"
    setup_workspace(tmp_path, candidate)
    report = validate_candidate(tmp_path / "environment.yaml", tmp_path / "candidate.yaml")
    assert not report.valid
    assert any(i.rule == "CONTROL_FLOW_UNKNOWN_COMPONENT" for i in report.issues)
