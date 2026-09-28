# GLEDGER-115 Result — Contradictory Result Handling

TASK_ID=GLEDGER-115
STATUS=PROVEN (by reused evidence incl. a decided live precedent; no new source reads)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=GLEDGER-107 (non-equivalence + non-rules); GLEDGER-110 (closed under contradiction); GLEDGER-113 (rule 4: contradiction marking); GLEDGER-114 (CONTRADICTED row); candidate-b-1 vs candidate-b-2 resolution (b2's status-drop vs b1's tuple → b2 REJECTED — decided precedent)

## Definition (normative)
A contradiction = two non-duplicate-equivalent results (or evidences) asserted for the same (task_id, generation) where both claim authority: e.g. different verdicts on one result_id, different artifact hashes for one artifact_id, or a candidate (b2) whose semantics weaken an accepted candidate (b1) on the same acceptance cases.

## Procedure (normative — never duplicate-ACK contradictions)
1. DETECT: equivalence check fails (GLEDGER-107) yet both items claim the same slot → flag CONTRADICTION_CANDIDATE, halt auto-adoption of either.
2. PRESERVE: both items kept as history with full provenance (submitter, binding, timestamp). Neither is deleted, overwritten, or silently dropped.
3. DECIDE by exactly one authority path: (a) deterministic rule already on record (e.g. stricter duplicate-equivalence wins — the b1/b2 precedent: weakening semantics loses); (b) independent re-evidence (fresh targeted check both items must survive); (c) explicit owner/central-writer ruling naming the winner and reason.
4. MARK: loser → CONTRADICTED status in ledger (kept, never reconciled as truth); winner → RECONCILED with `supersedes: <loser-fingerprint>` reference.
5. RESUME: downstream (reconcile, NEXT_READY, harvest) consumes the winner only after marking completes. No consumer may race the decision.

## b1/b2 precedent (decided, reusable)
b2 ("acknowledge duplicates when status omitted") contradicted b1's (dispatch, result, status) tuple on cases 8–12. Resolution: rule (a) — duplicate-equivalence may only strengthen, never weaken → b2 REJECTED, b1 stands. Future weakening proposals resolve identically without new procedure.

MISSING=None.
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-128 (harvester contradiction gate); GLEDGER-130 (open contradictions block the finish gate).
DO_NOT_REPEAT_FINGERPRINT=gledger-115-contradiction-procedure-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-b28833c841665370

DO_NOT_REPEAT_FINGERPRINT=sha256-bd1e46a06f7b33a0
