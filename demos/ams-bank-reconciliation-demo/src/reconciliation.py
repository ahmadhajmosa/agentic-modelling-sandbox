from __future__ import annotations
from datetime import date
from itertools import combinations
from tools.recon import balance_proof, normalize_amount

try:
    import dspy
except ImportError:
    dspy = None


if dspy is not None:
    class ReconcileSignature(dspy.Signature):
        bank: list[dict] = dspy.InputField()
        gl: list[dict] = dspy.InputField()
        matched_count: int = dspy.OutputField()
        unmatched_bank_count: int = dspy.OutputField()
        unmatched_gl_count: int = dspy.OutputField()
        validation_passed: bool = dspy.OutputField()


    class Reconcile(dspy.Module):
        signature = ReconcileSignature

        def forward(self, bank: list[dict], gl: list[dict]) -> dict:
            return predict(bank, gl)


def _days(a, b):
    return abs((date.fromisoformat(a)-date.fromisoformat(b)).days)

def _find_subset(items, target_cents, anchor_date, used_ids, max_size=3):
    pool=[x for x in items if x["id"] not in used_ids and _days(x["date"], anchor_date) <= 3]
    for size in range(1, min(max_size, len(pool))+1):
        for combo in combinations(pool, size):
            if sum(normalize_amount(x["amount"]) for x in combo) == target_cents:
                return list(combo)
    return None

def predict(bank: list[dict], gl: list[dict]) -> dict:
    used_bank=set()
    used_gl=set()
    matched_bank=[]
    matched_gl=[]
    groups=0

    # 1) Prefer direct 1:1 matches.
    for b in bank:
        if b["id"] in used_bank:
            continue
        target=normalize_amount(b["amount"])
        candidates=[
            g for g in gl
            if g["id"] not in used_gl
            and normalize_amount(g["amount"]) == target
            and _days(g["date"], b["date"]) <= 3
        ]
        if candidates:
            g=min(candidates,key=lambda x:_days(x["date"],b["date"]))
            used_bank.add(b["id"]); used_gl.add(g["id"])
            matched_bank.append(b["id"]); matched_gl.append(g["id"])
            groups += 1

    # 2) Match one bank settlement to multiple GL lines.
    for b in bank:
        if b["id"] in used_bank:
            continue
        combo=_find_subset(gl, normalize_amount(b["amount"]), b["date"], used_gl)
        if combo and len(combo) > 1:
            used_bank.add(b["id"])
            matched_bank.append(b["id"])
            for g in combo:
                used_gl.add(g["id"]); matched_gl.append(g["id"])
            groups += 1

    # 3) Match multiple bank transactions to one GL line.
    for g in gl:
        if g["id"] in used_gl:
            continue
        combo=_find_subset(bank, normalize_amount(g["amount"]), g["date"], used_bank)
        if combo and len(combo) > 1:
            used_gl.add(g["id"])
            matched_gl.append(g["id"])
            for b in combo:
                used_bank.add(b["id"]); matched_bank.append(b["id"])
            groups += 1

    proof=balance_proof(bank,gl,matched_bank,matched_gl)
    return {
        "matched_count":groups,
        "unmatched_bank_count":len(bank)-len(used_bank),
        "unmatched_gl_count":len(gl)-len(used_gl),
        "validation_passed":proof["passed"],
    }
