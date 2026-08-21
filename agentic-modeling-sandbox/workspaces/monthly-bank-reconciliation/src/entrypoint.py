"""AMS evaluation entrypoint.

A thin adapter only: it holds no reconciliation logic, so what the environment
evaluates is the same code path a month-end run uses.
"""

from __future__ import annotations

from src.reconciliation import reconcile, to_payload


def predict(bank: list[dict], gl: list[dict]) -> dict:
    """Reconcile one period and return the result contract plus its evidence."""
    return to_payload(reconcile(bank, gl))
