# Agentic Modeling Sandbox (AMS)

## Final Video Presentation Specification

**Working title:** *Agentic Modeling Sandbox — Putting the Environment Around the AI Agent*

**Target duration:** 8–10 minutes

**Format:** Technical product presentation with live demo

**Audience:**

- AI engineers building coding agents
- Financial modeling professionals
- Banking, accounting, pension, and private market teams
- Technology leaders evaluating AI agent reliability
- Developers using Claude Code, Codex, or similar coding agents

---

# 1. Executive Summary

AI coding agents are becoming remarkably capable at generating Python, SQL, Excel automation, financial models, and accounting workflows.

The problem is no longer whether an agent can write code.

The problem is:

> **Who determines whether the generated financial solution is actually correct?**

Today, that responsibility is usually carried by a human finance professional who repeatedly reviews outputs, checks reconciliations, validates formulas, identifies missing edge cases, and asks the agent to try again.

Agentic Modeling Sandbox (AMS) introduces a different approach.

AMS is **not another AI agent**.

AMS is an **LLM-free execution environment** that surrounds an external coding agent with deterministic rules, capabilities, validation, evaluation, observability, and protected testing.

The agent remains responsible for designing and implementing the solution.

AMS becomes responsible for defining the environment in which that solution must prove itself.

The central thesis of this presentation is:

> **Don't put the LLM inside the framework. Put the framework around the LLM.**

---

# 2. Presentation Objective

By the end of the presentation, the audience should understand:

1. Why financial coding agents require stronger evaluation than prompt engineering alone.
2. How the reinforcement-learning environment analogy inspired AMS.
3. The architectural separation between the external LLM agent and AMS.
4. How AMS enables deterministic validation, evaluation, observability, and optimization protocols.
5. How Claude Code or another coding agent can interact with AMS entirely through the CLI.
6. A complete real-world bank reconciliation example where an external agent improves from a rejected implementation to an accepted one using AMS feedback.

The audience should leave with one clear mental model:

> **The LLM is the policy. AMS is the environment.**

---

# 3. Core Narrative

The presentation follows three acts.

## Act I — The Problem

AI agents can now build financial software.

They generate reconciliation scripts, valuation models, forecasting pipelines, and spreadsheet automation.

However, most workflows still look like this:

> Human explains process → AI writes code → Human checks results → Human finds mistakes → AI rewrites code.

The human has unintentionally become the testing framework.

That does not scale.

---

## Act II — The Idea

Historically, reinforcement learning succeeded because researchers created environments rather than simply smarter agents.

An environment defines:

- states
- allowed actions
- constraints
- transitions
- rewards
- terminal conditions

The policy learns to operate inside that world.

AMS applies the same philosophy to AI coding agents.

Instead of telling Claude exactly how to build a pension model or reconciliation engine, AMS defines the world in which the agent operates.

The agent decides the implementation.

AMS decides how correctness is measured.

---

## Act III — Proof

A realistic bank reconciliation environment is presented.

The external coding agent:

1. discovers the environment,
2. reads rules and capabilities,
3. writes a reconciliation engine,
4. receives structured evaluation feedback,
5. repairs the implementation,
6. passes validation,
7. passes executable tests,
8. passes protected held-out evaluation,
9. generates an observability report.

The demo proves that improvement comes from interacting with the environment rather than receiving another prompt.

---

# 4. Storyboard

## Scene 1 — Opening Hook

**Duration:** 30 seconds

### Narration

> Claude can write a bank reconciliation in Python.
>
> It can automate Excel workflows, generate SQL, build financial models, and write reusable accounting scripts.
>
> But there is one question that matters more than code generation.
>
> **How do we know the solution is actually correct?**

### Visual

Animated sequence:

<svg viewBox="0 0 320 180" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=180 rx=18 fill="#F3F4F6"/>
  <rect x=18 y=38 width=84 height=104 rx=10 fill="#FFFFFF" stroke="#D1D5DB"/>
  <text x=60 y=56 fontSize=10 fontFamily=Arial fill="#374151" textAnchor="middle" fontWeight="bold">
    Finance
  </text>
  <text x=60 y=70 fontSize=8 fontFamily=Arial fill="#6B7280" textAnchor="middle">
    SOP
  </text>
  <text x=60 y=82 fontSize=8 fontFamily=Arial fill="#6B7280" textAnchor="middle">
    Excel
  </text>
  <text x=60 y=94 fontSize=8 fontFamily=Arial fill="#6B7280" textAnchor="middle">
    Rules
  </text>
  <rect x=118 y=52 width=84 height=76 rx=12 fill="#DDEAFE" stroke="#93C5FD"/>
  <text x=160 y=73 fontSize=11 fontFamily=Arial fill="#1D4ED8" textAnchor="middle" fontWeight="bold">
    Claude
  </text>
  <text x=160 y=88 fontSize=8 fontFamily=Arial fill="#1D4ED8" textAnchor="middle">
    Coding Agent
  </text>
  <rect x=218 y=38 width=84 height=104 rx=10 fill="#FFFFFF" stroke="#D1D5DB"/>
  <text x=260 y=56 fontSize=10 fontFamily=Arial fill="#374151" textAnchor="middle" fontWeight="bold">
    Python
  </text>
  <text x=260 y=70 fontSize=8 fontFamily=Arial fill="#6B7280" textAnchor="middle">
    SQL
  </text>
  <text x=260 y=82 fontSize=8 fontFamily=Arial fill="#6B7280" textAnchor="middle">
    Excel
  </text>
  <text x=260 y=94 fontSize=8 fontFamily=Arial fill="#6B7280" textAnchor="middle">
    Models
  </text>
  <path d="M102 90 L118 90" stroke="#64748B" strokeWidth=1.5 strokeDasharray="4 4"/>
  <path d="M202 90 L218 90" stroke="#64748B" strokeWidth=1.5 strokeDasharray="4 4"/>
  <text x=160 y=150 fontSize=11 fontFamily=Arial fill="#DC2626" textAnchor="middle" fontWeight="bold">
    But... who validates it?
  </text>
</svg>

---

## Scene 2 — The Current Reality

**Duration:** 45 seconds

### Narration

Finance professionals are increasingly using AI coding agents for recurring workflows.

Examples include:

- bank reconciliation,
- month-end close automation,
- forecasting models,
- valuation calculations,
- pension liability analysis,
- stress testing,
- spreadsheet generation.

The interesting observation is that the AI often writes the implementation successfully.

The difficult part is verifying whether the implementation satisfies accounting and business rules.

### Visual

<svg viewBox="0 0 320 220" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=220 rx=16 fill="#FFFFFF" stroke="#E5E7EB"/>
  <text x=160 y=22 fontSize=13 fontFamily=Arial fill="#111827" textAnchor="middle" fontWeight="bold">
    Today's workflow
  </text>
  {#each ["Explain process","Generate code","Run workflow","Human reviews","Fix mistakes"] as step, i}
    <rect x=34 y={36+i*34} width=252 height=24 rx=12 fill={i===3 ? "#FDE68A" : "#F3F4F6"} stroke="#D1D5DB"/>
    <circle cx=48 cy={48+i*34} r=8 fill={i===3 ? "#F59E0B" : "#9CA3AF"}/>
    <text x=64 y={52+i*34} fontSize=9 fontFamily=Arial fill="#111827">
      {step}
    </text>
  {/each}
  <path d="M160 194 V204" stroke="#9CA3AF" strokeWidth=1.5 strokeDasharray="4 4"/>
  <path d="M160 204 C120 214, 90 214, 70 194" fill="none" stroke="#EF4444" strokeWidth=1.5 strokeDasharray="4 4"/>
  <text x=170 y=214 fontSize=8 fontFamily=Arial fill="#EF4444">
    Repeat
  </text>
</svg>

### Key Message

The human is acting as the environment.

---

# 5. The Reinforcement Learning Analogy

## Scene 3 — Why Environments Matter

**Duration:** 60 seconds

### Narration

When we trained reinforcement learning agents, we didn't simply improve the neural network.

We designed environments.

Those environments defined:

- what the agent could observe,
- where it could move,
- which actions were allowed,
- what constraints existed,
- and how reward was calculated.

The policy was free to discover strategies.

That separation is the inspiration behind AMS.

### Visual

<svg viewBox="0 0 320 200" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=200 rx=18 fill="#F8FAFC" stroke="#E5E7EB"/>
  <text x=160 y=20 fontSize=13 fontFamily=Arial fill="#111827" textAnchor="middle" fontWeight="bold">
    Reinforcement Learning
  </text>
  <rect x=18 y=36 width=284 height=146 rx=12 fill="#E0F2FE" stroke="#7DD3FC" strokeDasharray="6 4"/>
  <text x=30 y=52 fontSize=10 fontFamily=Arial fill="#0369A1" fontWeight="bold">
    Environment
  </text>
  <rect x=52 y=68 width=52 height=34 rx=8 fill="#FFFFFF" stroke="#64748B"/>
  <text x=78 y=82 fontSize=8 fontFamily=Arial fill="#374151" textAnchor="middle">
    State
  </text>
  <rect x=128 y=68 width=64 height=34 rx=8 fill="#FFFFFF" stroke="#64748B"/>
  <text x=160 y=82 fontSize=8 fontFamily=Arial fill="#374151" textAnchor="middle">
    Actions
  </text>
  <rect x=216 y=68 width=52 height=34 rx=8 fill="#FFFFFF" stroke="#64748B"/>
  <text x=242 y=82 fontSize=8 fontFamily=Arial fill="#374151" textAnchor="middle">
    Reward
  </text>
  <rect x=104 y=124 width=112 height=42 rx=21 fill="#2563EB"/>
  <text x=160 y=141 fontSize=11 fontFamily=Arial fill="#FFFFFF" textAnchor="middle" fontWeight="bold">
    Agent
  </text>
  <text x=160 y=153 fontSize=8 fontFamily=Arial fill="#DBEAFE" textAnchor="middle">
    Policy
  </text>
  <path d="M78 102 V118" stroke="#0EA5E9" strokeWidth=1.5 strokeDasharray="3 3"/>
  <path d="M160 102 V118" stroke="#0EA5E9" strokeWidth=1.5 strokeDasharray="3 3"/>
  <path d="M242 102 V118" stroke="#0EA5E9" strokeWidth=1.5 strokeDasharray="3 3"/>
</svg>

### Transition

> What if we built this same concept for financial coding agents?

---

# 6. Introducing AMS

## Scene 4 — The Core Idea

**Duration:** 60 seconds

### Narration

Agentic Modeling Sandbox is an execution environment for AI-generated financial models and automations.

It contains no embedded LLM.

Instead, it surrounds Claude, Codex, or another external coding agent with deterministic infrastructure.

The agent decides:

- architecture,
- decomposition,
- code,
- abstractions,
- DSPy composition,
- implementation strategy.

AMS decides:

- allowed actions,
- constraints,
- deterministic capabilities,
- validation,
- evaluation,
- observability,
- optimization evidence.

### Visual

<svg viewBox="0 0 320 220" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=220 rx=18 fill="#FFFFFF" stroke="#E5E7EB"/>
  <text x=160 y=20 fontSize=13 fontFamily=Arial fill="#111827" textAnchor="middle" fontWeight="bold">
    Agentic Modeling Sandbox
  </text>
  <rect x=18 y=34 width=284 height=168 rx=14 fill="#ECFEFF" stroke="#06B6D4" strokeWidth=1.5 strokeDasharray="6 4"/>
  <text x=30 y=50 fontSize=10 fontFamily=Arial fill="#0F766E" fontWeight="bold">
    AMS Environment
  </text>
  {#each [
      "Rules","Capabilities","Validation","Evaluation",
      "Held-out Tests","Observability"
    ] as item, i}
    <rect x={30+(i%2)*132} y={62+Math.floor(i/2)*34} width=116 height=24 rx=8 fill="#FFFFFF" stroke="#99F6E4"/>
    <text x={88+(i%2)*132} y={77+Math.floor(i/2)*34} fontSize=8 fontFamily=Arial fill="#115E59" textAnchor="middle">
      {item}
    </text>
  {/each}
  <rect x=94 y=142 width=132 height=44 rx=22 fill="#2563EB"/>
  <text x=160 y=159 fontSize=11 fontFamily=Arial fill="#FFFFFF" textAnchor="middle" fontWeight="bold">
    External LLM
  </text>
  <text x=160 y=171 fontSize=8 fontFamily=Arial fill="#DBEAFE" textAnchor="middle">
    Claude / Codex
  </text>
</svg>

---

# 7. Responsibility Separation

## Scene 5 — Agent vs Environment

**Duration:** 45 seconds

### Narration

This separation is the most important architectural decision.

AMS never prescribes the solution.

For example, if the task is pension modeling, AMS will not say:

> Use ScenarioInterpreter followed by ModelingExecutor.

Instead, the external agent chooses that composition.

AMS only verifies that material LLM boundaries are explicit, contracts exist where required, validation is executable, and evaluation remains independent.

### Visual

<svg viewBox="0 0 320 200" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=200 rx=16 fill="#FFFFFF" stroke="#E5E7EB"/>
  <rect x=16 y=36 width=136 height=148 rx=12 fill="#EFF6FF" stroke="#93C5FD"/>
  <text x=84 y=54 fontSize=11 fontFamily=Arial fill="#1D4ED8" textAnchor="middle" fontWeight="bold">
    External Agent
  </text>
  {#each ["Architecture","Decomposition","Python / SQL","DSPy Modules","Abstractions"] as t,i}
    <text x=30 y={76+i*20} fontSize=9 fontFamily=Arial fill="#1E3A8A">
      • {t}
    </text>
  {/each}
  <rect x=168 y=36 width=136 height=148 rx=12 fill="#ECFDF5" stroke="#86EFAC"/>
  <text x=236 y=54 fontSize=11 fontFamily=Arial fill="#047857" textAnchor="middle" fontWeight="bold">
    AMS
  </text>
  {#each ["Rules","Capabilities","Validation","Evaluation","Observability"] as t,i}
    <text x=182 y={76+i*20} fontSize=9 fontFamily=Arial fill="#065F46">
      • {t}
    </text>
  {/each}
</svg>

### Key Statement

> The agent decides **how**. AMS defines **what success means**.

---

# 8. Self-Describing CLI

## Scene 6 — Discovering the Environment

**Duration:** 60 seconds

### Narration

Another important design decision is that AMS should not require a massive system prompt.

An unfamiliar coding agent should discover the environment by itself.

The CLI exposes everything deterministically.

### Terminal Demonstration

```bash
ams help --json

ams guide --json

ams rules --json

ams capabilities --json

ams schema candidate --json
```

### Visual Layout

Left side:

```text
$ ams guide

Stage:
candidate_contract

Next action:
Validate source alignment
```

Right side:

```text
$ ams capabilities

normalize_amount

date_distance

balance_proof
```

Bottom caption:

> The environment becomes discoverable rather than memorized.

---

# 9. Real Demo Introduction

## Scene 7 — Bank Reconciliation Environment

**Duration:** 45 seconds

### Narration

Now let's move from architecture to proof.

The task is simple to describe but surprisingly difficult to implement correctly.

Build a reusable bank reconciliation engine.

The environment contains:

- bank transactions,
- general ledger transactions,
- deterministic matching utilities,
- reconciliation controls,
- validation datasets,
- hidden held-out scenarios.

The agent receives the objective.

Not the implementation.

### Visual

<svg viewBox="0 0 320 180" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=180 rx=16 fill="#F8FAFC" stroke="#E5E7EB"/>
  <text x=160 y=20 fontSize=13 fontFamily=Arial fill="#111827" textAnchor="middle" fontWeight="bold">
    Bank Reconciliation
  </text>
  <rect x=22 y=40 width=116 height=118 rx=10 fill="#DBEAFE" stroke="#93C5FD"/>
  <text x=80 y=56 fontSize=10 fontFamily=Arial fill="#1D4ED8" textAnchor="middle" fontWeight="bold">
    Bank
  </text>
  {#each ["Deposit 100","Fee -15","Payment 300","Reversal -400"] as row,i}
    <rect x=32 y={68+i*20} width=96 height=14 rx=4 fill="#FFFFFF" opacity=0.9/>
    <text x=36 y={78+i*20} fontSize=6 fontFamily=Arial fill="#1E40AF">
      {row}
    </text>
  {/each}
  <rect x=182 y=40 width=116 height=118 rx=10 fill="#D1FAE5" stroke="#86EFAC"/>
  <text x=240 y=56 fontSize=10 fontFamily=Arial fill="#047857" textAnchor="middle" fontWeight="bold">
    GL
  </text>
  {#each ["Invoice 100","Receipt 500","Inv1 100","Inv2 200"] as row,i}
    <rect x=192 y={68+i*20} width=96 height=14 rx=4 fill="#FFFFFF" opacity=0.9/>
    <text x=196 y={78+i*20} fontSize=6 fontFamily=Arial fill="#065F46">
      {row}
    </text>
  {/each}
  <path d="M138 99 L182 99" stroke="#64748B" strokeWidth=1.5 strokeDasharray="5 4"/>
  <text x=160 y=91 fontSize=7 fontFamily=Arial fill="#374151" textAnchor="middle">
    Match
  </text>
</svg>

---

# 10. The Agent's First Attempt

## Scene 8 — Initial Implementation

**Duration:** 60 seconds

### Narration

The agent first discovers the environment.

Then it writes a perfectly reasonable implementation.

Its logic is:

- match equal amounts,
- allow a three-day date tolerance,
- reconcile matched transactions,
- report unmatched entries.

That sounds correct.

Let's evaluate it.

### Show Code

Only a small excerpt should appear.

```python
for bank_tx in bank:

    candidates = [

        gl_tx for gl_tx in gl

        if same_amount(bank_tx, gl_tx)

        and within_three_days(bank_tx, gl_tx)

    ]

    match_best_candidate()
```

Avoid showing the entire source.

The emphasis is behavior.

---

# 11. AMS Rejects the Candidate

## Scene 9 — Evaluation Failure

**Duration:** 75 seconds

### Narration

AMS evaluates the candidate against validation scenarios owned by the environment.

The result is:

<svg viewBox="0 0 320 140" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=140 rx=16 fill="#FEF2F2" stroke="#FCA5A5"/>
  <text x=160 y=30 fontSize=14 fontFamily=Arial fill="#991B1B" textAnchor="middle" fontWeight="bold">
    Validation Result
  </text>
  <text x=160 y=58 fontSize=28 fontFamily=Arial fill="#DC2626" textAnchor="middle" fontWeight="bold">
    0.875
  </text>
  <text x=160 y=76 fontSize=10 fontFamily=Arial fill="#7F1D1D" textAnchor="middle">
    Required minimum: 0.90
  </text>
  <rect x=70 y=92 width=180 height=28 rx=14 fill="#FEE2E2" stroke="#FCA5A5"/>
  <text x=160 y=110 fontSize=11 fontFamily=Arial fill="#B91C1C" textAnchor="middle" fontWeight="bold">
    REJECTED
  </text>
</svg>

The important part is not the score.

It's the structured observation.

AMS reports that the implementation fails on:

- split payment,
- many-to-one aggregation.

Notice what AMS does **not** say.

It does not say:

> Use recursion.

It does not say:

> Create another module.

It simply exposes where the behavior violates the environment.

### Visual

Two failed scenarios highlighted.

<svg viewBox="0 0 320 150" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=150 rx=14 fill="#FFFFFF" stroke="#E5E7EB"/>
  <text x=160 y=20 fontSize=12 fontFamily=Arial fill="#111827" textAnchor="middle" fontWeight="bold">
    Failed scenarios
  </text>
  <rect x=18 y=36 width=134 height=96 rx=10 fill="#FEE2E2" stroke="#FCA5A5"/>
  <text x=85 y=52 fontSize=9 fontFamily=Arial fill="#991B1B" textAnchor="middle" fontWeight="bold">
    Split Payment
  </text>
  <rect x=30 y=66 width=48 height=18 rx=4 fill="#DBEAFE"/>
  <text x=54 y=78 fontSize=7 fontFamily=Arial fill="#1D4ED8" textAnchor="middle">
    $300
  </text>
  <path d="M78 75 L92 75" stroke="#9CA3AF" strokeWidth=1.5 strokeDasharray="3 3"/>
  <rect x=92 y=60 width=22 height=18 rx=4 fill="#D1FAE5"/>
  <rect x=120 y=84 width=22 height=18 rx=4 fill="#D1FAE5"/>
  <text x=103 y=73 fontSize=6 fontFamily=Arial fill="#047857" textAnchor="middle">
    100
  </text>
  <text x=131 y=97 fontSize=6 fontFamily=Arial fill="#047857" textAnchor="middle">
    200
  </text>
  <text x=85 y=120 fontSize=8 fontFamily=Arial fill="#B91C1C" textAnchor="middle">
    Not matched
  </text>
  <rect x=168 y=36 width=134 height=96 rx=10 fill="#FEE2E2" stroke="#FCA5A5"/>
  <text x=235 y=52 fontSize=9 fontFamily=Arial fill="#991B1B" textAnchor="middle" fontWeight="bold">
    Aggregation
  </text>
  <rect x=180 y=60 width=22 height=18 rx=4 fill="#DBEAFE"/>
  <rect x=208 y=84 width=22 height=18 rx=4 fill="#DBEAFE"/>
  <text x=191 y=73 fontSize=6 fontFamily=Arial fill="#1D4ED8" textAnchor="middle">
    120
  </text>
  <text x=219 y=97 fontSize=6 fontFamily=Arial fill="#1D4ED8" textAnchor="middle">
    80
  </text>
  <path d="M230 75 L244 75" stroke="#9CA3AF" strokeWidth=1.5 strokeDasharray="3 3"/>
  <rect x=244 y=66 width=46 height=18 rx=4 fill="#D1FAE5"/>
  <text x=267 y=78 fontSize=7 fontFamily=Arial fill="#047857" textAnchor="middle">
    $200
  </text>
  <text x=235 y=120 fontSize=8 fontFamily=Arial fill="#B91C1C" textAnchor="middle">
    Not matched
  </text>
</svg>

---

# 12. Agent Improves the Solution

## Scene 10 — Repair Loop

**Duration:** 60 seconds

### Narration

The external agent now receives only observations.

It changes its own implementation.

This time it introduces bounded subset matching.

The architecture evolved because the agent interpreted the environment—not because AMS prescribed the algorithm.

### Visual

<svg viewBox="0 0 320 170" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=170 rx=14 fill="#FFFFFF" stroke="#E5E7EB"/>
  <text x=160 y=20 fontSize=12 fontFamily=Arial fill="#111827" textAnchor="middle" fontWeight="bold">
    Observation → Repair → Re-evaluate
  </text>
  <rect x=18 y=42 width=84 height=92 rx=10 fill="#FEE2E2" stroke="#FCA5A5"/>
  <text x=60 y=58 fontSize=9 fontFamily=Arial fill="#991B1B" textAnchor="middle" fontWeight="bold">
    AMS
  </text>
  <text x=60 y=74 fontSize=7 fontFamily=Arial fill="#7F1D1D" textAnchor="middle">
    Split fails
  </text>
  <text x=60 y=86 fontSize=7 fontFamily=Arial fill="#7F1D1D" textAnchor="middle">
    Aggregate fails
  </text>
  <rect x=118 y=42 width=84 height=92 rx=10 fill="#DBEAFE" stroke="#93C5FD"/>
  <text x=160 y=58 fontSize=9 fontFamily=Arial fill="#1D4ED8" textAnchor="middle" fontWeight="bold">
    Agent
  </text>
  <text x=160 y=74 fontSize=7 fontFamily=Arial fill="#1E40AF" textAnchor="middle">
    Refactors
  </text>
  <text x=160 y=86 fontSize=7 fontFamily=Arial fill="#1E40AF" textAnchor="middle">
    Adds tests
  </text>
  <rect x=218 y=42 width=84 height=92 rx=10 fill="#D1FAE5" stroke="#86EFAC"/>
  <text x=260 y=58 fontSize=9 fontFamily=Arial fill="#047857" textAnchor="middle" fontWeight="bold">
    AMS
  </text>
  <text x=260 y=74 fontSize=7 fontFamily=Arial fill="#065F46" textAnchor="middle">
    Evaluate
  </text>
  <text x=260 y=86 fontSize=7 fontFamily=Arial fill="#065F46" textAnchor="middle">
    Observe
  </text>
  <path d="M102 88 L118 88" stroke="#64748B" strokeWidth=1.5 markerEnd="url(#arrow)"/>
  <path d="M202 88 L218 88" stroke="#64748B" strokeWidth=1.5 markerEnd="url(#arrow)"/>
  <defs>
    <marker id="arrow" markerWidth=6 markerHeight=6 refX=5 refY=3 orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#64748B"/>
    </marker>
  </defs>
</svg>

### Terminal

```bash
ams act write_file

ams test

ams eval --split validation
```

---

# 13. Successful Validation

## Scene 11 — Acceptance

**Duration:** 45 seconds

### Narration

After the repair, AMS evaluates the exact same validation environment.

The result changes from rejection to acceptance.

<svg viewBox="0 0 320 150" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=150 rx=16 fill="#F0FDF4" stroke="#86EFAC"/>
  <text x=160 y=28 fontSize=13 fontFamily=Arial fill="#166534" textAnchor="middle" fontWeight="bold">
    Validation Result
  </text>
  <text x=160 y=68 fontSize=34 fontFamily=Arial fill="#16A34A" textAnchor="middle" fontWeight="bold">
    1.000
  </text>
  <text x=160 y=88 fontSize=10 fontFamily=Arial fill="#166534" textAnchor="middle">
    Minimum required: 0.90
  </text>
  <rect x=84 y=104 width=152 height=28 rx=14 fill="#DCFCE7" stroke="#86EFAC"/>
  <text x=160 y=122 fontSize=11 fontFamily=Arial fill="#166534" textAnchor="middle" fontWeight="bold">
    ACCEPTED
  </text>
</svg>

Then the executable tests pass.

This proves that the candidate is not only scoring correctly—it is also behaving as reusable software.

---

# 14. Protected Held-Out Evaluation

## Scene 12 — Honest Testing

**Duration:** 45 seconds

### Narration

A common mistake in AI evaluation is optimizing against the same examples used for testing.

AMS prevents that.

The held-out dataset belongs to the environment.

The agent can optimize against training and validation.

But final verification happens against protected scenarios.

### Visual

<svg viewBox="0 0 320 180" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=180 rx=16 fill="#FFFFFF" stroke="#E5E7EB"/>
  <text x=160 y=20 fontSize=13 fontFamily=Arial fill="#111827" textAnchor="middle" fontWeight="bold">
    Evaluation Protocol
  </text>
  <rect x=18 y=42 width=86 height=108 rx=10 fill="#DBEAFE" stroke="#93C5FD"/>
  <text x=61 y=58 fontSize=10 fontFamily=Arial fill="#1D4ED8" textAnchor="middle" fontWeight="bold">
    Train
  </text>
  <text x=61 y=78 fontSize=8 fontFamily=Arial fill="#1E40AF" textAnchor="middle">
    Visible
  </text>
  <text x=61 y=92 fontSize=8 fontFamily=Arial fill="#1E40AF" textAnchor="middle">
    Develop
  </text>
  <rect x=117 y=42 width=86 height=108 rx=10 fill="#FDE68A" stroke="#F59E0B"/>
  <text x=160 y=58 fontSize=10 fontFamily=Arial fill="#92400E" textAnchor="middle" fontWeight="bold">
    Validation
  </text>
  <text x=160 y=78 fontSize=8 fontFamily=Arial fill="#92400E" textAnchor="middle">
    Feedback
  </text>
  <text x=160 y=92 fontSize=8 fontFamily=Arial fill="#92400E" textAnchor="middle">
    Improve
  </text>
  <rect x=216 y=42 width=86 height=108 rx=10 fill="#D1FAE5" stroke="#16A34A"/>
  <text x=259 y=58 fontSize=10 fontFamily=Arial fill="#166534" textAnchor="middle" fontWeight="bold">
    Test
  </text>
  <icon name=lock color="#166534" size=xl/>
  <text x=259 y=98 fontSize=8 fontFamily=Arial fill="#166534" textAnchor="middle">
    Protected
  </text>
  <text x=259 y=112 fontSize=8 fontFamily=Arial fill="#166534" textAnchor="middle">
    Final only
  </text>
  <path d="M104 96 L117 96" stroke="#64748B" strokeWidth=1.5 markerEnd="url(#arr2)"/>
  <path d="M203 96 L216 96" stroke="#64748B" strokeWidth=1.5 markerEnd="url(#arr2)"/>
  <defs>
    <marker id="arr2" markerWidth=6 markerHeight=6 refX=5 refY=3 orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#64748B"/>
    </marker>
  </defs>
</svg>

### Terminal

```bash
ams eval --split test --final
```

Output:

```text
Score: 1.000

Cases: Hidden

Accepted: True
```

---

# 15. Observability

## Scene 13 — Evidence Instead of Trust

**Duration:** 60 seconds

### Narration

A production financial workflow requires more than a score.

It requires evidence.

AMS records the entire lifecycle.

It knows:

- every action requested,
- every policy decision,
- every validation,
- every evaluation score,
- every failed observation,
- current environment state,
- optimization baseline,
- final acceptance.

### Visual

<svg viewBox="0 0 320 190" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=190 rx=16 fill="#0F172A"/>
  <text x=18 y=22 fontSize=12 fontFamily=Arial fill="#E2E8F0" fontWeight="bold">
    AMS Observability Report
  </text>
  {#each [
    ["Actions","8"],
    ["Validation","PASS"],
    ["Tests","PASS"],
    ["Scores","0.875 → 1.000"],
    ["Held-out","1.000"],
    ["Policy Denials","0"]
  ] as row,i}
    <text x=24 y={42+i*22} fontSize=9 fontFamily=Arial fill="#94A3B8">
      {row[0]}
    </text>
    <text x=296 y={42+i*22} fontSize=9 fontFamily=Arial fill="#F8FAFC" textAnchor="end" fontWeight="bold">
      {row[1]}
    </text>
    <line x1=18 y1={48+i*22} x2=302 y2={48+i*22} stroke="#334155" strokeWidth=1/>
  {/each}
</svg>

### Key Statement

> The output is no longer just code. It is code plus evidence.

---

# 16. Architecture Summary

## Scene 14 — Final Architecture

**Duration:** 60 seconds

### Narration

Everything we've seen follows one architectural principle.

The LLM never becomes part of AMS.

AMS remains deterministic infrastructure.

Claude or another coding agent interacts through the CLI today.

Eventually it can interact through MCP.

But the architecture remains unchanged.

### Visual

<svg viewBox="0 0 320 240" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=240 rx=18 fill="#FFFFFF" stroke="#E5E7EB"/>
  <rect x=78 y=18 width=164 height=34 rx=17 fill="#2563EB"/>
  <text x=160 y=39 fontSize=11 fontFamily=Arial fill="#FFFFFF" textAnchor="middle" fontWeight="bold">
    External LLM Agent
  </text>
  <text x=160 y=48 fontSize=7 fontFamily=Arial fill="#DBEAFE" textAnchor="middle">
    Claude / Codex
  </text>
  <path d="M160 52 V68" stroke="#64748B" strokeWidth=1.5 markerEnd="url(#a3)"/>
  <rect x=18 y=68 width=284 height=154 rx=14 fill="#ECFEFF" stroke="#06B6D4" strokeWidth=1.5 strokeDasharray="6 4"/>
  <text x=30 y=84 fontSize=10 fontFamily=Arial fill="#0F766E" fontWeight="bold">
    Agentic Modeling Sandbox
  </text>
  {#each [
    ["State","Rules"],
    ["Capabilities","Actions"],
    ["Contracts","Validation"],
    ["Evaluation","Observability"],
    ["Optimization","Held-out Tests"]
  ] as pair,i}
    <rect x=32 y={96+i*22} width=120 height=16 rx=5 fill="#FFFFFF" stroke="#99F6E4"/>
    <rect x=168 y={96+i*22} width=120 height=16 rx=5 fill="#FFFFFF" stroke="#99F6E4"/>
    <text x=92 y={107+i*22} fontSize=7 fontFamily=Arial fill="#115E59" textAnchor="middle">
      {pair[0]}
    </text>
    <text x=228 y={107+i*22} fontSize=7 fontFamily=Arial fill="#115E59" textAnchor="middle">
      {pair[1]}
    </text>
  {/each}
  <defs>
    <marker id="a3" markerWidth=6 markerHeight=6 refX=5 refY=3 orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#64748B"/>
    </marker>
  </defs>
</svg>

---

# 17. Broader Applications

## Scene 15 — Beyond Bank Reconciliation

**Duration:** 45 seconds

### Narration

Bank reconciliation is only one environment.

The same architecture can support many financial domains.

### Visual

<svg viewBox="0 0 320 180" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=180 rx=16 fill="#F8FAFC" stroke="#E5E7EB"/>
  <text x=160 y=20 fontSize=13 fontFamily=Arial fill="#111827" textAnchor="middle" fontWeight="bold">
    AMS Environment Library
  </text>
  {#each [
    ["Accounting","Bank reconciliation","Month-end close"],
    ["FP&A","Forecasting","Variance analysis"],
    ["Banking","Credit models","Stress testing"],
    ["Pensions","ALM","Liability projection"],
    ["Private Markets","DCF","LBO / Waterfalls"]
  ] as row,i}
    <rect x=18 y={34+i*28} width=284 height=22 rx=8 fill="#FFFFFF" stroke="#D1D5DB"/>
    <text x=30 y={48+i*28} fontSize=8 fontFamily=Arial fill="#111827" fontWeight="bold">
      {row[0]}
    </text>
    <text x=110 y={48+i*28} fontSize=7 fontFamily=Arial fill="#6B7280">
      {row[1]}
    </text>
    <text x=205 y={48+i*28} fontSize=7 fontFamily=Arial fill="#6B7280">
      {row[2]}
    </text>
  {/each}
</svg>

---

# 18. Closing

## Scene 16 — Final Message

**Duration:** 30 seconds

### Narration

We don't need another framework that tells agents how to think.

We need environments that make their work measurable.

Claude writes the code.

The finance professional defines the business problem.

AMS defines the world where that solution must prove itself.

### Final Screen

<svg viewBox="0 0 320 180" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width=320 height=180 rx=18 fill="#0F172A"/>
  <text x=160 y=42 fontSize=16 fontFamily=Arial fill="#F8FAFC" textAnchor="middle" fontWeight="bold">
    Agentic Modeling Sandbox
  </text>
  <line x1=60 y1=58 x2=260 y2=58 stroke="#334155" strokeWidth=1.5/>
  <text x=160 y=82 fontSize=12 fontFamily=Arial fill="#93C5FD" textAnchor="middle">
    The LLM is the policy.
  </text>
  <text x=160 y=104 fontSize=12 fontFamily=Arial fill="#5EEAD4" textAnchor="middle">
    AMS is the environment.
  </text>
  <rect x=78 y=126 width=164 height=28 rx=14 fill="#2563EB"/>
  <text x=160 y=144 fontSize=10 fontFamily=Arial fill="#FFFFFF" textAnchor="middle" fontWeight="bold">
    Build • Test • Evaluate • Prove
  </text>
</svg>

---

# 19. Demo Assets Required

The live recording should include the following terminal interactions.

## Environment Discovery

```bash
ams help --json
ams guide --json
ams rules --json
ams capabilities --json
```

## Candidate Development

```bash
ams schema candidate --json
ams act write_file
ams validate --source --json
```

## Testing

```bash
ams test --json
```

## Evaluation

```bash
ams eval --split validation --json
```

Show the rejected score:

```text
0.875

accepted: false
```

Then after the repair:

```text
1.000

accepted: true
```

## Held-out Verification

```bash
ams eval --split test --final --json
```

Show only aggregate output.

Do not expose held-out cases.

## Observability

```bash
ams summary --json
ams report .
```

Display the generated Markdown report briefly.

---

# 20. Production Guidelines

## Tone

The presentation should feel like an engineering breakthrough rather than a marketing announcement.

Avoid exaggerated claims.

Use evidence from the live demo as the primary proof.

## Editing Style

- Fast opening within the first 20 seconds.
- Alternate between talking head and terminal recording.
- Use architecture diagrams sparingly.
- Keep code snippets short.
- Spend more time showing observations than showing implementation.
- Make the score transition visually memorable.

## Visual Identity

Primary aesthetic:

- dark technical background,
- clean blue accents,
- teal for successful environment validation,
- red only for rejected evaluation,
- minimal gradients,
- terminal typography for CLI demonstrations.

The visual language should communicate:

> deterministic, auditable, engineering-focused infrastructure.

---

# 21. Final Takeaway

The audience should remember one sentence:

> **AI agents should not be trusted because they generated code. They should be trusted because they generated code that survived a well-defined environment.**

That environment is Agentic Modeling Sandbox.