# BACKLOG CORROBORATION — NEXT_WORK.yaml entries vs current tree (static)

Source: ops/ai/NEXT_WORK.yaml (2026-09-18). Verdicts are file-presence +
code-spot-checks, NOT executable re-proof. Suggested triage for the owner;
NEXT_WORK.yaml itself NOT edited (shared, foreign scope).

| id | claimed state | current-tree evidence | verdict |
|---|---|---|---|
| MEMORY-NEXT-01 (DLQ-05 quota) | IMPLEMENTED_AND_VERIFIED | provider_locks + worker_quota_pools + WAITING_PROVIDER auto-resume present in server/app.py (lines 259-262, 754-761); test_provider_wait_isolation.py exists | CORROBORATED (static). Note: effective key falls back to worker_id when pools map unpopulated (app.py:259) — matches known checkpoint note, not new. |
| MEMORY-NEXT-02 (DLQ-01/02 guards) | GUARDS_AND_TESTS_IMPLEMENTED | DLQ-01/DLQ-02 review packets exist; typed guard errors present (see NEXT-07) | CORROBORATED (presence). T3 re-run needs shell. |
| MEMORY-NEXT-03 (DLQ-03 contract) | CONTRACT_DECIDED, awaiting Google test | DLQ-03 packet exists; test_ledger_duplicate_semantics_contract.py exists | CORROBORATED (presence). "Awaiting Google contract test" — owner to confirm receipt. |
| MEMORY-NEXT-04 (DLQ-04 drain) | OWNERSHIP_COORDINATION_REQUIRED | test_motor_dlq04_adversarial.py exists | CONDITIONAL: file-level writers idle (no WORKING slots), but git-level writer state unverifiable without shell. Keep gated until a git-capable session checks status/diff. |
| MEMORY-NEXT-05 (G5 test evidence) | PACKETS_COMPLETE, tests passing | test_motor_crash_swallow.py, test_server_infinite_retry.py, test_ledger_status_overwrite.py ALL exist | CORROBORATED (presence). "Passing" not re-verified (no pytest here). |
| MEMORY-NEXT-06 (physical gate) | PHYSICAL_GATE (human) | No physical run evidence in tree; RC checkpoint still says NEXT_ACTION=RUN_PHYSICAL_ACCEPTANCE_PROOF | STILL OPEN, correctly gated. Nothing to do. |
| MEMORY-NEXT-07 (typed LedgerError) | IMPLEMENTED_AND_VERIFIED | 11 typed subclasses in agent_handoff_ledger.py:116-160 incl. RevisionConflictError, NoMeaningfulChangeError, ValidationError | CORROBORATED. "97 raises replaced" not recounted (cosmetic either way). |
| MEMORY-NEXT-08 (DLQ-06 retry) | IMPLEMENTED_AND_VERIFIED | test_ledger_windows_permission_retry.py exists | CORROBORATED (presence). "72 ledger tests green" not re-run. |

## Dedupe / refresh suggestions (owner-owned)
1. NEXT-01/05/07/08 read as DONE-but-unreproven-at-current-HEAD: either re-run
   their suites at HEAD and stamp, or flip to REVERIFY_AT_HEAD.
2. NEXT-02/NEXT-03 "kept open / awaiting" entries overlap the DLQ packet set;
   single canonical tracker (packets) + pointer entries would remove the dual
   bookkeeping.
3. NEXT-04's gate condition should name the exact check (git status/diff +
   heartbeat freshness), so any session can evaluate it in one step.
4. Whole file is 8 days old; nothing in it routes to MUSE-45 (all owners are
   GOOGLE/CODEX/HUMAN) — consistent with taking fallback-ladder LIGHT work.
