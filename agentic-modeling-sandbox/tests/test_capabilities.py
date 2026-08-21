from pathlib import Path

from typer.testing import CliRunner

from ams.cli import app
from ams.io import dump_yaml
from ams.runtime import execute_action
from ams.templates import ENVIRONMENT_TEMPLATE, CANDIDATE_TEMPLATE, PENSION_TOOL_TEMPLATES


def setup_workspace(tmp_path: Path):
    dump_yaml(ENVIRONMENT_TEMPLATE, tmp_path / "environment.yaml")
    dump_yaml(CANDIDATE_TEMPLATE, tmp_path / "candidate.yaml")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    for rel, content in PENSION_TOOL_TEMPLATES.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def test_declared_capability_invocation(tmp_path):
    setup_workspace(tmp_path)
    obs = execute_action(tmp_path, {
        "type": "invoke_capability",
        "capability": "calculate_funded_ratio",
        "arguments": {"asset_value": 90.0, "liability_value": 100.0},
    })
    assert obs.status == "success"
    assert obs.data["result"]["funded_ratio"] == 0.9
    assert obs.data["deterministic"] is True


def test_undeclared_capability_is_denied(tmp_path):
    setup_workspace(tmp_path)
    obs = execute_action(tmp_path, {
        "type": "invoke_capability",
        "capability": "delete_everything",
        "arguments": {},
    })
    assert obs.status == "denied"
    assert obs.policy.rule == "CAPABILITY_REGISTRY"


def test_bad_capability_arguments_are_structured_error(tmp_path):
    setup_workspace(tmp_path)
    obs = execute_action(tmp_path, {
        "type": "invoke_capability",
        "capability": "calculate_funded_ratio",
        "arguments": {"asset_value": 100.0},
    })
    assert obs.status == "error"
    assert "liability_value" in obs.policy.message


def test_pension_capabilities_compose_through_actions(tmp_path):
    setup_workspace(tmp_path)
    liabilities = execute_action(tmp_path, {
        "type": "invoke_capability",
        "capability": "project_liabilities",
        "arguments": {"cashflows": [50.0, 50.0], "discount_rate": 0.05},
    })
    assets = execute_action(tmp_path, {
        "type": "invoke_capability",
        "capability": "value_assets",
        "arguments": {"market_values": [40.0, 60.0]},
    })
    ratio = execute_action(tmp_path, {
        "type": "invoke_capability",
        "capability": "calculate_funded_ratio",
        "arguments": {
            "asset_value": assets.data["result"]["market_value"],
            "liability_value": liabilities.data["result"]["present_value"],
        },
    })
    rec = execute_action(tmp_path, {
        "type": "invoke_capability",
        "capability": "reconcile_funded_ratio",
        "arguments": {
            "asset_value": assets.data["result"]["market_value"],
            "liability_value": liabilities.data["result"]["present_value"],
            "funded_ratio": ratio.data["result"]["funded_ratio"],
        },
    })
    assert all(o.status == "success" for o in [liabilities, assets, ratio, rec])
    assert rec.data["result"]["passed"] is True


def test_capabilities_cli_reports_runtime_signature(tmp_path):
    setup_workspace(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["capabilities", str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert '"available": true' in result.stdout
    assert 'calculate_funded_ratio' in result.stdout
    assert 'asset_value' in result.stdout
