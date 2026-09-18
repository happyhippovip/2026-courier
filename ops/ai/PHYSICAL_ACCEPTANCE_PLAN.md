# PHYSICAL ACCEPTANCE PLAN
Software completion != physical acceptance. Physical claims require observed
process transitions, never mocks.

Prerequisites: reviewed deployable SHA; actual Windows runtime reports that exact
SHA; OS-owned process identity is observed; canonical server and verifier are
reachable; no synthetic worker/result/counter injection is enabled.

PASS: one canonical goal progresses through real claims, execution, durable
results, independent verification, reconciliation, next dispatch/replenishment,
terminal completion, and clean idle with exact identity and zero duplicate
external effects. Restart/resume must preserve identity and must not replay an
ambiguous external effect.

FAIL: stale/wrong/unknown runtime SHA, interactive-agent ownership, manufactured
evidence, missing verifier independence, duplicate effect, replayed dispatch,
remaining safe READY work at clean idle, or any UNKNOWN predicate promoted to
PASS.
