# Google Windows Continuous Queue Index

Status: STABLE ENTRY POINT
Purpose: this file is intentionally stable so the same Google worker prompt can be reused every day.

## Current queue source

Primary seeded queue:
- ops/ai/GOOGLE_WINDOWS_NIGHT_QUEUE_50_2026-09-27.md

Stable worker bootstrap:
- ops/ai/GOOGLE_WINDOWS_CONTINUOUS_WORKER.txt

## Current queue generation

QUEUE_GENERATION=2026-09-27-A

The seeded 50-task queue remains the initial task source until its concrete tasks are completed, blocked, or superseded by newer durable project truth.

## Durable truth

Canonical current project state:
- ops/ai/COURIER_SESSION_STATE_2026-09-26.json

Cost/noninterference policy:
- ops/ai/NIGHT_QUEUE_NONINTERFERENCE_AND_COST_POLICY_2026-09-27.md

Subscription routing product rule:
- ops/ai/SUBSCRIPTION_FIRST_AUTO_ROUTER_2026-09-27.md

Device admission rule:
- ops/ai/DEVICE_ADAPTIVE_MOTOR_ADMISSION_2026-09-27.md

## Refresh rule

Workers must NOT repeatedly rescan the repo to create work.

When the current generation has no READY task:
- exactly one worker may acquire local queue_refresh.lock;
- refresh only from durable state, prior task results, and an explicitly named Central Writer handoff;
- do not scan source;
- if no concrete new READY work exists, stop.

When a newer canonical queue generation is committed here, workers should use that generation and must not rerun completed work from older generations unless the new task explicitly says RETEST_AFTER_FINAL_SHA.

## Source writer authority

Windows Antigravity Central Writer is the only final-candidate source writer unless newer canonical state explicitly changes this.

Google continuous workers remain targeted read-only/test workers.
