# Courier 2026-09-26 — Convergence & Handoff Order

Status: ACTIVE COORDINATION RECORD
Purpose: prevent context loss, duplicated reasoning, architecture drift, and restart-from-zero behavior while Opus, Codex, Muse and the existing writer work in parallel.

This record complements `docs/CANONICAL_COMPLETION_HANDOFF.md`. It does not replace the canonical handoff schema.

## Non-negotiable operating rules

- CONTINUE_BY_DEFAULT.
- FEATHERLIGHT_BY_DEFAULT.
- TRUTH > SPEED.
- One canonical scheduler authority.
- One source writer per write scope.
- Running long-lived Muse/Google workers are not interrupted just to deliver new context.
- Simulated proof is not physical proof.
- No evidence -> no PASS.
- A new model/session must resume from the latest proven state instead of restarting analysis from zero.
- The coordination branch is not a runtime branch and must not be blindly merged into active runtime work.

## Current strategic objective

Prove the smallest real chain:

`ONE HUMAN START -> TASK A -> REAL WORKER -> RESULT A -> VERIFY -> TASK B AUTO -> REAL WORKER -> RESULT B`

Then scale safely:

`1 -> 4 -> 8 -> 16 -> bounded multi-hour soak`

while preserving Mac/Windows responsiveness and real user activity such as screen recording, music, browser and normal desktop use.

## Required perspectives

### A. Opus — convergence/integration

Primary role:
- identify canonical runtime and canonical scheduler
- distinguish IMPLEMENTED / SIMULATED_PROVEN / PHYSICALLY_PROVEN / UNKNOWN
- eliminate duplicate architecture
- derive minimal integration sequence
- preserve product simplicity

Expected reports:
- `/Users/user/Downloads/courier_work/muse_burn30/reports/OPUS_CONTINUATION_CONVERGENCE.md`
- later: `/Users/user/Downloads/courier_work/muse_burn30/reports/OPUS_FEATHERLIGHT_NUMBER_ONE.md`

### B. Codex — red-team/runtime truth

Primary role:
- attack assumptions
- inspect crash/restart/duplicate/result/claim/process ownership
- find exact physical A->B blocker
- define exact canary and evidence
- avoid architecture redesign

Expected reports:
- `/Users/user/Downloads/courier_work/muse_burn30/reports/CODEX_NUMBER_ONE_RED_TEAM.md`
- or existing runtime proof report if produced:
  `/Users/user/Downloads/courier_work/muse_burn30/reports/CODEX_NEXT_VIDEO_RUNTIME_PROOF.md`

### C. Existing Muse/Google workers

Primary role:
- continue currently owned tasks
- preserve long-run evidence
- do not receive duplicate prompts while actively working
- write reports/backlog/checkpoints in their current coordination roots

### D. Existing single writer

Primary role:
- implement only the final minimal approved delta after convergence
- never compete with another live writer
- preserve protected scopes
- run targeted verification first

## Review order

### Step 1 — Let current Opus finish its first report

Do not interrupt it.

Its report is a hypothesis/convergence analysis, not final authority.

### Step 2 — Let Codex finish independent red-team report

Codex must not be shown Opus conclusions before its independent review is complete unless the current task explicitly requires reconciliation.

Reason: preserve independent failure discovery.

### Step 3 — Compare Opus vs Codex

Build an evidence matrix for every material claim:

- CLAIM
- OPUS = AGREE | DISAGREE | UNKNOWN
- CODEX = AGREE | DISAGREE | UNKNOWN
- REPO/TEST/RUNTIME EVIDENCE
- FINAL STATUS = PROVEN | UNPROVEN | CONTRADICTED
- REQUIRED NEXT ACTION

Agreement between models is not proof.
Repository/test/runtime evidence decides.

### Step 4 — Give both reports to Opus for final reconciliation

Opus must:
- read its earlier report
- read Codex report
- read current repo evidence
- classify every material disagreement
- not restart reasoning from zero
- not invent a new scheduler/wall
- produce one prioritized implementation sequence
- produce one NEXT_SINGLE_WRITER_TASK

This is the correct point to deliver the Codex result to Opus.

### Step 5 — Persist the final decision

The final synthesis must produce a durable handoff record conforming conceptually to:
- `docs/CANONICAL_COMPLETION_HANDOFF.md`
- `schemas/canonical_handoff.schema.json`

Required minimum fields in the handoff:
- CURRENT_GOAL
- SOURCE_BRANCH / SOURCE_SHA or fingerprint
- CANONICAL_RUNTIME
- CANONICAL_SCHEDULER
- IMPLEMENTED
- SIMULATED_PROVEN
- PHYSICALLY_PROVEN
- UNKNOWN
- UNRESOLVED_BLOCKER
- SINGLE_WRITER_PRESERVED
- HEAVY_JOB_LIMIT
- CURRENT_ACTIVE_WORK
- NEXT_SINGLE_WRITER_TASK
- NEXT_SAFE_ACTION
- HUMAN_GATE_REQUIRED
- READY_FOR_NEXT_GOAL
- evidence/report paths

Narrative summaries never override these evidence fields.

### Step 6 — Existing writer receives ONE task

Do not send the whole brainstorm.

Writer receives:
- exact goal
- exact files/scope
- exact acceptance test
- exact forbidden scope
- evidence expected
- stop condition

### Step 7 — Physical canary

Prove:
- real task claim
- real Muse execution
- durable result
- independent verification
- automatic next claim
- second real Muse execution
- zero human relay between A and B

### Step 8 — Scale only after evidence

1 -> 4 -> 8 -> 16.

At each stage record:
- logical slots
- active workers
- heavy jobs
- tasks completed
- auto-next count
- human relays
- duplicates
- lost results
- result-to-next latency
- CPU/memory/swap/resource headroom when observable

### Step 9 — Featherlight soak

Run a bounded 60-120+ minute soak while normal user activity continues.

Success is not "maximum processes".
Success is verified useful work while the machine remains responsive.

## Do not forget

The product goal is not 45 visible terminals.

The product goal is:
- 45 logical capacity slots can exist cheaply
- only resource-safe work becomes physically active
- idle logical capacity costs almost nothing
- result -> next happens automatically
- the user is not the message bus
- Mac and Windows remain usable
- provider/session endings do not erase mission state

## Final synthesis prompt should be issued only after Step 1 + Step 2 reports exist

Do not ask the final synthesizer to guess missing reports.
If a report is absent, mark it UNKNOWN and keep the sequence blocked at the appropriate point.
