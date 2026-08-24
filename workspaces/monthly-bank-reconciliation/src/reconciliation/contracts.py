"""Typed contracts for the reconciliation process.

Amounts are held in integer cents throughout. Floating point money is a
reconciliation hazard: 0.1 + 0.2 != 0.3, and a penny of drift turns a clean
balance proof into an unexplained difference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

BANK = "bank"
GL = "gl"


@dataclass(frozen=True)
class Transaction:
    """A single line from a bank or general-ledger extract."""

    id: str
    date: str
    amount_cents: int
    description: str
    source: str

    @property
    def as_date(self) -> date:
        return date.fromisoformat(self.date)


@dataclass(frozen=True)
class MatchGroup:
    """One reconciled unit: the bank lines and GL lines that settle each other.

    A group is 1:1 for a simple match, 1:N for a split payment, and N:1 for an
    aggregated settlement. ``matched_count`` in the result counts groups, not
    transactions, because one settlement is one reconciling event.
    """

    bank_ids: tuple[str, ...]
    gl_ids: tuple[str, ...]
    rule: str
    amount_cents: int
    date_span_days: int

    @property
    def is_one_to_one(self) -> bool:
        return len(self.bank_ids) == 1 and len(self.gl_ids) == 1


@dataclass(frozen=True)
class ReconcilingItem:
    """An unmatched transaction, with the reason it did not match.

    Every unmatched line becomes one of these. A count of exceptions is not
    actionable; a categorised exception is.
    """

    transaction_id: str
    source: str
    date: str
    amount_cents: int
    description: str
    category: str
    explanation: str
    related_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ControlResult:
    """The outcome of one environment-required control."""

    name: str
    passed: bool
    detail: str


@dataclass
class ReconciliationResult:
    """The complete outcome of reconciling one period."""

    matches: list[MatchGroup] = field(default_factory=list)
    exceptions: list[ReconcilingItem] = field(default_factory=list)
    controls: list[ControlResult] = field(default_factory=list)
    balance_proof: dict = field(default_factory=dict)

    @property
    def matched_bank_ids(self) -> list[str]:
        return [tid for group in self.matches for tid in group.bank_ids]

    @property
    def matched_gl_ids(self) -> list[str]:
        return [tid for group in self.matches for tid in group.gl_ids]

    @property
    def validation_passed(self) -> bool:
        return all(control.passed for control in self.controls)
