from pathlib import Path

from ams.dspy_inspector import inspect_candidate
from ams.templates import ENVIRONMENT_TEMPLATE, CANDIDATE_TEMPLATE
from ams.io import dump_yaml
from ams.validation import validate_source_alignment


DSPY_SOURCE = """
import dspy

class Interpret(dspy.Signature):
    request: str = dspy.InputField()
    scenario: str = dspy.OutputField()

class Program(dspy.Module):
    def __init__(self):
        super().__init__()
        self.example_interpreter = dspy.Predict(Interpret)

class FundedRatioSignature(dspy.Signature):
    asset_value: float = dspy.InputField()
    liability_value: float = dspy.InputField()
    funded_ratio: float = dspy.OutputField()

class FundedRatio(dspy.Module):
    signature = FundedRatioSignature

    def forward(self, asset_value: float, liability_value: float):
        return {"funded_ratio": asset_value / liability_value}
"""


def make_workspace(tmp_path: Path):
    dump_yaml(ENVIRONMENT_TEMPLATE, tmp_path / "environment.yaml")
    dump_yaml(CANDIDATE_TEMPLATE, tmp_path / "candidate.yaml")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "program.py").write_text(DSPY_SOURCE)


def test_inspector_discovers_boundary_and_signature(tmp_path):
    make_workspace(tmp_path)
    report = inspect_candidate(tmp_path)
    assert report["boundaries"][0]["id"] == "example_interpreter"
    assert report["boundaries"][0]["implementation"] == "dspy.Predict"
    assert report["boundaries"][0]["signature"] == "Interpret"
    assert report["signatures"][0]["inputs"] == ["request"]
    assert report["signatures"][0]["outputs"] == ["scenario"]
    assert report["modules"][1]["name"] == "FundedRatio"
    assert report["modules"][1]["signature"] == "FundedRatioSignature"


def test_source_alignment_passes_for_declared_boundary(tmp_path):
    make_workspace(tmp_path)
    report = validate_source_alignment(tmp_path)
    assert report.valid, report.model_dump()


def test_undeclared_boundary_is_rejected(tmp_path):
    make_workspace(tmp_path)
    p = tmp_path / "src" / "program.py"
    p.write_text(DSPY_SOURCE + "\nextra = dspy.ChainOfThought(Interpret)\n")
    report = validate_source_alignment(tmp_path)
    assert not report.valid
    assert any(i.rule == "UNDECLARED_LLM_BOUNDARY" for i in report.issues)


def test_declared_missing_boundary_is_rejected(tmp_path):
    make_workspace(tmp_path)
    (tmp_path / "src" / "program.py").write_text("def deterministic(): return 1\n")
    report = validate_source_alignment(tmp_path)
    assert not report.valid
    assert any(i.rule == "DECLARED_LLM_BOUNDARY_NOT_FOUND" for i in report.issues)


def test_implementation_mismatch_is_rejected(tmp_path):
    make_workspace(tmp_path)
    p = tmp_path / "src" / "program.py"
    p.write_text(DSPY_SOURCE.replace("dspy.Predict(Interpret)", "dspy.ChainOfThought(Interpret)"))
    report = validate_source_alignment(tmp_path)
    assert not report.valid
    assert any(i.rule == "LLM_IMPLEMENTATION_MISMATCH" for i in report.issues)


def test_missing_declared_deterministic_dspy_module_is_rejected(tmp_path):
    make_workspace(tmp_path)
    p = tmp_path / "src" / "program.py"
    p.write_text(DSPY_SOURCE.replace("class FundedRatio(dspy.Module):", "class WrongName(dspy.Module):"))
    report = validate_source_alignment(tmp_path)
    assert not report.valid
    assert any(i.rule == "DECLARED_DSPY_MODULE_NOT_FOUND" for i in report.issues)


def test_untyped_deterministic_dspy_signature_is_rejected(tmp_path):
    make_workspace(tmp_path)
    p = tmp_path / "src" / "program.py"
    p.write_text("""
import dspy

class Interpret(dspy.Signature):
    request: str = dspy.InputField()
    scenario: str = dspy.OutputField()

class Program(dspy.Module):
    def __init__(self):
        super().__init__()
        self.example_interpreter = dspy.Predict(Interpret)

class FundedRatioSignature(dspy.Signature):
    pass

class FundedRatio(dspy.Module):
    signature = FundedRatioSignature
""")
    report = validate_source_alignment(tmp_path)
    assert not report.valid
    assert any(i.rule == "DSPY_SIGNATURE_UNTYPED" for i in report.issues)


def test_control_flow_cannot_name_undeclared_component(tmp_path):
    make_workspace(tmp_path)
    data = CANDIDATE_TEMPLATE.copy()
    data["decomposition"] = CANDIDATE_TEMPLATE["decomposition"].copy()
    data["decomposition"]["control_flow"] = "example_interpreter -> ghost"
    dump_yaml(data, tmp_path / "candidate.yaml")
    report = validate_source_alignment(tmp_path)
    assert not report.valid
    assert any(i.rule == "CONTROL_FLOW_UNKNOWN_COMPONENT" for i in report.issues)


def test_inspection_does_not_import_or_execute_candidate(tmp_path):
    make_workspace(tmp_path)
    marker = tmp_path / "executed.txt"
    p = tmp_path / "src" / "program.py"
    p.write_text(DSPY_SOURCE + f'\\nopen({str(marker)!r}, "w").write("bad")\\n')
    inspect_candidate(tmp_path)
    assert not marker.exists()
