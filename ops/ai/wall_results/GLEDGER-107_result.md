# GLEDGER-107 Result — Result Identity + Duplicate-Equivalence Boundary

TASK_ID=GLEDGER-107
STATUS=PROVEN with two carried opens (marked OPEN below; both already queued to central writer, not re-litigated here)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=GLEDGER-104 (generation rule); L2 twelve-case map; L3 replay audit (result + verify ACK paths, 409/400 sets); POST200-021 (b1/b2 duplicate semantics); PHYS-003 (attempts==1, no replay)

## Canonical Result identity
Fields (GLEDGER-102/103): goal_id, task_id, worker_id, attempt (int), dispatch_id, result_id, artifacts[], completed_at; status SUCCESS|FAILED (RESULT_STATES).
result_fingerprint (normative): sha256 over the canonical JSON (sort_keys, compact separators) of {goal_id, task_id, worker_id, attempt, dispatch_id, result_id, artifacts[], status} — the same canonical-hash construction the local path uses for result_id derivation. completed_at is EXCLUDED (resubmissions carry fresh timestamps; identity must survive them).

## Duplicate-equivalence boundary (normative)
Two results are duplicate-equivalent IFF all of {task_id, attempt, dispatch_id, result_id, status, artifacts[]} are equal AND both bind to the same server-held generation. Equivalent → second submission ACKs as duplicate (no re-execution, no re-verify, no state change). ANY difference in {status, worker_id, attempt, dispatch_id} → NOT equivalent → 409/400, never silent ACK (b1, proven by code + tests + b2 negative proof).
OPEN-1 (artifact-identity): b1's result-ACK tuple compares (dispatch_id, result_id, status) WITHOUT comparing artifacts[] — same ids + altered artifacts would ACK. Canonical rule requires artifacts[] in the equivalence set (stated above); implementation gap queued to writer (POST200-021 case 12).
OPEN-2 (server-path result_id): remote path accepts non-empty result_id string without recompute, so generation identity leans on server-held (attempt, dispatch) binding rather than content derivation. Canonical rule holds via binding; content-derived result_id on all paths is writer-optional hardening (POST200-021 cases 1/4).

## Non-rules (explicitly NOT identity)
completed_at, transport retries, log text, worker internals, poll counts — none participate in equivalence. Resubmission with fresh timestamp but identical fingerprint → duplicate. Contradictory results (same generation, non-equivalent content) → never ACK (GLEDGER-115 owns the contradiction procedure).

MISSING=None for the boundary definition. OPEN-1/OPEN-2 are writer-ruling items, already filed.
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-108 (artifact refs use fingerprint-adjacent bindings); GLEDGER-110 (reconcile consumes equivalence outcomes); GLEDGER-115 (contradiction handling).
DO_NOT_REPEAT_FINGERPRINT=gledger-107-result-identity-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-ba97073965399276

DO_NOT_REPEAT_FINGERPRINT=sha256-1b5ffca40047259c

DO_NOT_REPEAT_FINGERPRINT=sha256-16c07d3539cdce08
