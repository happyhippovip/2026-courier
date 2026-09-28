# GLEDGER-104 Result — Attempt/Dispatch Identity

TASK_ID=GLEDGER-104
STATUS=PROVEN (by reused harvested evidence; no new source reads)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=GLEDGER-101 (§4–6 claim/dispatch rules); GLEDGER-102 (attempt_id alias vs integer attempt); GLEDGER-103 (attempt/dispatch forbidden-mutation rules); L3 replay audit (resume/reclaim paths); PHYS-003 (attempts==1 after restart — no replay)

## attempt_id semantics
- Canonical Ledger identity: integer `attempt` scoped to (`task_id`), starting at 1.
- Uniqueness: (`task_id`, `attempt`) is unique; attempt increments if and only if the server accepts `/tasks/{id}/resume` retry from HUMAN_REQUIRED, FAILED_VERIFICATION, or FAILED_TERMINAL. No other path changes attempt — never on resubmit, never on verify, never on restart, never on reclaim.
- Transport alias: local build path expresses the same identity as string `{task_id}:attempt:{n}` (prepare_task). Alias, not second identity: equality is defined on (task_id, integer n).
- Retry rule: a retry ALWAYS moves to attempt n+1 with a fresh dispatch_id. Same-attempt redelivery is a duplicate (→ ACK path, GLEDGER-107), never a new execution authorization.

## dispatch_generation semantics
- `dispatch_id` (`dispatch-<uuidhex12>`) minted fresh on every claim, bound 1:1 to (task_id, attempt, worker_id, claimed_at).
- Uniqueness: never reused across claims, including retries of the same attempt number progression — each claim event mints exactly one dispatch_id.
- Binding enforcement: result submit must present the exact (attempt, dispatch_id) the server holds; mismatch → 400/409 (observed). After resume mints (n+1, new dispatch), the old pair is permanently unbindable — results referencing it are rejected, never reconciled, never ACKed as duplicates of the new generation.
- Restart rule (PHYS-003): coordinator restart preserves (attempt, dispatch_id) bindings from durable state; reconciled tasks keep `attempts == 1`; no new dispatch is minted for completed work (no A-replay).

## Combined generation rule (duplicate-equivalence input)
A result generation is identified by (task_id, attempt, dispatch_id, result_id, status). Identical full tuple → duplicate-ACK eligible (GLEDGER-107 boundary + artifact-identity open item carried). Any change in attempt or dispatch → different generation → rejected, never ACKed.

MISSING=None for identity semantics. Carried opens (owned elsewhere): server-path result_id canonicalization (GLEDGER-107); artifact-identity in result-ACK tuple (central-writer ruling).
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-105 (claim/lease record references attempt/dispatch binding); GLEDGER-107 (generation rule input).
DO_NOT_REPEAT_FINGERPRINT=gledger-104-attempt-dispatch-identity-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-6e8b305211f935f5

DO_NOT_REPEAT_FINGERPRINT=sha256-5937b495a1ee54c5

DO_NOT_REPEAT_FINGERPRINT=sha256-3b4ab3a26d667046
