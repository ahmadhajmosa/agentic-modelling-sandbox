from src.reconciliation import predict

def test_split_payment():
    bank=[{"id":"b1","date":"2026-07-20","amount":300.0,"description":"Settlement"}]
    gl=[
        {"id":"g1","date":"2026-07-20","amount":100.0,"description":"Inv1"},
        {"id":"g2","date":"2026-07-20","amount":200.0,"description":"Inv2"},
    ]
    out=predict(bank,gl)
    assert out["matched_count"] == 1
    assert out["unmatched_bank_count"] == 0
    assert out["unmatched_gl_count"] == 0
    assert out["validation_passed"] is True
