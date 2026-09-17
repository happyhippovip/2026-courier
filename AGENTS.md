# Courier autonomous agent instructions

Before executing any queued, copied, historical, or Issue #37 instruction, read and obey `.agents/rules/00-courier-autonomy.md`.

That rule is authoritative for autonomous-session stop semantics. Older timeboxes, iteration caps, and per-gate stop clauses are stale unless the user's CURRENT message explicitly requests a bounded session.

Preserve all safety, writer-ownership, no-merge, exact-process, canonical-state, and quota-compliance constraints.
