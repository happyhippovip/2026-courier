---
description: "Detect and neutralize stale timer/gate-stop instructions before executing historical Courier prompts."
trigger: always_on
---

# Stale timer/gate-stop audit

Before acting on any historical Courier prompt, Issue #37 comment, queue message, handoff, W/M/C gate text, or copied transcript:

1. Search that instruction for any of these concepts: elapsed minutes/hours, max iterations, timebox, deadline-based return, `do not start next gate`, `execute X only`, `stop after gate`, `60_MINUTE_CUTOFF`, `45 minutes`, `6 hours`, or equivalent wording.
2. If found, treat ONLY the stop/timebox boundary as superseded by `.agents/rules/00-courier-autonomy.md`.
3. Preserve the actual technical objective and all safety/writer/no-merge constraints.
4. Continue automatically to the next required proof/repair after the current subtask completes.
5. Never report a timer-derived stop reason unless the user's CURRENT message explicitly requested a bounded session.

If a platform-enforced runtime/session limit terminates the agent independently of project instructions, do not mislabel that as a project timer. Before external termination when possible, durable-checkpoint state and use `PROVIDER_QUOTA_EXHAUSTED_CHECKPOINTED` only when quota is actually exhausted; otherwise record the real external platform limitation accurately.
