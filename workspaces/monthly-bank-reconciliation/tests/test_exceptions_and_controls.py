"""Reconciling-item classification and the environment's required controls."""

from src.reconciliation import reconcile, to_payload


def tx(id, date, amount, description=""):
    return {"id": id, "date": date, "amount": amount, "description": description}


def categories(payload):
    return {i["transaction_id"]: i["category"] for i in payload["exceptions"]}


def test_bank_fee_is_a_reconciling_item_and_still_reconciles():
    out = to_payload(reconcile(
        [tx("b1", "2026-07-15", 500.0, "Receipt"), tx("b2", "2026-07-15", -15.0, "BANK FEE")],
        [tx("g1", "2026-07-15", 500.0, "Receipt")],
    ))
    assert out["matched_count"] == 1
    assert out["unmatched_bank_count"] == 1
    assert categories(out)["b2"] == "bank_fee"
    # An unposted bank charge is expected; the reconciliation still holds.
    assert out["validation_passed"] is True


def test_reversal_pair_is_linked_and_nets_to_zero():
    out = to_payload(reconcile(
        [tx("b1", "2026-07-10", 400.0, "Payment"), tx("b2", "2026-07-11", -400.0, "REVERSAL")],
        [],
    ))
    assert categories(out) == {"b1": "reversal", "b2": "reversal"}
    related = {i["transaction_id"]: i["related_ids"] for i in out["exceptions"]}
    assert related["b1"] == ["b2"] and related["b2"] == ["b1"]
    assert out["validation_passed"] is True


def test_reversal_of_an_already_matched_payment_is_not_unexplained():
    """The common real case: the payment matched, then the bank reversed it."""
    out = to_payload(reconcile(
        [tx("b1", "2026-07-10", 400.0, "Payment"), tx("b2", "2026-07-11", -400.0, "REVERSAL")],
        [tx("g1", "2026-07-10", 400.0, "Payment")],
    ))
    assert out["matched_count"] == 1
    assert out["unmatched_bank_count"] == 1
    item = next(i for i in out["exceptions"] if i["transaction_id"] == "b2")
    assert item["category"] == "reversal"
    assert item["related_ids"] == ["b1"]
    assert "still needs to be posted" in item["explanation"]


def test_timing_difference_is_distinguished_from_unexplained():
    out = to_payload(reconcile(
        [tx("b1", "2026-07-28", 900.0, "Cheque")],
        [tx("g1", "2026-06-01", 900.0, "Cheque")],
    ))
    assert categories(out) == {"b1": "timing_difference", "g1": "timing_difference"}


def test_unexplained_item_is_flagged_for_investigation():
    out = to_payload(reconcile([tx("b1", "2026-07-01", 77.0, "???")], []))
    assert categories(out)["b1"] == "unexplained"


def test_every_unmatched_line_is_explained():
    out = to_payload(reconcile(
        [tx("b1", "2026-07-01", 10.0), tx("b2", "2026-07-02", 20.0)],
        [tx("g1", "2026-07-01", 30.0)],
    ))
    explained = {i["transaction_id"] for i in out["exceptions"]}
    assert explained == {"b1", "b2", "g1"} or out["matched_count"] == 1


def test_controls_are_reported_by_name():
    out = to_payload(reconcile([tx("b1", "2026-07-01", 100.0)], [tx("g1", "2026-07-01", 100.0)]))
    names = {c["name"] for c in out["controls"]}
    assert names == {"balance_reconciles", "unmatched_items_reported"}
    assert all(c["passed"] for c in out["controls"])


def test_balance_proof_comes_from_the_environment_capability():
    out = to_payload(reconcile(
        [tx("b1", "2026-07-15", 500.0, "Receipt"), tx("b2", "2026-07-15", -15.0, "BANK FEE")],
        [tx("g1", "2026-07-15", 500.0, "Receipt")],
    ))
    proof = out["balance_proof"]
    assert proof["passed"] is True
    assert proof["bank_total_cents"] == 48500
    assert proof["gl_total_cents"] == 50000
    assert proof["unmatched_bank_cents"] == -1500
