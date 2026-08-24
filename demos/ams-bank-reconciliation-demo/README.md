# AMS Bank Reconciliation — External Agent Demo

This demo exercises Agentic Modeling Sandbox with a realistic accounting workflow.

## Environment

The AMS environment owns:

- bank-to-GL reconciliation objective;
- deterministic amount normalization, date-distance, and balance-proof capabilities;
- execution/write constraints;
- required controls;
- train/validation/test datasets;
- 0.90 minimum acceptance score;
- protected held-out test split.

The candidate is agent-owned.

## External-agent loop

1. The agent inspected `ams guide`, `ams rules`, and `ams capabilities`.
2. It wrote a simple 1:1/date-tolerant reconciliation implementation through `ams act`.
3. Validation score: **0.875 — rejected**.
4. Visible failures were split-payment and many-to-one aggregation cases.
5. The agent refactored the candidate to support bounded subset aggregation.
6. It added an executable reconciliation test.
7. `ams test`: **PASS**.
8. Validation score after repair: **1.000 — accepted**.
9. `ams validate --source`: **PASS**.
10. Protected held-out evaluation: **1.000 — accepted**; individual held-out cases remained hidden in the AMS response.
11. AMS produced the observability report in `ams-report.md`.

## What this demonstrates

The LLM/coding agent owns implementation decisions. AMS provides the environment, allowed actions, controls, evaluation, observations, and evidence.

The demo also uncovered two AMS runtime/observability defects that were fixed in v0.9:

- subprocess tests now receive the candidate workspace on `PYTHONPATH`;
- direct `ams eval` calls are persisted through the action/observation protocol, so evaluation trends appear in reports.
