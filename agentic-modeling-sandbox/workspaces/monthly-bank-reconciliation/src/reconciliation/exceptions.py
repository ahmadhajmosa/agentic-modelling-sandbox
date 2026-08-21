"""Classification of unmatched transactions into reconciling items.

An unmatched line is not automatically an error. A bank fee the ledger has not
yet recorded, a payment reversed in the same period, and a cheque that cleared
after period end are all normal and expected; a genuinely unexplained
difference is not. Only the last needs a human, so the process says which is
which instead of reporting one undifferentiated pile of exceptions.
"""

from __future__ import annotations

from .contracts import BANK, GL, ReconcilingItem, Transaction

try:
    import dspy
except ImportError:
    dspy = None


FEE_KEYWORDS = ("FEE", "CHARGE", "COMMISSION", "INTEREST", "SERVICE CHG")

CATEGORY_REVERSAL = "reversal"
CATEGORY_BANK_FEE = "bank_fee"
CATEGORY_TIMING = "timing_difference"
CATEGORY_UNEXPLAINED = "unexplained"


def _looks_like_fee(transaction: Transaction) -> bool:
    upper = transaction.description.upper()
    return transaction.amount_cents < 0 and any(word in upper for word in FEE_KEYWORDS)


def _pair_reversals(
    unmatched: list[Transaction],
    everything: list[Transaction],
) -> dict[str, tuple[str, bool]]:
    """Find lines that cancel each other out within the same extract.

    A payment of 400 and a reversal of -400 net to nothing. Two cases matter and
    they read differently to a reviewer:

    - both lines are unmatched, so the pair simply cancels; and
    - the original already matched to the ledger and only the reversal is
      outstanding, which means the ledger is still carrying an entry the bank
      has since backed out.

    Returns ``id -> (counterpart_id, counterpart_is_also_unmatched)``.
    """
    paired: dict[str, tuple[str, bool]] = {}
    ordered = sorted(unmatched, key=lambda t: (t.date, t.id))

    # Prefer a mutual pair: both sides of the reversal are outstanding.
    for index, candidate in enumerate(ordered):
        if candidate.id in paired or candidate.amount_cents == 0:
            continue
        for other in ordered[index + 1:]:
            if other.id in paired:
                continue
            if other.amount_cents == -candidate.amount_cents:
                paired[candidate.id] = (other.id, True)
                paired[other.id] = (candidate.id, True)
                break

    # Otherwise look for the reversed original among lines that did match.
    unmatched_ids = {t.id for t in unmatched}
    settled = sorted(
        (t for t in everything if t.id not in unmatched_ids),
        key=lambda t: (t.date, t.id),
    )
    claimed: set[str] = set()
    for candidate in ordered:
        if candidate.id in paired or candidate.amount_cents == 0:
            continue
        for other in settled:
            if other.id in claimed:
                continue
            if other.amount_cents == -candidate.amount_cents:
                paired[candidate.id] = (other.id, False)
                claimed.add(other.id)
                break
    return paired


def classify(
    unmatched_bank: list[Transaction],
    unmatched_gl: list[Transaction],
    all_bank: list[Transaction] | None = None,
    all_gl: list[Transaction] | None = None,
) -> list[ReconcilingItem]:
    """Explain every unmatched line on both sides."""
    items: list[ReconcilingItem] = []
    reversals = {
        BANK: _pair_reversals(unmatched_bank, all_bank if all_bank is not None else unmatched_bank),
        GL: _pair_reversals(unmatched_gl, all_gl if all_gl is not None else unmatched_gl),
    }
    opposite = {BANK: unmatched_gl, GL: unmatched_bank}

    for source, transactions in ((BANK, unmatched_bank), (GL, unmatched_gl)):
        for transaction in sorted(transactions, key=lambda t: (t.date, t.id)):
            pair = reversals[source].get(transaction.id)
            if pair:
                counterpart, counterpart_outstanding = pair
                category = CATEGORY_REVERSAL
                explanation = (
                    f"Cancels against {counterpart} in the same {source} extract; "
                    "the pair nets to zero."
                    if counterpart_outstanding
                    else (
                        f"Reverses {counterpart}, which already matched to the other "
                        "side; the reversing entry still needs to be posted there."
                    )
                )
                related = (counterpart,)
            elif source == BANK and _looks_like_fee(transaction):
                category = CATEGORY_BANK_FEE
                explanation = (
                    "Bank-originated charge with no ledger entry; post to the "
                    "general ledger to clear."
                )
                related = ()
            else:
                same_value = [
                    other.id
                    for other in opposite[source]
                    if other.amount_cents == transaction.amount_cents
                ]
                if same_value:
                    category = CATEGORY_TIMING
                    explanation = (
                        "Same value exists on the other side but outside the "
                        "matching window; likely a timing difference."
                    )
                    related = tuple(sorted(same_value))
                else:
                    category = CATEGORY_UNEXPLAINED
                    explanation = "No corresponding entry found; requires investigation."
                    related = ()

            items.append(ReconcilingItem(
                transaction_id=transaction.id,
                source=source,
                date=transaction.date,
                amount_cents=transaction.amount_cents,
                description=transaction.description,
                category=category,
                explanation=explanation,
                related_ids=related,
            ))
    return items


if dspy is not None:
    class ExceptionClassificationSignature(dspy.Signature):
        unmatched_bank: list[Transaction] = dspy.InputField()
        unmatched_gl: list[Transaction] = dspy.InputField()
        all_bank: list[Transaction] = dspy.InputField()
        all_gl: list[Transaction] = dspy.InputField()
        exceptions: list[ReconcilingItem] = dspy.OutputField()


    class ExceptionClassification(dspy.Module):
        signature = ExceptionClassificationSignature

        def forward(
            self,
            unmatched_bank: list[Transaction],
            unmatched_gl: list[Transaction],
            all_bank: list[Transaction],
            all_gl: list[Transaction],
        ) -> list[ReconcilingItem]:
            return classify(unmatched_bank, unmatched_gl, all_bank, all_gl)
