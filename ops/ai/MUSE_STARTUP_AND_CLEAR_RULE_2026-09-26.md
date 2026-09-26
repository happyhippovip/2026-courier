# Muse Startup + Clear Rule — 2026-09-26

Status: HARD OPERATING CONVENTION FOR COURIER MUSE SESSIONS

## Startup

When the user explicitly chooses Muse YOLO / auto-approval for trusted local Courier work, start the new Muse session in that selected mode.

Typical explicit user-selected invocation:

muse --yolo

This is convenience, not authority.

YOLO does NOT override:

- writer ownership
- host/resource safety
- money/spend gates
- credentials/OAuth/2FA/CAPTCHA gates
- publication/deployment gates
- destructive/irreversible action gates
- no-evidence-no-pass
- exact candidate/runtime binding

Never silently enable YOLO when the user did not choose it.

## Clear

A fresh Muse session is preferred whenever old context is no longer needed for the next decision.

Required lifecycle:

CHECKPOINT
-> SAVE DURABLE RESULT
-> SAVE NEXT EXACT ACTION
-> /clear OR NEW SESSION
-> LOAD MINIMAL CURRENT TRUTH
-> CONTINUE

Do not preserve obsolete chat history solely because the session can technically continue.

## Why

Large stale context can cause:

- slower response/turn latency
- higher token/API usage
- repeated work
- stale branch/candidate assumptions
- more confused ownership
- larger local-client resource pressure

The correct goal is not "infinite chat continuity."

The correct goal is:

**durable project continuity with disposable featherlight sessions.**

## Agent handoff

Every agent/provider/chat transition should assume the next session starts nearly empty.

The repo/ledger carries durable truth.

The active chat carries only the current mission.

## Long-run exception

A 10-hour overnight run may use multiple fresh contexts over its lifetime.

Do not end useful work merely because a context is cleared.

Checkpoint, rotate, reload, continue.

## Never forget

SESSION_MEMORY_IS_CACHE
REPO_LEDGER_IS_DURABLE_TRUTH
CLEAR_STALE_CONTEXT=YES
CONTINUE_FROM_CHECKPOINT=YES
