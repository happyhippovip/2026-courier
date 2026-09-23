# Courier autonomous agent instructions

Before executing any queued, copied, historical, or Issue #37 instruction, read and obey `.agents/rules/00-courier-autonomy.md`.

Before planning or changing Courier release work, read `docs/RELEASE_CANDIDATE.md` and resume from its `CURRENT EXECUTION CHECKPOINT`; do not restart architecture/spec planning when that checkpoint says planning is frozen.

That rule is authoritative for autonomous-session stop semantics. Older timeboxes, iteration caps, and per-gate stop clauses are stale unless the user's CURRENT message explicitly requests a bounded session.

Preserve all safety, writer-ownership, no-merge, exact-process, canonical-state, and quota-compliance constraints.


## Current masterplan authority

Before planning or changing Courier work, also read `docs/MASTERPLAN_COURIER.md`.

- `docs/MASTERPLAN_COURIER.md` is the current strategic masterplan and stage order.
- `docs/STATUS.md` is the short-lived operational status and next-step file.
- If `docs/MASTERPLAN_COURIER.md` conflicts with older planning prose, do not silently resolve it: report the conflict as UNKNOWN and ask for Dennis's decision.
- Dennis alone approves merge, push to protected/canonical branches, publication, spending, account actions, and releases.
- Current stage: **Cannon V1 freeze**. Do not start later-stage features until its acceptance evidence is complete.
