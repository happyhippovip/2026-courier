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
| **S1** | **Restart Before Persist** | Worker running; crash before submission | Task remains `DISPATCHED` in memory | Watchdog reclaims after lease timeout; rolls back to `READY` | Task cleanly retried with attempt+1; zero ghost state |
| **S2** | **Restart After Persist Before Validate** | Result on disk; crash before schema check | Result exists in intake queue | Server reloads; detects unvalidated submission; runs schema check | Result validated without re-executing task |
| **S3** | **Restart After Validate Before Verify** | Schema passed; crash before Verifier download | Task marked `VALIDATED_PENDING_VERIFY` | Verifier daemon polls pending queue on boot; downloads bytes | Bytes hashed directly; no task rerun |
| **S4** | **Restart After Verify Before Reconcile** | Verifier exit 0; crash before ledger entry | Result file in `ops/ai/wall_results/` | Harvester detects unharvested result; updates `ledger.jsonl` | Atomic reconciliation; no task rerun |
| **S5** | **Restart After Reconcile Before Dispatch** | Task A reconciled; crash before Task B dispatch | Task A marked `RECONCILED` in ledger | Scheduler recomputes `NEXT_READY`; dispatches Task B | Zero replay of Task A; Task B starts cleanly |
| **S6** | **Restart After Dispatch Before Result** | Task dispatched; crash while worker computes | Active lease with heartbeat | If worker submits before timeout, accepted; if dead, reclaimed | Single active execution; clean recovery |
| **S7** | **Worker Disappears** | Worker process killed or drops network | Unrenewed claim / heartbeat | Watchdog detects missed heartbeats; marks attempt `ABANDONED` | Task returned to `READY` for fresh attempt |
| **S8** | **Provider Outage** | External LLM / API throttled or down | Task fails with provider error | Exponential backoff with jitter; routes to alternate or pauses | Preserves task identity; no infinite thrash |
| **S9** | **Stale Result After Timeout** | Worker returns late after lease reclaimed | Stale `attempt_id` < current | Server rejects with HTTP 409 Conflict | Canonical state protected against stale overwrite |

---

## 3. Evidence Mapping

All 9 scenarios are formally validated through:
- Unit / Idempotency Tests: `tests/test_p3_server_idempotency.py` (idempotency, duplicate rejection, state reload).
- Contract Tests: `tests/test_integration_contract.py` (5-tuple identity binding, schema versioning).
- Physical Canary Tests: `PHYS-002` (RUN_1) and `PHYS-003` (RUN_2) in `ops/ai/wall_v2/publish_queue/PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md`.
