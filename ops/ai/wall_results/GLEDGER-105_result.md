# GLEDGER-105 Result — Claim/Lease Record

TASK_ID=GLEDGER-105
STATUS=PROVEN (by reused harvested evidence; no new source reads)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=GLEDGER-101 (§5 claim binding + recovery ownership); GLEDGER-104 (dispatch mint/binding rules); L3 (claim gating, reclaim_stale, sequential gating); P5 (daemon once-only + STOP fencing); PHYS-003 (no replay, bindings preserved)

## Canonical claim/lease record
REQUIRED: `task_id`, `worker_id` (server-assigned canonical ID, never worker-chosen), `attempt` (integer, GLEDGER-104), `dispatch_id` (fresh per claim), `claimed_at` (server timestamp of claim acceptance), `lease_until` (expiry; server is the lease clock — worker heartbeats/seen-markers refresh `dispatch_last_seen`, never self-extend).
OPTIONAL: `run_id` (worker execution handle, informational only — confers no identity), claim poll context (queue position served).
FORBIDDEN: worker-set lease_until; worker self-assignment of worker_id; second active claim on the same task (only the indexed QUEUED step is servable; all other claimants receive task=None).

## Recovery ownership
- Expiry/staleness detection is server-owned (sweep of `dispatch_last_seen` vs lease). Worker "release" signals are hints, not authority.
- Stale worker's DISPATCHED task → HUMAN_REQUIRED (quarantine). The recovery owner of a quarantined task is the resume path (explicit retry action minting attempt n+1), never the stale worker, never an auto-replay loop.
- Released-claim tasks (worker gave up, lease intact or expired) re-enter QUEUED only via server transition; daemon-side they are quarantined locally (no re-execution after restart).
- STOP fencing (`runtime_state.py` primitives): a stopped worker's in-flight execution cannot bind results afterward — any late submit carries a superseded or unbound generation → rejected.

## Single-claim invariant
At most one live (task_id, attempt, dispatch_id) binding exists per task at any time. A new claim requires terminal-or-quarantine resolution of the prior binding (reconciled/failed-terminal/human-required + resume). Concurrent double-claim of the same step is impossible by construction (indexed single servable step + atomic claim acceptance + durable state).

MISSING=Exact lease-duration constants and sweep-interval values (operational tuning, not contract; flagged for GLEDGER-118 device/wall state if capacity representation needs them).
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-106 (execution lifecycle starts at claim acceptance); GLEDGER-118 (lease/capacity truthful representation may reference lease_until semantics).
DO_NOT_REPEAT_FINGERPRINT=gledger-105-claim-lease-record-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-14ba56eb57d1fb42

DO_NOT_REPEAT_FINGERPRINT=sha256-91976cf5d6245d24

DO_NOT_REPEAT_FINGERPRINT=sha256-bc514ad878c4efed
