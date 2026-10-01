# 24h Long-Run Watchdog (interim operator mode)

## Why this exists

Interactive Muse/Antigravity turns can return after 10–20 minutes even when the
overall project is not finished. Making the prompt longer does not guarantee a
longer runtime and can waste context/tokens.

This watchdog moves the *persistence* outside the model turn:

- one bounded local Python process stays alive for a fixed wall-clock period;
- it invokes Courier's existing `AutonomousSupervisor` in bounded slices;
- when no evidence-backed work exists, it sleeps locally instead of spending model tokens;
- it reuses one durable session budget across all slices;
- model work and external actions default to **0**;
- it writes durable state to `events/longrun-watchdog/`.

It is an interim bridge until this lifecycle is owned directly by the Courier desktop app.

## Host-safety rule

Read these before enabling non-zero model/external budgets:

- `docs/HOST_OVERHEAT_INCIDENT_AND_RESUME_GATE.md`
- `docs/COMPUTE_RESOURCE_SAFETY_POLICY.md`

The watchdog **fails closed** unless `--host-gate-passed` is supplied for any
non-zero model or external-action budget. This flag is an operator assertion; do
not use it until the documented resume gate is actually satisfied.

## Safe zero-model overnight canary

This stays alive for up to 24 hours, checks for local evidence-backed work in
bounded slices, and sleeps for 5 minutes while idle:

```bash
python3 scripts/run_longrun_watchdog.py \
  --hours 24 \
  --slice-seconds 900 \
  --idle-sleep-seconds 300 \
  --max-operations-per-slice 12 \
  --max-model-jobs 0 \
  --max-external-actions 0 \
  --zero-spend-limit-eur 0
```

This mode does **not** guarantee that useful work exists for 24 hours. It
guarantees that the watchdog process itself remains available until the deadline
unless a signal, exception, or fail-closed safety condition stops it.

## One-slice canary

Before an overnight run:

```bash
python3 scripts/run_longrun_watchdog.py --once --hours 0.25
```

## Bounded model work after the host gate passes

Example only, after the permanent host-safety gate is genuinely green:

```bash
python3 scripts/run_longrun_watchdog.py \
  --hours 24 \
  --max-model-jobs 4 \
  --max-external-actions 0 \
  --host-gate-passed
```

The total model reservation budget is reused across slices via the same session
ID. Idle time still sleeps locally and does not consume a model turn.

## Important distinction

This watchdog does not keep an individual GUI chat/model turn open for 24 hours.
That is not controllable from a prompt. It keeps the **Courier orchestration
process** alive and checkpointed, so short model turns are no longer the
persistence mechanism.

Existing `/loop` jobs can still be useful for specific interactive windows, but
they should not be multiplied blindly. The watchdog is intended to reduce the
need for many idle loops.

## State and stop behavior

State is written atomically to:

`events/longrun-watchdog/<session-id>.json`

A normal deadline ends with `DEADLINE_REACHED`.
SIGINT/SIGTERM ends with `STOPPED_BY_SIGNAL`.
Circuit/payment safety conditions end fail-closed with `PAUSED_FAIL_CLOSED`.

The watchdog never performs an automatic merge, deploy, secret change, purchase,
or external commercial action by itself.
