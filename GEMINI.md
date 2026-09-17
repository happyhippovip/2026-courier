# Courier agent bootstrap

Antigravity/Gemini sessions working in this repository must load and obey the workspace rules under `.agents/rules/` before executing queued or historical instructions.

The primary execution policy is:

@.agents/rules/00-courier-autonomy.md

If an old Issue #37 comment, copied queue prompt, or stale handoff conflicts with that policy, preserve the technical task but discard stale timer/iteration/gate-stop clauses.
