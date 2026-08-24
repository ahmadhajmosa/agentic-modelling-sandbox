ENVIRONMENT_TEMPLATE = {
    "schema_version": "ams/v1",
    "environment": {
        "name": "pension-alm",
        "version": "0.1",
        "description": "Pension funded-status and stress modeling environment",
    },
    "objective": {
        "description": "Build a reusable modeling program for pension funded-status scenario analysis.",
        "success_definition": "Correct, reproducible scenario outputs with required validation controls.",
    },
    "capabilities": [
        {"name": "project_liabilities", "callable": "tools.liabilities:project", "description": "Discount liability cashflows.", "deterministic": True, "tags": ["pension", "liability"]},
        {"name": "value_assets", "callable": "tools.assets:value", "description": "Aggregate asset market values.", "deterministic": True, "tags": ["pension", "assets"]},
        {"name": "shock_assets", "callable": "tools.assets:shock", "description": "Apply a uniform asset-value shock.", "deterministic": True, "tags": ["pension", "assets", "scenario"]},
        {"name": "apply_scenario", "callable": "tools.scenario:apply", "description": "Apply additive shocks to numeric assumptions.", "deterministic": True, "tags": ["scenario"]},
        {"name": "calculate_funded_ratio", "callable": "tools.funding:calculate", "description": "Calculate assets divided by liabilities.", "deterministic": True, "tags": ["pension", "funding"]},
        {"name": "reconcile_funded_ratio", "callable": "tools.funding:reconcile", "description": "Verify funded-ratio arithmetic.", "deterministic": True, "tags": ["validation", "pension"]},
    ],
    "constraints": {
        "execution": {
            "network": False,
            "timeout_seconds": 30,
            "allowed_write_paths": ["src", "tests", "candidate.yaml"],
            "allowed_commands": ["python", "python3", "pytest"],
            "max_output_chars": 20000,
            "max_file_bytes": 200000,
        },
        "decomposition": {
            "require_explicit_llm_boundaries": True,
            "require_typed_contracts": True,
            "require_end_to_end_contract": True,
            "deterministic_calculations_testable": True,
        },
        "validation": {
            "required_checks": ["funded_ratio_reconciles", "assumptions_complete"],
            "executable_checks": {"funded_ratio_reconciles": "tools.funding:check_reconciles"},
        },
    },
    "evaluation": {
        "datasets": {"train": "evals/train.jsonl", "validation": "evals/validation.jsonl", "test": "evals/test.jsonl"},
        "metrics": ["numerical_accuracy", "contract_compliance", "validation_compliance"],
        "minimum_score": 0.85,
        "protect_test_split": True,
        "max_final_evaluations": 3,
    },
}

CANDIDATE_TEMPLATE = {
    "schema_version": "ams/candidate-v1",
    "candidate_name": "candidate-001",
    "decomposition": {
        "description": "Agent-owned decomposition. Replace this example with the actual proposed structure.",
        "llm_modules": [
            {
                "id": "example_interpreter",
                "implementation": "dspy.Predict",
                "inputs": [{"name": "request", "type": "str"}],
                "outputs": [{"name": "scenario", "type": "ScenarioDefinition"}],
                "evaluation_metric": "scenario_accuracy",
                "optimization_target": True,
            }
        ],
        "deterministic_components": [
            {
                "id": "funded_ratio",
                "implementation": "FundedRatio",
                "signature": "FundedRatioSignature",
                "inputs": [
                    {"name": "asset_value", "type": "float"},
                    {"name": "liability_value", "type": "float"},
                ],
                "outputs": [{"name": "funded_ratio", "type": "float"}],
                "callable": "tools.funding:calculate",
                "responsibility": "Calculate funded ratio deterministically.",
            }
        ],
        "control_flow": "example_interpreter -> funded_ratio",
    },
    "validation": {"checks": ["funded_ratio_reconciles", "assumptions_complete"]},
    "evaluation": {
        "end_to_end_metric": "overall_modeling_score",
        "module_metrics": {"example_interpreter": "scenario_accuracy"},
    },
    "optimization": {"targets": ["example_interpreter"], "optimizer": "external", "notes": "AMS verifies; external runtime optimizes."},
    "artifacts": {"source_roots": ["src"], "test_roots": ["tests"], "entrypoint": "src/model.py:predict"},
}

PENSION_TOOL_TEMPLATES = {
    "tools/__init__.py": "\"\"\"Environment-owned deterministic pension modeling capabilities.\"\"\"\n",
    "tools/liabilities.py": '''from __future__ import annotations\n\n\ndef project(cashflows: list[float], discount_rate: float) -> dict:\n    \"\"\"Discount annual liability cash flows at a flat annual rate.\"\"\"\n    if discount_rate <= -1.0:\n        raise ValueError("discount_rate must be greater than -1.0")\n    pv = sum(float(cf) / ((1.0 + float(discount_rate)) ** year) for year, cf in enumerate(cashflows, start=1))\n    return {"present_value": pv, "cashflow_count": len(cashflows), "discount_rate": float(discount_rate)}\n''',
    "tools/assets.py": '''from __future__ import annotations\n\n\ndef value(market_values: list[float]) -> dict:\n    \"\"\"Aggregate asset market values.\"\"\"\n    values = [float(v) for v in market_values]\n    if any(v < 0 for v in values):\n        raise ValueError("market values must be non-negative")\n    return {"market_value": sum(values), "position_count": len(values)}\n\n\ndef shock(market_values: list[float], shock_pct: float) -> dict:\n    \"\"\"Apply a uniform percentage shock to asset market values.\"\"\"\n    factor = 1.0 + float(shock_pct)\n    if factor < 0:\n        raise ValueError("shock_pct cannot reduce values below zero")\n    shocked = [float(v) * factor for v in market_values]\n    return {"market_values": shocked, "market_value": sum(shocked), "shock_pct": float(shock_pct)}\n''',
    "tools/scenario.py": '''from __future__ import annotations\n\n\ndef apply(base: dict, shocks: dict) -> dict:\n    \"\"\"Apply additive scenario shocks to named numeric assumptions.\"\"\"\n    result = dict(base)\n    for key, delta in shocks.items():\n        if key not in result:\n            raise ValueError(f"unknown scenario assumption: {key}")\n        if not isinstance(result[key], (int, float)):\n            raise ValueError(f"assumption '{key}' is not numeric")\n        result[key] = float(result[key]) + float(delta)\n    return result\n''',
    "tools/funding.py": '''from __future__ import annotations\n\n\ndef calculate(asset_value: float, liability_value: float) -> dict:\n    \"\"\"Calculate pension funded ratio.\"\"\"\n    asset_value = float(asset_value)\n    liability_value = float(liability_value)\n    if asset_value < 0:\n        raise ValueError("asset_value must be non-negative")\n    if liability_value <= 0:\n        raise ValueError("liability_value must be positive")\n    return {\n        "asset_value": asset_value,\n        "liability_value": liability_value,\n        "funded_ratio": asset_value / liability_value,\n    }\n\n\ndef reconcile(asset_value: float, liability_value: float, funded_ratio: float, tolerance: float = 1e-9) -> dict:\n    \"\"\"Verify a funded ratio reconciles to assets divided by liabilities.\"\"\"\n    expected = calculate(asset_value, liability_value)["funded_ratio"]\n    difference = abs(expected - float(funded_ratio))\n    return {\n        "passed": difference <= float(tolerance),\n        "expected": expected,\n        "actual": float(funded_ratio),\n        "difference": difference,\n        "tolerance": float(tolerance),\n    }\n\n\ndef check_reconciles(inputs: dict, output: dict) -> dict:\n    \"\"\"Environment-owned check: recompute the funded ratio from the case inputs.\n\n    AMS runs this against whatever the candidate returned, so the candidate\n    cannot certify its own result.\n    \"\"\"\n    if "funded_ratio" not in output:\n        return {"passed": False, "reason": "output is missing funded_ratio"}\n    return reconcile(\n        inputs["asset_value"],\n        inputs["liability_value"],\n        output["funded_ratio"],\n    )\n''',
}


PENSION_EVAL_TEMPLATES = {
    "evals/train.jsonl": [
        {"id": "train-base-1", "input": {"asset_value": 90.0, "liability_value": 100.0}, "expected": {"funded_ratio": 0.9, "validation_passed": True}},
        {"id": "train-base-2", "input": {"asset_value": 100.0, "liability_value": 100.0}, "expected": {"funded_ratio": 1.0, "validation_passed": True}},
    ],
    "evals/validation.jsonl": [
        {"id": "val-underfunded", "input": {"asset_value": 80.0, "liability_value": 100.0}, "expected": {"funded_ratio": 0.8, "validation_passed": True}},
        {"id": "val-overfunded", "input": {"asset_value": 110.0, "liability_value": 100.0}, "expected": {"funded_ratio": 1.1, "validation_passed": True}},
    ],
    "evals/test.jsonl": [
        {"id": "test-hidden-1", "input": {"asset_value": 95.0, "liability_value": 100.0}, "expected": {"funded_ratio": 0.95, "validation_passed": True}},
        {"id": "test-hidden-2", "input": {"asset_value": 120.0, "liability_value": 150.0}, "expected": {"funded_ratio": 0.8, "validation_passed": True}},
    ],
}

CANDIDATE_MODEL_TEMPLATE = """from __future__ import annotations

try:
    import dspy
except ImportError:
    dspy = None

from tools.funding import calculate, reconcile


if dspy is not None:
    class InterpretScenario(dspy.Signature):
        request: str = dspy.InputField()
        scenario: str = dspy.OutputField()


    class PensionModel(dspy.Module):
        def __init__(self):
            super().__init__()
            self.example_interpreter = dspy.Predict(InterpretScenario)


    class FundedRatioSignature(dspy.Signature):
        asset_value: float = dspy.InputField()
        liability_value: float = dspy.InputField()
        funded_ratio: float = dspy.OutputField()


    class FundedRatio(dspy.Module):
        signature = FundedRatioSignature

        def forward(self, asset_value: float, liability_value: float) -> dict:
            return calculate(asset_value, liability_value)


def predict(asset_value: float, liability_value: float) -> dict:
    result = calculate(asset_value, liability_value)
    check = reconcile(asset_value, liability_value, result["funded_ratio"])
    return {
        "funded_ratio": result["funded_ratio"],
        "validation_passed": check["passed"],
    }
"""
