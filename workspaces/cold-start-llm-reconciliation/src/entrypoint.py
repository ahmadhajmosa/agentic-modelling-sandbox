from __future__ import annotations

from itertools import combinations
import re
from typing import Any

from tools.recon import balance_proof, date_distance, normalize_amount

try:
    import dspy
except ImportError:
    dspy = None


DATE_TOLERANCE_DAYS = 3
MAX_GROUP_SIZE = 4


class Txn:
    def __init__(
        self,
        id: str,
        source: str,
        date: str,
        amount: float,
        amount_cents: int,
        description: str,
        tokens: frozenset[str],
        refs: frozenset[str],
    ) -> None:
        self.id = id
        self.source = source
        self.date = date
        self.amount = amount
        self.amount_cents = amount_cents
        self.description = description
        self.tokens = tokens
        self.refs = refs


SYNONYMS = {
    "strp": "stripe",
    "stripe": "stripe",
    "shop": "shopify",
    "shopify": "shopify",
    "inv": "invoice",
    "invoice": "invoice",
    "ord": "order",
    "order": "order",
    "chg": "charge",
    "fee": "fee",
}


if dspy is not None:
    class MemoInterpretationSignature(dspy.Signature):
        bank_description: str = dspy.InputField()
        gl_descriptions: list[str] = dspy.InputField()
        normalized_entities: list[str] = dspy.OutputField()
        references: list[str] = dspy.OutputField()
        exception_category: str = dspy.OutputField()


    class ReconciliationProgram(dspy.Module):
        def __init__(self):
            super().__init__()
            self.memo_interpreter = dspy.Predict(MemoInterpretationSignature)


    class TransactionNormalizerSignature(dspy.Signature):
        value: float = dspy.InputField()
        amount_cents: int = dspy.OutputField()


    class TransactionNormalizer(dspy.Module):
        signature = TransactionNormalizerSignature

        def forward(self, value: float) -> dict[str, int]:
            return {"amount_cents": normalize_amount(value)}


    class DateWindowSignature(dspy.Signature):
        bank_date: str = dspy.InputField()
        gl_date: str = dspy.InputField()
        days: int = dspy.OutputField()


    class DateWindow(dspy.Module):
        signature = DateWindowSignature

        def forward(self, bank_date: str, gl_date: str) -> dict[str, int]:
            return {"days": date_distance(bank_date, gl_date)}


    class MatchEngineSignature(dspy.Signature):
        bank: list[dict] = dspy.InputField()
        gl: list[dict] = dspy.InputField()
        matches: list[dict] = dspy.OutputField()
        exceptions: list[dict] = dspy.OutputField()


    class MatchEngine(dspy.Module):
        signature = MatchEngineSignature

        def forward(self, bank: list[dict], gl: list[dict]) -> dict[str, Any]:
            result = predict({"bank": bank, "gl": gl})
            return {"matches": result["matches"], "exceptions": result["exceptions"]}


    class BalanceControlSignature(dspy.Signature):
        bank: list[dict] = dspy.InputField()
        gl: list[dict] = dspy.InputField()
        matched_bank_ids: list[str] = dspy.InputField()
        matched_gl_ids: list[str] = dspy.InputField()
        passed: bool = dspy.OutputField()
        totals: dict = dspy.OutputField()


    class BalanceControl(dspy.Module):
        signature = BalanceControlSignature

        def forward(
            self,
            bank: list[dict],
            gl: list[dict],
            matched_bank_ids: list[str],
            matched_gl_ids: list[str],
        ) -> dict[str, Any]:
            proof = balance_proof(bank, gl, matched_bank_ids, matched_gl_ids)
            return {"passed": proof["passed"], "totals": proof}


def predict(payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    data = payload or kwargs
    if "input" in data and isinstance(data["input"], dict):
        data = data["input"]

    bank_raw = list(data.get("bank", []))
    gl_raw = list(data.get("gl", []))
    bank = [_txn(row, "bank") for row in bank_raw]
    gl = [_txn(row, "gl") for row in gl_raw]

    matches: list[dict[str, Any]] = []
    used_bank: set[str] = set()
    used_gl: set[str] = set()

    _add_semantic_remittance_splits(bank, gl, used_bank, used_gl, matches)
    _add_one_to_one_matches(bank, gl, used_bank, used_gl, matches)
    _add_group_matches(bank, gl, used_bank, used_gl, matches)

    exceptions = [
        _exception(txn, bank, gl)
        for txn in bank + gl
        if txn.id not in (used_bank if txn.source == "bank" else used_gl)
    ]

    proof = balance_proof(bank_raw, gl_raw, sorted(used_bank), sorted(used_gl))
    return {
        "matches": matches,
        "exceptions": exceptions,
        "matched_count": len(matches),
        "unmatched_bank_count": sum(1 for txn in bank if txn.id not in used_bank),
        "unmatched_gl_count": sum(1 for txn in gl if txn.id not in used_gl),
        "validation_passed": bool(proof["passed"]),
        "validation": {
            "balance_reconciles": bool(proof["passed"]),
            "unmatched_items_reported": True,
            "balance_proof": proof,
        },
        "evidence": {
            "bank_total_cents": proof["bank_total_cents"],
            "gl_total_cents": proof["gl_total_cents"],
            "matched_bank_cents": proof["bank_total_cents"] - proof["unmatched_bank_cents"],
            "matched_gl_cents": proof["gl_total_cents"] - proof["unmatched_gl_cents"],
            "reconciling_bank_cents": proof["unmatched_bank_cents"],
            "reconciling_gl_cents": proof["unmatched_gl_cents"],
        },
    }


def _txn(row: dict[str, Any], source: str) -> Txn:
    description = str(row.get("description", ""))
    return Txn(
        id=str(row["id"]),
        source=source,
        date=str(row["date"]),
        amount=float(row["amount"]),
        amount_cents=normalize_amount(row["amount"]),
        description=description,
        tokens=frozenset(_tokens(description)),
        refs=frozenset(_refs(description)),
    )


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[A-Za-z0-9]+", text.lower())
    return {SYNONYMS.get(token, token) for token in raw if len(token) > 1}


def _refs(text: str) -> set[str]:
    refs: set[str] = set()
    normalized = text.upper()
    for prefix, value in re.findall(r"\b(INV|ORD|RA|REF)[-:\s]*([A-Z]?\d+[A-Z0-9]*)", normalized):
        if prefix != "REF":
            refs.add(value)
    for value in re.findall(r"\b[A-Z]\d{2,}\b|\b\d{3,}\b", normalized):
        refs.add(value)
    return refs


def _add_semantic_remittance_splits(
    bank: list[Txn],
    gl: list[Txn],
    used_bank: set[str],
    used_gl: set[str],
    matches: list[dict[str, Any]],
) -> None:
    for b in bank:
        if b.id in used_bank or not b.refs:
            continue
        candidates = [
            g
            for g in gl
            if g.id not in used_gl
            and g.refs
            and b.refs.intersection(g.refs)
            and date_distance(b.date, g.date) <= DATE_TOLERANCE_DAYS
        ]
        if len(candidates) < 2:
            continue
        for group in _candidate_groups(candidates):
            if sum(g.amount_cents for g in group) == b.amount_cents:
                _record_match([b], group, "semantic_remittance_split", used_bank, used_gl, matches)
                break


def _add_one_to_one_matches(
    bank: list[Txn],
    gl: list[Txn],
    used_bank: set[str],
    used_gl: set[str],
    matches: list[dict[str, Any]],
) -> None:
    while True:
        scored: list[tuple[int, int, str, Txn, Txn]] = []
        for b in bank:
            if b.id in used_bank:
                continue
            for g in gl:
                if g.id in used_gl or b.amount_cents != g.amount_cents:
                    continue
                days = date_distance(b.date, g.date)
                if days > DATE_TOLERANCE_DAYS:
                    continue
                score = _pair_score(b, g)
                if score >= 10:
                    scored.append((score, -days, b.id + g.id, b, g))
        if not scored:
            return
        scored.sort(reverse=True, key=lambda item: (item[0], item[1], item[2]))
        _, _, _, b, g = scored[0]
        rule = "semantic_reference" if _is_semantic_pair(b, g) else "exact" if b.date == g.date else "date_tolerance"
        _record_match([b], [g], rule, used_bank, used_gl, matches)


def _pair_score(bank: Txn, gl: Txn) -> int:
    score = 10 - date_distance(bank.date, gl.date)
    shared_refs = bank.refs.intersection(gl.refs)
    shared_tokens = bank.tokens.intersection(gl.tokens)
    score += 20 * len(shared_refs)
    score += 4 * len(shared_tokens)
    if _semantic_name(bank.tokens).intersection(_semantic_name(gl.tokens)):
        score += 12
    return score


def _is_semantic_pair(bank: Txn, gl: Txn) -> bool:
    return bool(bank.refs.intersection(gl.refs) or _semantic_name(bank.tokens).intersection(_semantic_name(gl.tokens)))


def _semantic_name(tokens: frozenset[str]) -> set[str]:
    return set(tokens).intersection({"stripe", "shopify", "acme"})


def _add_group_matches(
    bank: list[Txn],
    gl: list[Txn],
    used_bank: set[str],
    used_gl: set[str],
    matches: list[dict[str, Any]],
) -> None:
    progress = True
    while progress:
        progress = False
        for b in bank:
            if b.id in used_bank:
                continue
            available_gl = [g for g in gl if g.id not in used_gl and date_distance(b.date, g.date) <= DATE_TOLERANCE_DAYS]
            group = _best_amount_group([b], available_gl)
            if group:
                _record_match([b], group, "aggregation", used_bank, used_gl, matches)
                progress = True
                break
        if progress:
            continue
        for g in gl:
            if g.id in used_gl:
                continue
            available_bank = [b for b in bank if b.id not in used_bank and date_distance(b.date, g.date) <= DATE_TOLERANCE_DAYS]
            group = _best_amount_group([g], available_bank)
            if group:
                _record_match(group, [g], "aggregation", used_bank, used_gl, matches)
                progress = True
                break


def _best_amount_group(anchor: list[Txn], candidates: list[Txn]) -> list[Txn]:
    target = sum(txn.amount_cents for txn in anchor)
    for group in _candidate_groups(candidates):
        if len(group) > 1 and sum(txn.amount_cents for txn in group) == target:
            return list(group)
    return []


def _candidate_groups(candidates: list[Txn]) -> list[tuple[Txn, ...]]:
    ordered = sorted(candidates, key=lambda txn: (txn.date, txn.id))
    groups: list[tuple[Txn, ...]] = []
    for size in range(2, min(MAX_GROUP_SIZE, len(ordered)) + 1):
        groups.extend(combinations(ordered, size))
    return groups


def _record_match(
    bank_group: list[Txn] | tuple[Txn, ...],
    gl_group: list[Txn] | tuple[Txn, ...],
    rule: str,
    used_bank: set[str],
    used_gl: set[str],
    matches: list[dict[str, Any]],
) -> None:
    bank_ids = sorted(txn.id for txn in bank_group)
    gl_ids = sorted(txn.id for txn in gl_group)
    used_bank.update(bank_ids)
    used_gl.update(gl_ids)
    dates = [txn.date for txn in list(bank_group) + list(gl_group)]
    matches.append(
        {
            "bank_ids": bank_ids,
            "gl_ids": gl_ids,
            "rule": rule,
            "amount_cents": sum(txn.amount_cents for txn in bank_group),
            "date_span_days": date_distance(min(dates), max(dates)),
        }
    )


def _exception(txn: Txn, bank: list[Txn], gl: list[Txn]) -> dict[str, Any]:
    return {
        "transaction_id": txn.id,
        "source": txn.source,
        "date": txn.date,
        "amount_cents": txn.amount_cents,
        "description": txn.description,
        "category": _exception_category(txn),
        "related_ids": _offsetting_related_ids(txn, bank if txn.source == "bank" else gl),
    }


def _exception_category(txn: Txn) -> str:
    tokens = txn.tokens
    if txn.amount_cents < 0 and ({"fee", "charge", "service", "intl", "txn"} & tokens):
        return "bank_fee"
    if "reversal" in tokens or "reverse" in tokens:
        return "reversal"
    if txn.source == "bank":
        return "bank_only"
    return "unexplained"


def _offsetting_related_ids(txn: Txn, same_source: list[Txn]) -> list[str]:
    related = [
        other.id
        for other in same_source
        if other.id != txn.id
        and other.amount_cents + txn.amount_cents == 0
        and date_distance(other.date, txn.date) <= DATE_TOLERANCE_DAYS
    ]
    return sorted(related)
