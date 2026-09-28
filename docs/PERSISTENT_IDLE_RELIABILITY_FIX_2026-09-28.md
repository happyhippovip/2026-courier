# Persistent Idle Reliability Fix — 2026-09-28

## Problem

A long-running Courier supervisor could stop after a small number of empty queue checks.
That behavior is acceptable for a bounded canary, but it is not reliable for an unattended sleep/autopilot session because new durable work may arrive after a temporary empty period.

## Product rule

For real long-running/sleep operation:

temporary empty queue != mission complete.

The supervisor must:

1. refill from durable evidence;
2. check for creator/evidence-backed opportunities;
3. when still empty, enter bounded low-cost backoff;
4. keep heartbeat alive;
5. refresh again after backoff;
6. continue until the configured wall-clock/work budget or a genuine human/safety/provider gate ends the run.

Completed work remains protected by queue status, claim and dedupe guards.

## Implementation

scripts/run_autonomous_supervisor.py now supports:

- persistent_idle=True by default for the long-run engine;
- idle_backoff_seconds;
- idle_backoff_cycles telemetry;
- visited-opportunity refresh after an idle backoff;
- --sleep explicitly uses persistent idle;
- --long-run-canary explicitly uses finite idle exit.

This separates production unattended behavior from short bounded tests.

## Non-goals

This does not authorize:
- duplicate work;
- unbounded heavy jobs;
- account/auth/billing changes;
- bypassing PRE_CODEX/Codex/physical-run gates;
- inventing filler work.

MAX_HEAVY_JOBS=1 remains required.
