"""The matching engine.

Passes run in descending order of confidence, and each pass may only claim
transactions no earlier pass took. That ordering is a correctness property, not
a performance choice: two same-value invoices a day apart must be paired by
exact date before any date-tolerant rule is allowed to consider them, or the
engine will cross-pair them and produce a reconciliation that balances while
being wrong at the line level.

Every tie is broken deterministically by transaction id, so the same two
extracts always reconcile the same way and a reviewer can reproduce the result.
"""

from __future__ import annotations

from itertools import combinations

from .contracts import BANK, GL, MatchGroup, Transaction

try:
    import dspy
except ImportError:
    dspy = None


DEFAULT_DATE_TOLERANCE_DAYS = 3
DEFAULT_MAX_GROUP_SIZE = 4

# Subset search is combinatorial. On a real month-end extract a three-day window
# can hold hundreds of lines, and C(300, 4) is ~330 million combinations, so the
# candidate pool is capped at the nearest-dated lines. Raising this trades run
# time for the ability to find larger split settlements in dense periods.
SUBSET_CANDIDATE_LIMIT = 24


def _days_apart(left: Transaction, right: Transaction) -> int:
    return abs((left.as_date - right.as_date).days)


def _span(transactions: list[Transaction]) -> int:
    dates = [t.as_date for t in transactions]
    return (max(dates) - min(dates)).days


class _Pool:
    """Tracks which transactions are still unclaimed."""

    def __init__(self, bank: list[Transaction], gl: list[Transaction]):
        self._by_source = {BANK: list(bank), GL: list(gl)}
        self._claimed: set[tuple[str, str]] = set()

    def available(self, source: str) -> list[Transaction]:
        return [t for t in self._by_source[source] if (source, t.id) not in self._claimed]

    def claim(self, transactions: list[Transaction]) -> None:
        for transaction in transactions:
            self._claimed.add((transaction.source, transaction.id))


def _match_one_to_one(pool: _Pool, tolerance: int, same_day_only: bool) -> list[MatchGroup]:
    """Pair a single bank line with a single GL line of the same amount."""
    groups: list[MatchGroup] = []
    for bank_tx in sorted(pool.available(BANK), key=lambda t: (t.date, t.id)):
        if bank_tx not in pool.available(BANK):
            continue
        candidates = [
            gl_tx
            for gl_tx in pool.available(GL)
            if gl_tx.amount_cents == bank_tx.amount_cents
            and (_days_apart(bank_tx, gl_tx) == 0 if same_day_only else _days_apart(bank_tx, gl_tx) <= tolerance)
        ]
        if not candidates:
            continue
        # Nearest date wins; id breaks ties so the result is reproducible.
        gl_tx = min(candidates, key=lambda t: (_days_apart(bank_tx, t), t.id))
        pool.claim([bank_tx, gl_tx])
        groups.append(MatchGroup(
            bank_ids=(bank_tx.id,),
            gl_ids=(gl_tx.id,),
            rule="exact" if same_day_only else "date_tolerant",
            amount_cents=bank_tx.amount_cents,
            date_span_days=_days_apart(bank_tx, gl_tx),
        ))
    return groups


def _find_subset(
    anchor: Transaction,
    pool_side: list[Transaction],
    tolerance: int,
    max_group_size: int,
) -> list[Transaction] | None:
    """Find the smallest set of lines that sums to the anchor within the window."""
    window = [t for t in pool_side if _days_apart(anchor, t) <= tolerance]
    # Keep the nearest-dated candidates, then restore date order so the search
    # itself stays deterministic.
    window.sort(key=lambda t: (_days_apart(anchor, t), t.date, t.id))
    window = window[:SUBSET_CANDIDATE_LIMIT]
    window.sort(key=lambda t: (t.date, t.id))
    for size in range(2, min(max_group_size, len(window)) + 1):
        for combo in combinations(window, size):
            if sum(t.amount_cents for t in combo) == anchor.amount_cents:
                return list(combo)
    return None


def _match_grouped(
    pool: _Pool,
    anchor_source: str,
    counterpart_source: str,
    rule: str,
    tolerance: int,
    max_group_size: int,
) -> list[MatchGroup]:
    """Match one line on one side against several on the other.

    Used for split payments (one bank receipt settling several invoices) and for
    aggregated settlements (several bank lines clearing one GL entry).
    """
    groups: list[MatchGroup] = []
    for anchor in sorted(pool.available(anchor_source), key=lambda t: (t.date, t.id)):
        if anchor not in pool.available(anchor_source):
            continue
        combo = _find_subset(anchor, pool.available(counterpart_source), tolerance, max_group_size)
        if not combo:
            continue
        pool.claim([anchor] + combo)
        bank_side = [anchor] if anchor_source == BANK else combo
        gl_side = combo if anchor_source == BANK else [anchor]
        groups.append(MatchGroup(
            bank_ids=tuple(t.id for t in bank_side),
            gl_ids=tuple(t.id for t in gl_side),
            rule=rule,
            amount_cents=anchor.amount_cents,
            date_span_days=_span([anchor] + combo),
        ))
    return groups


def match_transactions(
    bank: list[Transaction],
    gl: list[Transaction],
    date_tolerance_days: int = DEFAULT_DATE_TOLERANCE_DAYS,
    max_group_size: int = DEFAULT_MAX_GROUP_SIZE,
) -> tuple[list[MatchGroup], list[Transaction], list[Transaction]]:
    """Reconcile two extracts.

    Returns the match groups plus whatever remained unmatched on each side.
    """
    pool = _Pool(bank, gl)
    groups: list[MatchGroup] = []

    # 1. Same amount, same day. Highest confidence, so it claims first.
    groups += _match_one_to_one(pool, date_tolerance_days, same_day_only=True)
    # 2. Same amount within the clearing window.
    groups += _match_one_to_one(pool, date_tolerance_days, same_day_only=False)
    # 3. One bank receipt settling several GL entries.
    groups += _match_grouped(pool, BANK, GL, "split_payment", date_tolerance_days, max_group_size)
    # 4. Several bank lines clearing one GL entry.
    groups += _match_grouped(pool, GL, BANK, "aggregated_settlement", date_tolerance_days, max_group_size)

    return groups, pool.available(BANK), pool.available(GL)


if dspy is not None:
    class MatchingSignature(dspy.Signature):
        bank: list[Transaction] = dspy.InputField()
        gl: list[Transaction] = dspy.InputField()
        matches: list[MatchGroup] = dspy.OutputField()
        unmatched_bank: list[Transaction] = dspy.OutputField()
        unmatched_gl: list[Transaction] = dspy.OutputField()


    class Matching(dspy.Module):
        signature = MatchingSignature

        def forward(
            self,
            bank: list[Transaction],
            gl: list[Transaction],
        ) -> tuple[list[MatchGroup], list[Transaction], list[Transaction]]:
            return match_transactions(bank, gl)
