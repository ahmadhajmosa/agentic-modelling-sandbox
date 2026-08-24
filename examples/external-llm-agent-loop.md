# External LLM Agent → AMS Loop

This example was executed with an LLM acting **outside AMS** and interacting with AMS through its CLI/action protocol. AMS itself contains no LLM.

## Experiment

1. Initialize a pension modeling environment.
2. External agent writes a deliberately incorrect candidate through `ams act`.
3. Agent requests validation evaluation through the AMS action protocol.
4. AMS returns a score of **0.35**, below the environment acceptance threshold of **0.85**.
5. The external agent interprets the case-level metrics and repairs the candidate.
6. AMS re-evaluates the candidate at **1.00**.
7. `ams test` passes.
8. `ams summary` records the activity and score trend.
9. `ams report` emits a Markdown evidence report.

```text
External LLM Agent
      |
      | write candidate
      v
   ams act
      |
      v
AMS environment
      |
      | score = 0.35 / rejected
      v
External LLM Agent
      |
      | repair code
      v
   ams act
      |
      v
AMS environment
      |
      | score = 1.00 / accepted
      v
Observability report
```

The LLM controls code generation and repair. AMS defines the environment, executes allowed actions, evaluates the candidate, and returns structured observations.
