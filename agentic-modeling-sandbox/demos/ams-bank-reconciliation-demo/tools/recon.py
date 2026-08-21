from __future__ import annotations
from datetime import date

def normalize_amount(value: float) -> int:
    return int(round(float(value) * 100))

def date_distance(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)

def balance_proof(bank: list[dict], gl: list[dict], matched_bank_ids: list[str], matched_gl_ids: list[str]) -> dict:
    bank_total = sum(normalize_amount(x["amount"]) for x in bank)
    gl_total = sum(normalize_amount(x["amount"]) for x in gl)
    unmatched_bank = sum(normalize_amount(x["amount"]) for x in bank if x["id"] not in set(matched_bank_ids))
    unmatched_gl = sum(normalize_amount(x["amount"]) for x in gl if x["id"] not in set(matched_gl_ids))
    # matched portions reconcile iff removing exceptions leaves equal totals
    passed = (bank_total - unmatched_bank) == (gl_total - unmatched_gl)
    return {
        "passed": passed,
        "bank_total_cents": bank_total,
        "gl_total_cents": gl_total,
        "unmatched_bank_cents": unmatched_bank,
        "unmatched_gl_cents": unmatched_gl,
    }
