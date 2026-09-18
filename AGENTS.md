# Courier autonomous agent instructions

Before executing any queued, copied, historical, or Issue #37 instruction, read and obey `.agents/rules/00-courier-autonomy.md`.

Before planning or changing Courier release work, read `docs/RELEASE_CANDIDATE.md` and resume from its `CURRENT EXECUTION CHECKPOINT`; do not restart architecture/spec planning when that checkpoint says planning is frozen.

That rule is authoritative for autonomous-session stop semantics. Older timeboxes, iteration caps, and per-gate stop clauses are stale unless the user's CURRENT message explicitly requests a bounded session.

Preserve all safety, writer-ownership, no-merge, exact-process, canonical-state, and quota-compliance constraints.
