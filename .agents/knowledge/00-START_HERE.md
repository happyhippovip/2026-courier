# START HERE (Next Agent Handoff)

CURRENT_HEAD=f71ff070
CURRENT_RUNTIME_STATE=Clean (release-candidate-integration)
CURRENT_OWNERSHIP=Google (Windows/Integration), Codex (Ledger), Muse (Cockpit)

LAST_VERIFIED_TESTS=tests/test_windows_runtime_torture.py

KNOWN_BLOCKERS=Windows Physical Deployment (Blocked on Human Operator)

KNOWN_GOOD_INVARIANTS:
- Duplicate results are safely rejected (409).
- Crashing mid-task yields AMBIGUOUS_CRASH, not replay.
- Stale workers are rejected (426).

FILES_TO_READ_FIRST:
- .agents/knowledge/01-findings-pack.md
- DEFERRED_LEDGER_QUEUE.md

DO_NOT_REDISCOVER:
- Do not re-test Windows duplicate result handling; it is proven via `test_windows_runtime_torture.py`.
- Do not add `psutil` or `tasklist` checks to the Windows daemon lock; it causes cross-platform test breakage and was removed in favor of basic file locking.

NEXT_EXECUTABLE_TASKS:
1. LEDGER-01: Atomic State Persistence (server/app.py)
2. LEDGER-02: Unauthenticated Human Approval Gate
3. LEDGER-03: Uncoordinated Provider Quota Backoff
