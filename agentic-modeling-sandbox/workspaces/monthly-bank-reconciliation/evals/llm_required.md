# LLM-required reconciliation challenge cases

This dataset is intentionally outside the official AMS `train`, `validation`,
and protected `test` splits. It demonstrates cases where amount/date rules can
produce a reconciliation that balances while still being wrong at the line or
exception level.

Use it when deciding whether to introduce an LLM boundary such as
`memo_interpreter`.

Expected LLM boundary:

```text
memo_interpreter -> matching -> exception_classification -> controls
```

The LLM boundary should produce structured, reviewable fields such as:

- normalized counterparty
- invoice/order/reference ids
- memo category, for example fee, reversal, remittance advice, payout
- confidence and rationale

The LLM must not certify the reconciliation. It should only interpret messy
memo text. Deterministic modules must still perform matching, exception
classification, and the environment-owned balance proof.

Cases:

- `ambiguous-same-day-same-amount-reference-disambiguation`: identical amounts
  and dates require interpreting `STRP`, `SHOP`, invoice `2044`, and order
  `991` to avoid cross-pairing.
- `abbreviated-bank-charge`: `INTL TXN CHG` should be interpreted as a bank
  charge even though it does not use the existing deterministic fee keywords.
- `remittance-advice-links-split-invoices`: remittance advice `A17/B44` should
  override a tempting same-amount GL line and match a split invoice group.
