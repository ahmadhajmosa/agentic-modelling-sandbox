"""Replay every visible environment case as an executable regression test.

The held-out split is deliberately not read here; it belongs to the environment.
"""

import json
from pathlib import Path

import pytest

from src.entrypoint import predict

WORKSPACE = Path(__file__).resolve().parents[1]


def load(split):
    path = WORKSPACE / "evals" / f"{split}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def cases():
    return [
        pytest.param(case, id=f"{split}-{case['id']}")
        for split in ("train", "validation")
        for case in load(split)
    ]


@pytest.mark.parametrize("case", cases())
def test_visible_case_reconciles_as_expected(case):
    output = predict(**case["input"])
    for key, expected in case["expected"].items():
        assert output[key] == expected, (
            f"{case['id']}: {key} was {output[key]}, expected {expected}"
        )


@pytest.mark.parametrize("case", cases())
def test_visible_case_explains_every_unmatched_line(case):
    output = predict(**case["input"])
    matched = {i for m in output["matches"] for i in m["bank_ids"] + m["gl_ids"]}
    all_ids = {t["id"] for t in case["input"]["bank"]} | {t["id"] for t in case["input"]["gl"]}
    explained = {i["transaction_id"] for i in output["exceptions"]}
    assert matched | explained == all_ids
    assert not matched & explained, "a line was both matched and reported as an exception"
