# Google/Central repair handoff — independent Codex review eba56edb

HANDOFF_ID: CODEX-TO-GOOGLE-CENTRAL-eba56edb
STATUS: OWNER_REPAIR_REQUESTED
PRODUCTION_OWNER: GOOGLE / existing Central production owner
OWNERSHIP_TRANSFER: NONE
REVIEWED_LOCAL_HEAD: eba56edb837256857d123b64b74e81421009ebc0
REMOTE_HEAD_OBSERVED_WHILE_ROUTING: a46e32e33e08222f98f649c9fabe0a3634b118a0
SOURCE: Independent Codex review supplied by the user in this conversation.
EVIDENCE_STATUS: Findings and test counts are reported by that review; the routing assistant has not rerun the tests or independently reproduced the defects.
OWNER_ACKNOWLEDGEMENT: NOT_OBSERVED
REPAIR_OR_ACCEPTANCE_CLAIM: NONE

## Routing and snapshot boundary

This is a repair request for the existing owner, not a new production-writer assignment, a replacement scheduler, or a completed implementation-review packet.

At the observed remote snapshot, `ops/ai/OWNERSHIP_MAP.yaml` assigns `ledger_guard_motor` to GOOGLE, `OWNED_UNTIL_EXPLICIT_HANDOFF`, and `canonical_integration_windows_runtime` to GOOGLE. `ops/ai/GOOGLE_CONTINUOUS_WORK.yaml` is the existing implementation work loop and includes `ops/ai/packets/` among its inputs.

The reviewed local SHA and the observed remote SHA are different. Preserve the review's original binding. Before editing, the existing owner must inspect local status/diff and the bounded delta affecting these findings, reproduce against its exact candidate, and record any finding already fixed with the corresponding evidence. Do not rebind the reported results to a newer SHA or infer that later green test counts resolve these counterexamples.

## First repair queue — preserve this order

### 1. Contradictory duplicate result incorrectly acknowledged

FILE: `server/app.py`
FUNCTION: `task_result()`

REPORTED_BEHAVIOR: Duplicate detection compares only `result_id` + `worker_id`. A second payload using the same IDs, but changing SUCCESS to FAILURE and changing artifacts, receives HTTP 200 `ACK_DUPLICATE`.

IMPORTANT_SCOPE: The authoritative first result remains intact. The reported defect is the false idempotent acknowledgement of a contradictory body, not an observed overwrite of that first result.

REQUIRED_REPAIR: Require equality of the canonical DurableResult payload/digest before issuing the idempotent ACK. Otherwise return HTTP 409 `CONTRADICTORY_DUPLICATE`, preserving the authoritative first result.

REQUIRED_TEST: Same IDs with a different body, including changed success/failure and artifacts, must return the conflict. Keep a genuinely identical-retry control that still receives the idempotent ACK. Verify the first stored result remains unchanged.

ROUTING_NOTE: This is the server result-endpoint contract. Do not treat the existing storage-layer DLQ-03 no-meaningful-change/revision-conflict test as proof that this endpoint compares the full result body.

### 2. Timed-out running threads retain executor capacity

FILE: `scripts/courier_continue.py`
FUNCTION: `main()`
RELATED_WORK: DLQ-08 / DLQ-04 bounded-drain work.

REPORTED_BEHAVIOR: After the 8-second timeout, a running Future is only removed from `running_tasks`. `cancel()` cannot stop an already running thread. Hung tasks retain ThreadPoolExecutor slots; five hangs can wedge all later work.

REQUIRED_REPAIR: Use a genuinely bounded/terminable execution boundary. Removing tracking entries or calling `cancel()` alone is not the requested repair.

REQUIRED_TEST: Repeated hangs must not exhaust effective execution capacity; a healthy sibling must still run after repeated hangs. Demonstrate bounded termination/cleanup of owned execution resources, not merely removal from `running_tasks`. Do not terminate unrelated processes.

### 3. INIT-planted evidence promoted by a differently named writer

FILE: `scripts/agent_handoff_ledger.py`
PATH: INIT PROVISIONAL -> next update by a differently named writer.
RELATED_WORK: DLQ-01 / DLQ-02 / DLQ-07 trust-root and binding-epoch work.

REPORTED_BEHAVIOR: INIT with a PROVISIONAL guard and caller-planted VALID MACHINE_ARTIFACT promotes on the next differently named writer to CANONICAL_ACCEPTED, CLEAN_IDLE=YES, and QUEUE_INDEPENDENT=YES.

REQUIRED_REPAIR: Require server-owned authenticated attestation plus binding epoch. Caller-selected `producer_id`, `verifier_id`, and `updated_by` strings are not a trust root. Historical string-only evidence remains untrusted and cannot establish acceptance.

REQUIRED_TEST: Preserve this exact INIT -> different-writer promotion counterexample as a regression. It must not become accepted simply by surviving a revision or changing names. A legitimate current independently authenticated attestation remains the positive control. Do not manufacture physical proof or silently upgrade historical records.

### Additional required repair: restore provider-lock enforcement

FILE: `server/app.py`
PATH: `claim_task()` before READY scanning.
RELATED_WORK: DLQ-05.

REQUIRED_REPAIR: Restore the missing `provider_locks` gate before READY scanning. Preserve unrelated READY work and existing physical/authorization gates; this request does not authorize a cluster-wide stop.

REPORTED_TARGETED_RESULT: 3 failed, 22 passed.
RESULT_BINDING: From the supplied independent review at REVIEWED_LOCAL_HEAD; exact command, test IDs, and raw log were not included in the handoff. Do not invent them or present this count as a rerun by the routing assistant.

## Owner execution and handback

Use the existing Google/Central production owner and its normal serialized ownership path. Preserve all future work, queued tasks, foreign edits, and physical gates. Do not replace or empty the deferred queue. Do not close future tasks, set completion flags, or claim global exhaustion from this handoff.

For each repair, return the exact candidate SHA, bounded behavioral reproducer/test command, expected versus observed result, and affected regression output. Follow the existing T0/T1/T2/T3 workflow and provide a complete implementation packet for independent Codex re-review. Passing this batch does not constitute physical acceptance or authorize merge, deployment, payment, publication, credential changes, or other gated effects.

## Original user-supplied handoff (verbatim)

> Courier Ledger/Motor handoff from independent Codex review. Route these to the existing Google/Central production owner; do not create a second writer and do not close future tasks. Reviewed local HEAD eba56edb837256857d123b64b74e81421009ebc0. First repair queue: (1) server/app.py task_result(): identical retry currently compares only result_id + worker_id. A second payload with the same IDs but SUCCESS changed to FAILURE and artifacts changed is incorrectly answered HTTP 200 ACK_DUPLICATE; authoritative first result remains intact. Require canonical DurableResult payload/digest equality for idempotent ACK; otherwise 409 CONTRADICTORY_DUPLICATE. Add same-ID/different-body test. (2) scripts/courier_continue.py main(): after the 8s timeout a running Future is only removed from running_tasks; cancel() cannot stop a running thread, so hung tasks retain ThreadPoolExecutor slots and five hangs can wedge all later work. Repair with a genuinely bounded/terminable execution boundary and test that a healthy sibling still runs after repeated hangs. (3) scripts/agent_handoff_ledger.py: INIT PROVISIONAL with caller-planted VALID MACHINE_ARTIFACT promotes on the next differently named writer to CANONICAL_ACCEPTED, CLEAN_IDLE=YES, QUEUE_INDEPENDENT=YES. Caller-selected producer_id/verifier_id/updated_by strings are not a trust root. Require server-owned authenticated attestation + binding epoch; historical string-only evidence stays untrusted. Also restore the missing provider_locks gate before READY scanning (current targeted result: 3 failed, 22 passed). Preserve all future work and physical gates; no fake closure.
