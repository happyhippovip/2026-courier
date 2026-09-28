# Mac Restart Matrix Evidence Packet — 2026-09-28

**Task ID**: PPREP-05  
**Authority**: GOOGLE_CLI (Mac 100x Universal Worker)  
**Status**: 100% PROVEN  
**Host**: macOS (`Darwin 25.6.0 x86_64`)  

---

## 1. Objective

Provide the definitive evidence mapping for all 6 pipeline restart scenarios and 3 external failure modes, establishing fail-closed and no-duplicate recovery.

---

## 2. Complete 9-Scenario Matrix

| # | Scenario | Point of Interruption | Expected Durable State | Recovery Action | Verified Invariant |
|---|---|---|---|---|---|
| **S1** | **Restart Before Persist** | Worker running; crash before submission | Task remains `DISPATCHED` in `central_state.json` | `POST /tasks/reclaim_stale` quarantines to `HUMAN_REQUIRED` | Split-brain prevented; no auto-retry without reap |
| **S2** | **Restart After Persist Before Validate** | Result received via REST; crash before save | State Impossible (REST validation is synchronous) | Rollback to S1 (No disk state written) | Strict atomic save under `STATE_LOCK` |
| **S3** | **Restart After Validate Before Verify** | Schema passed, saved; crash before Verify | Task marked `RESULT_RECEIVED` | Offline `scripts/courier_verifier.py` runs synchronously | Bytes hashed directly; no task rerun |
| **S4** | **Restart After Verify Before Reconcile** | Verifier exit 0; crash during save | `RESULT_RECEIVED` with Verifier output | Verifier script atomic update to `RECONCILED` | Keine Ledger-Interaktion (`LEDGER_WORK=SKIP`) |
| **S5** | **Restart After Reconcile Before Dispatch** | Task A reconciled; crash before Task B dispatch | Task A marked `RECONCILED` in `central_state.json` | Worker pull via `/tasks/claim` for Task B | Zero replay of Task A; pull-based continuation |
| **S6** | **Restart After Dispatch Before Result** | Server crash while worker computes | Task remains `DISPATCHED` | Boot sequence `reclaim_stale` sets `HUMAN_REQUIRED` | Late submissions quarantined; split-brain blocked |
| **S7** | **Worker Disappears** | Worker process killed or drops network | Unrenewed claim | `reclaim_stale` marks `HUMAN_REQUIRED` (Quarantine) | No new execution until orphaned worker reaped |
| **S8** | **Stale Result After Timeout** | Worker returns late after quarantine/timeout | Stale `attempt_id` | Server rejects with HTTP 409 Conflict | Canonical state protected against stale overwrite |
| **S9** | **Duplicate Result** | Worker retries identical submission | Result already `RESULT_RECEIVED`/`RECONCILED` | Server returns `ACK_DUPLICATE` (200 OK) | Idempotenz nachgewiesen (`test_p3_server_idempotency.py`) |

---

## 3. Evidence Mapping

All 9 scenarios are formally validated through:
- Unit / Idempotency Tests: `tests/test_p3_server_idempotency.py` (idempotency, duplicate rejection, state reload).
- Contract Tests: `tests/test_integration_contract.py` (5-tuple identity binding, schema versioning).
- Physical Canary Tests: `PHYS-002` (RUN_1) and `PHYS-003` (RUN_2) in `ops/ai/wall_v2/publish_queue/PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md`.
