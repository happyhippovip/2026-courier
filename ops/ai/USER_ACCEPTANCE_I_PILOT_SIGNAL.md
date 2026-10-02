# User Acceptance I — Pilot Feedback: "Wann ist die Aufgabe wirklich fertig?"

Status: OPERATOR ACCEPTANCE (USER WINDOW) — 2026-09-28
Product Shell: NOT unlocked. Prep-only, no implementation.

## USER_PROBLEM
"Pilot erfolgreich?" is currently unanswerable: the same metric acronyms mean
different things in different canonical files, so GREEN/RED depends on which
file you read. Feedback capture (setup/support/cost/return) has no record format.

## CURRENT_RUNTIME_TRUTH (verified by reads, shell down, no execution)
- RSR has FOUR definitions: restart-scenarios ratio, target 100%
  (playbook `ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md:281-282`);
  tasks reaching VERIFIED first try, target >80%
  (`ops/ai/PILOT_METRICS_AND_SIGNAL_SPEC.md:8`); "Run Success Rate" reconciled,
  NO target (`ops/ai/PILOT_METRICS_AND_CONTRACT.md:10`); "Restart Survival Rate"
  100% (`ops/ai/PILOT_READINESS_DECLARATION.md:28`).
- NDR has THREE definitions: user voluntarily returns next day / cohort size
  (playbook `:284`); "No Duplicate Rate" dispatched exactly once, 100%
  (SIGNAL_SPEC `:9`, CONTRACT `:11`); "No Duplicate Replay" 100% (READINESS `:29`).
- HIPG consistent-ish: 0 everywhere except playbook target <1.0 (`:279`).
- CONSISTENT (good): gate stays locked until Positive signal — SIGNAL_SPEC `:15`,
  `:22,27,34`; CONTRACT `:22`; READINESS `PRODUCT_SHELL_UNLOCKED=NO` (`:35`);
  READINESS status PILOT_PREPARATION_COMPLETE (`:3`).
- CONSISTENT (good): `ops/ai/PILOT_DUMMY_TASK.json` exists and
  `scripts/verify_pilot_schema.py` exists (schema-validated dummy task).
- Vapor ref: beacon (`scripts/courier_beacon.py:26`) and a pilot candidate task
  ("metric to /system/metrics", `ops/ai/PILOT_GOAL_CONTRACT_SPEC.md:17`) reference
  an endpoint with no server route (see item A).
- Pilot contract sensible: isolation from repo, no direct commits, no human fixing
  (`ops/ai/PILOT_GOAL_CONTRACT_SPEC.md:9-14`); gate note says LOCKED (`:20`).

## ACCEPTANCE_REQUIREMENT
I-1: ONE metric dictionary: per metric exactly one name, formula, source fields
  (which state/log fields), and target. Acronym collisions (RSR/NDR) MUST be
  resolved by rename-or-merge, decided once by the pilot owner.
I-2: ONE signal function GREEN/YELLOW/RED over the unified dictionary; unlock
  follows item J only.
I-3: Per-pilot feedback record: setup minutes, support effort, provider cost,
  voluntary next-day return (the playbook cohort question), payment yes/no+amount.

## MISSING_SYSTEM_SUPPORT
- Metric-dictionary decision (pilot-prep owner).
- `/system/metrics` decision: implement route or remove all references.
- Feedback record schema (preparable now, values need live cohort).

## PREPARABLE_NOW (no code, this pass)
- Unified-dictionary proposal + feedback schema (this file as seed; owner ratifies).

## BLOCKED_UNTIL
- Pilot owner ratifies dictionary; live cohort produces values. No pilot runs here.

## NEXT
J — Product-Shell Acceptance (item J file).
