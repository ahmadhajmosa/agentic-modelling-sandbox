"""Challenge dataset documenting where an LLM boundary becomes useful.

These tests are not acceptance tests for the current deterministic candidate.
They verify that the separate llm_required.jsonl cases really expose semantic
gaps that amount/date logic should not pretend to solve.
"""

import json
from pathlib import Path

from src.entrypoint import predict

WORKSPACE = Path(__file__).resolve().parents[1]
DATASET = WORKSPACE / "evals" / "llm_required.jsonl"


def _cases():
    return [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]


def test_llm_required_dataset_is_well_formed():
    cases = _cases()
    assert {case["id"] for case in cases} == {
        "ambiguous-same-day-same-amount-reference-disambiguation",
        "abbreviated-bank-charge",
        "remittance-advice-links-split-invoices",
    }
    for case in cases:
        assert case["llm_reason"]
        assert "bank" in case["input"]
        assert "gl" in case["input"]
        assert case["expected"]["validation_passed"] is True


def test_current_deterministic_candidate_does_not_satisfy_semantic_cases():
    failures = []
    for case in _cases():
        output = predict(**case["input"])
        expected = case["expected"]
        for key in ("matches", "exceptions"):
            if key in expected and output.get(key) != expected[key]:
                failures.append(case["id"])
                break

    assert failures == [
        "ambiguous-same-day-same-amount-reference-disambiguation",
        "abbreviated-bank-charge",
        "remittance-advice-links-split-invoices",
    ]
