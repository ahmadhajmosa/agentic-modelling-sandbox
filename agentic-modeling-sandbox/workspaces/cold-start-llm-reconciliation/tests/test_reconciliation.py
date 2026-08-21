from __future__ import annotations

import json
from pathlib import Path

from src.entrypoint import predict


def _cases(path: str):
    with Path(path).open() as handle:
        for line in handle:
            yield json.loads(line)


def test_validation_fixture_cases_pass():
    for case in _cases("evals/validation.jsonl"):
        result = predict(case["input"])
        expected = case["expected"]
        assert result["matched_count"] == expected["matched_count"], case["id"]
        assert result["unmatched_bank_count"] == expected["unmatched_bank_count"], case["id"]
        assert result["unmatched_gl_count"] == expected["unmatched_gl_count"], case["id"]
        assert result["validation_passed"] is expected["validation_passed"], case["id"]


def test_required_semantic_evidence_is_preserved():
    case = next(c for c in _cases("evals/validation.jsonl") if c["id"] == "remittance-advice-links-split-invoices")
    result = predict(case["input"])
    assert result["matches"][0]["rule"] == "semantic_remittance_split"
    assert result["matches"][0]["gl_ids"] == ["g_alpha", "g_blue"]
    assert result["exceptions"][0]["transaction_id"] == "g_other"
