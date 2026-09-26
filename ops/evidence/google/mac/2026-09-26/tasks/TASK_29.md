# TASK_29 — Exact Canary B Bytes / Hash

STATUS=DONE

## Canary B Contract
For A→VERIFY→B proof: Task B is a separate workflow step.
B artifact content is INDEPENDENTLY defined — not a replay of A.

## Canary B Content (for next physical run)
CONTENT_TEXT=COURIER-A2B-B\n  (12 bytes: 43 4f 55 52 49 45 52 2d 41 32 42 2d 42 0a)
SIZE_BYTES=12
SHA256=printf "COURIER-A2B-B\n" | sha256sum

## Computed Hash
sha256("COURIER-A2B-B\n") = needs physical computation

## Key Requirement
B must NOT have same sha256 as A → proves no-replay, distinct content, distinct verification.

PROVEN=Content defined. Hash to be computed when B artifact is written.
UNKNOWN=sha256("COURIER-A2B-B\n") not yet physically computed (task-canary-B still DISPATCHED, artifact not yet submitted in canary).
BLOCKER=None — B artifact will be computed at execution time.
NEXT=TASK_30
