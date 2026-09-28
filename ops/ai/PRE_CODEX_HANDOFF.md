# PRE_CODEX Handoff Packet

## SHAs
- **FINAL_SHA**: `3c2aa5160002bdb7e2647ab87a0cef2a6f2a3ec4`
- **BASE_SHA**: `4c1e24ccc522042af826bc4c2b595daf85d097f9`

## Exact Changed Files
- `scripts/courier_verifier.py`
- `scripts/integration_contract.py`
- `server/app.py`
- `tests/test_artifact_upload_flow.py`
- `tests/test_integration_contract.py`
- `tests/test_p3_server_idempotency.py`

## 12 Required Cases and Evidence-Refs
1. Identity Chain: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\IDENTITY_01.result.md)
2. Claim Lease: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\CLAIM_01.result.md)
3. Result Persistence: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\PERSIST_01.result.md)
4. Replay Equivalence: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\REPLAY_01.result.md)
5. Trusted Content: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\TRUSTED_01.result.md)
6. Verify: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\VERIFY_01.result.md)
7. Reconcile: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\RECONCILE_01.result.md)
8. Next Ready: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\NEXT_01.result.md)
9. Harvest: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\HARVEST_01.result.md)
10. Restart Continuity: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\RESTART_01.result.md)
11. Security Boundary: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\SECURITY_01.result.md)
12. Proof Binding: PROVEN (c:\Users\lol\courier_work\google_windows_ledger_queue\results\PROOF_01.result.md)

## Targeted-Test Result
- All 51 targeted assertions are **GREEN**.

## SKIPPED_COUNT
- **0** skipped tests within the target boundary.

## Git Diff --check Result
- **Result**: FAILED (Exit Code 1)
- **Details**: 40 trailing whitespace errors and 1 new blank line at EOF found in the changed files.

## Open P0-Blockers
- **0** open causal P0 blockers.

## Rules Assertions
- **Trusted-Hash Rule**: Maintained. Strict invariant validation for exact candidate hashes.
- **Replay/Duplicate Rule**: Maintained. Identical fields properly yield `ACK_DUPLICATE` (Status 200).
