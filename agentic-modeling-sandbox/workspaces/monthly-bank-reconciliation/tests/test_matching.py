"""Matching rules, one test per rule plus the ordering property."""

from src.reconciliation import reconcile, to_payload


def tx(id, date, amount, description=""):
    return {"id": id, "date": date, "amount": amount, "description": description}


def test_exact_same_day_same_amount():
    out = to_payload(reconcile([tx("b1", "2026-07-01", 100.0)], [tx("g1", "2026-07-01", 100.0)]))
    assert out["matched_count"] == 1
    assert out["matches"][0]["rule"] == "exact"
    assert out["unmatched_bank_count"] == 0
    assert out["unmatched_gl_count"] == 0


def test_date_tolerant_match_within_clearing_window():
    out = to_payload(reconcile([tx("b1", "2026-07-03", 250.0)], [tx("g1", "2026-07-01", 250.0)]))
    assert out["matched_count"] == 1
    assert out["matches"][0]["rule"] == "date_tolerant"
    assert out["matches"][0]["date_span_days"] == 2


def test_no_match_beyond_clearing_window():
    out = to_payload(reconcile([tx("b1", "2026-07-20", 250.0)], [tx("g1", "2026-07-01", 250.0)]))
    assert out["matched_count"] == 0
    assert out["unmatched_bank_count"] == 1
    assert out["unmatched_gl_count"] == 1


def test_split_payment_one_bank_to_many_gl():
    out = to_payload(reconcile(
        [tx("b1", "2026-07-20", 300.0, "Settlement")],
        [tx("g1", "2026-07-20", 100.0, "Inv 1"), tx("g2", "2026-07-20", 200.0, "Inv 2")],
    ))
    assert out["matched_count"] == 1
    assert out["matches"][0]["rule"] == "split_payment"
    assert sorted(out["matches"][0]["gl_ids"]) == ["g1", "g2"]
    assert out["unmatched_gl_count"] == 0


def test_aggregated_settlement_many_bank_to_one_gl():
    out = to_payload(reconcile(
        [tx("b1", "2026-07-25", 120.0, "part 1"), tx("b2", "2026-07-25", 80.0, "part 2")],
        [tx("g1", "2026-07-25", 200.0, "invoice")],
    ))
    assert out["matched_count"] == 1
    assert out["matches"][0]["rule"] == "aggregated_settlement"
    assert sorted(out["matches"][0]["bank_ids"]) == ["b1", "b2"]


def test_equal_amounts_pair_by_exact_date_not_greedily():
    """The ordering property: same-value lines must not cross-pair."""
    out = to_payload(reconcile(
        [tx("b1", "2026-07-10", 100.0, "A"), tx("b2", "2026-07-11", 100.0, "B")],
        [tx("g1", "2026-07-10", 100.0, "A"), tx("g2", "2026-07-11", 100.0, "B")],
    ))
    assert out["matched_count"] == 2
    pairs = sorted((m["bank_ids"][0], m["gl_ids"][0]) for m in out["matches"])
    assert pairs == [("b1", "g1"), ("b2", "g2")]


def test_reconciliation_is_deterministic():
    bank = [tx("b1", "2026-07-10", 100.0), tx("b2", "2026-07-10", 100.0)]
    gl = [tx("g1", "2026-07-10", 100.0), tx("g2", "2026-07-10", 100.0)]
    first = to_payload(reconcile(bank, gl))
    second = to_payload(reconcile(list(reversed(bank)), list(reversed(gl))))
    assert first["matches"] == second["matches"]


def test_amounts_use_integer_cents():
    """0.1 + 0.2 must settle 0.30 exactly."""
    out = to_payload(reconcile(
        [tx("b1", "2026-07-01", 0.30)],
        [tx("g1", "2026-07-01", 0.10), tx("g2", "2026-07-01", 0.20)],
    ))
    assert out["matched_count"] == 1
    assert out["matches"][0]["amount_cents"] == 30
