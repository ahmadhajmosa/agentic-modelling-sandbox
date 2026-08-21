"""Controls, evidence, and the reconciliation statement.

The balance proof is not recomputed here. It is delegated to the environment's
own ``balance_proof`` capability, so the figure certifying the reconciliation is
produced by the control the environment owns rather than by the process being
checked.
"""

from __future__ import annotations

from tools.recon import balance_proof

from .contracts import BANK, GL, ControlResult, ReconciliationResult, Transaction

try:
    import dspy
except ImportError:
    dspy = None


CONTROL_BALANCE = "balance_reconciles"
CONTROL_EXCEPTIONS_REPORTED = "unmatched_items_reported"


def run_controls(
    bank_raw: list[dict],
    gl_raw: list[dict],
    result: ReconciliationResult,
    unmatched_bank: list[Transaction],
    unmatched_gl: list[Transaction],
) -> tuple[list[ControlResult], dict]:
    """Run the environment's required controls and return their evidence."""
    proof = balance_proof(bank_raw, gl_raw, result.matched_bank_ids, result.matched_gl_ids)

    reported = {item.transaction_id for item in result.exceptions}
    unmatched_ids = {t.id for t in unmatched_bank} | {t.id for t in unmatched_gl}
    outstanding = sorted(unmatched_ids - reported)

    controls = [
        ControlResult(
            name=CONTROL_BALANCE,
            passed=bool(proof["passed"]),
            detail=(
                f"Matched bank {proof['bank_total_cents'] - proof['unmatched_bank_cents']} "
                f"vs matched GL {proof['gl_total_cents'] - proof['unmatched_gl_cents']} (cents)."
            ),
        ),
        ControlResult(
            name=CONTROL_EXCEPTIONS_REPORTED,
            passed=not outstanding,
            detail=(
                "Every unmatched transaction carries a reconciling item."
                if not outstanding
                else f"Unmatched transactions missing an explanation: {outstanding}"
            ),
        ),
    ]
    return controls, proof


if dspy is not None:
    class ControlsSignature(dspy.Signature):
        bank_raw: list[dict] = dspy.InputField()
        gl_raw: list[dict] = dspy.InputField()
        result: ReconciliationResult = dspy.InputField()
        unmatched_bank: list[Transaction] = dspy.InputField()
        unmatched_gl: list[Transaction] = dspy.InputField()
        controls: list[ControlResult] = dspy.OutputField()
        balance_proof: dict = dspy.OutputField()


    class Controls(dspy.Module):
        signature = ControlsSignature

        def forward(
            self,
            bank_raw: list[dict],
            gl_raw: list[dict],
            result: ReconciliationResult,
            unmatched_bank: list[Transaction],
            unmatched_gl: list[Transaction],
        ) -> tuple[list[ControlResult], dict]:
            return run_controls(bank_raw, gl_raw, result, unmatched_bank, unmatched_gl)


def to_payload(result: ReconciliationResult) -> dict:
    """Serialise the result.

    The first four keys are the reconciliation contract the environment scores.
    The remainder is the audit trail a preparer and reviewer actually work from.
    """
    return {
        "matched_count": len(result.matches),
        "unmatched_bank_count": sum(1 for i in result.exceptions if i.source == BANK),
        "unmatched_gl_count": sum(1 for i in result.exceptions if i.source == GL),
        "validation_passed": result.validation_passed,
        "matches": [
            {
                "bank_ids": list(group.bank_ids),
                "gl_ids": list(group.gl_ids),
                "rule": group.rule,
                "amount_cents": group.amount_cents,
                "date_span_days": group.date_span_days,
            }
            for group in result.matches
        ],
        "exceptions": [
            {
                "transaction_id": item.transaction_id,
                "source": item.source,
                "date": item.date,
                "amount_cents": item.amount_cents,
                "description": item.description,
                "category": item.category,
                "explanation": item.explanation,
                "related_ids": list(item.related_ids),
            }
            for item in result.exceptions
        ],
        "controls": [
            {"name": c.name, "passed": c.passed, "detail": c.detail}
            for c in result.controls
        ],
        "balance_proof": result.balance_proof,
    }


def _money(cents: int) -> str:
    return f"{cents / 100:,.2f}"


def format_statement(payload: dict) -> str:
    """Render the reconciliation as a statement a finance reviewer can sign off."""
    proof = payload["balance_proof"]
    lines = [
        "BANK RECONCILIATION STATEMENT",
        "=" * 46,
        f"Bank extract total      {_money(proof['bank_total_cents']):>18}",
        f"Ledger extract total    {_money(proof['gl_total_cents']):>18}",
        "",
        f"Matched settlements     {len(payload['matches']):>18}",
        f"Bank reconciling items  {payload['unmatched_bank_count']:>18}",
        f"Ledger reconciling items{payload['unmatched_gl_count']:>18}",
        "",
        "MATCHED",
        "-" * 46,
    ]
    for group in payload["matches"] or []:
        lines.append(
            f"  {_money(group['amount_cents']):>12}  {group['rule']:<22}"
            f"  {'+'.join(group['bank_ids'])} <-> {'+'.join(group['gl_ids'])}"
        )
    if not payload["matches"]:
        lines.append("  (none)")

    lines += ["", "RECONCILING ITEMS", "-" * 46]
    for item in payload["exceptions"] or []:
        lines.append(
            f"  {_money(item['amount_cents']):>12}  {item['category']:<22}"
            f"  {item['transaction_id']} ({item['source']})"
        )
        lines.append(f"                {item['explanation']}")
    if not payload["exceptions"]:
        lines.append("  (none)")

    lines += ["", "CONTROLS", "-" * 46]
    for control in payload["controls"]:
        lines.append(f"  [{'PASS' if control['passed'] else 'FAIL'}] {control['name']}")
        lines.append(f"         {control['detail']}")

    verdict = "RECONCILED" if payload["validation_passed"] else "NOT RECONCILED"
    lines += ["", f"Result: {verdict}"]
    return "\n".join(lines)
