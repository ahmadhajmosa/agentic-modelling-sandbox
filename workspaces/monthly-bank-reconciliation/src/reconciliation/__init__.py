"""Reusable bank-to-ledger reconciliation.

    from src.reconciliation import reconcile, format_statement, to_payload

    result = reconcile(bank_rows, gl_rows)
    print(format_statement(to_payload(result)))

The process is deterministic: the same two extracts always produce the same
reconciliation, which is what makes the output reviewable and re-runnable.
"""

from __future__ import annotations

from tools.recon import normalize_amount

from .contracts import (
    BANK,
    GL,
    ControlResult,
    MatchGroup,
    ReconcilingItem,
    ReconciliationResult,
    Transaction,
)
from .exceptions import classify
from .matching import (
    DEFAULT_DATE_TOLERANCE_DAYS,
    DEFAULT_MAX_GROUP_SIZE,
    match_transactions,
)
from .report import format_statement, run_controls, to_payload

__all__ = [
    "reconcile",
    "to_payload",
    "format_statement",
    "ReconciliationResult",
    "MatchGroup",
    "ReconcilingItem",
    "ControlResult",
    "Transaction",
    "DEFAULT_DATE_TOLERANCE_DAYS",
]


def _to_transactions(rows: list[dict], source: str) -> list[Transaction]:
    """Normalise an extract into typed transactions with integer-cent amounts."""
    return [
        Transaction(
            id=str(row["id"]),
            date=str(row["date"]),
            # Amount normalisation is the environment's capability, so bank and
            # ledger figures are scaled the same way the controls expect.
            amount_cents=normalize_amount(row["amount"]),
            description=str(row.get("description", "")),
            source=source,
        )
        for row in rows
    ]


def reconcile(
    bank: list[dict],
    gl: list[dict],
    date_tolerance_days: int = DEFAULT_DATE_TOLERANCE_DAYS,
    max_group_size: int = DEFAULT_MAX_GROUP_SIZE,
) -> ReconciliationResult:
    """Reconcile a bank extract against a general-ledger extract.

    ``date_tolerance_days`` is the clearing window: how long a transaction may
    take to appear on the other side and still count as the same event.
    """
    bank_transactions = _to_transactions(bank, BANK)
    gl_transactions = _to_transactions(gl, GL)

    matches, unmatched_bank, unmatched_gl = match_transactions(
        bank_transactions, gl_transactions, date_tolerance_days, max_group_size
    )

    result = ReconciliationResult(matches=matches)
    result.exceptions = classify(
        unmatched_bank, unmatched_gl, bank_transactions, gl_transactions
    )
    result.controls, result.balance_proof = run_controls(
        bank, gl, result, unmatched_bank, unmatched_gl
    )
    return result
