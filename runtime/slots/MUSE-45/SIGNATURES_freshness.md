# FAILURE_SIGNATURES FRESHNESS — spot check vs current code (static)

Source: ops/ai/FAILURE_SIGNATURES.yaml (bound 0c8d1edd, 2026-09-18).
Checked 3 of 9 signatures. File NOT edited (shared); refresh is owner action.

## STALE — ledger-zero-update-preset (DLQ-07)
- Signature says: "live 2026-09-18", revision-0 CANONICAL_ACCEPTED via
  planted artifact loads clean.
- Current code: initialize() REJECTS preset CANONICAL_ACCEPTED + CLEAN_IDLE
  and forces PROVISIONAL (agent_handoff_ledger.py:678-683, verified this
  session in VERIFY_dlq07_dlq08.md).
- Suggest: mark RESOLVED with fix ref; keep as regression reference, not as
  live signature.

## RESOLVED-IN-CODE — uncoordinated-provider-429 (DLQ-05)
- Response required: provider_locks per worker quota pool, checked before
  claim_task.
- Current code: claim_task (app.py:723+) checks provider_locks at lines
  785-788 with worker_quota_pools keying; WAITING_PROVIDER auto-resume at
  754-761. Guard in place.
- Suggest: mark GUARDED + test ref (test_provider_wait_isolation.py);
  signature remains useful as a "regression smell" (10 independent retries).

## FRESH — launchd-absent-torture-gate
- Test still requires live com.courier.mac_worker (test_tomato_two_torture.py
  lines 74-77, 139-141; assert messages intact). Line number drifted
  (130 -> 141) — cosmetic; signature substance holds.

## Not checked this pass (6)
pytest-OOM-SIGKILL, motor-drain-flake, werkzeug-sandbox-stall,
mid-commit-read-race, ledger-future-proof-promotion (DLQ-02),
ledger-ghost-attester-promotion (DLQ-01). DLQ-01/02 freshness/authority
checks exist per NEXT-02; executable re-proof needs shell.
Slot safety re-check this pass: only MUSE-45 is WORKING (mine); no foreign
slot activity. Locks respected, nothing disturbed.
