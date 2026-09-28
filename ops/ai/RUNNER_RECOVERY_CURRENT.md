# Courier Runner Recovery — CURRENT

Status: LOCAL STACK FOUND / PUBLICATION-GATED
Date: 2026-09-28

This file records the current durable handoff from the Mac Muse endgame wall.

## Confirmed local state

LOCAL_HEAD=e9b4f15f
BASE_REMOTE_CANDIDATE=34b0a4264bf763bc2a78f761ffba36e47706b2cf
LOCAL_STACK_LENGTH=12 commits
LOCAL_STACK_REMOTE_PRESENT=NO
FAST_FORWARD_PUBLICATION_REPORTED_POSSIBLE=YES

The Mac wall found the physical-runner stack locally and tracked-clean:

- scripts/run_physical.py
- scripts/run_physical_restart.py
- scripts/run1_physical/
- scripts/run2_physical/
- tests/test_run_physical*.py

The stack is local-only on a detached Mac HEAD and is not present on origin/candidate-b-1 or the coordination branch.

## Current technical classification

The local RUN_1 path has real process/HTTP/state boundaries, but current evidence reports remaining proof-risk where transitions are synthesized from counters, DONE may be rewritten to SUCCESS, process exit can remain 0, and relay count may be hardcoded.

RUN_2 execute path is still classified as simulated/synthetic and must not be treated as real physical proof.

The earlier verifier dict-artifact defect is reported already fixed inside local HEAD e9b4f15f.

## New reported gaps from recovery wall

- N1: stale execute_run1 test reference can raise AttributeError.
- N2: RUN_1 -> RUN_2 gate can be vacuous if unconditional exit 0 feeds the RUN_2 gate.
- transition/proof sourcing still needs exact owner review.
- live checkpoint/fingerprint transport is not durable cross-host unless material is published/tracked.

## Current phase

CURRENT_PHASE=BEFORE_RUN1
RUN1_PREP_COMPLETE=NO
RUN2_PREP_COMPLETE=NO
CORE_FREEZE_PREP_COMPLETE=NO

## Required next order

1. PUBLISH_DECISION
   - designate one PUBLISH_ONLY owner on the Mac stack;
   - publish the exact 12-commit stack without modifying application bytes;
   - record remote branch + exact SHA.

2. POST_PUBLISH_FIXED-BYTES REVIEW
   - review exact published bytes only;
   - classify reusable/invalidated evidence;
   - do not redo unrelated historical review.

3. SOLE WRITER EXACT FIX PASS
   - only confirmed remaining defects from N1/N2/transition sourcing/Real Producer review;
   - targeted tests;
   - exact new SHA.

4. REAL PRODUCER GREEN
   - no fabricated/self-authored proof;
   - RUN_2 simulation removed from any path required for proof.

5. MAC EXACT BINDING

6. SINGLE PHYSICAL OWNER RUN_1

7. RUN_2

8. CORE FREEZE

## Ownership

Muse remains READ_ONLY.
Google workers may prepare/review.
Application-source changes require exactly one explicit SOURCE_WRITE owner.
Publishing the already-existing local stack may be assigned as PUBLISH_ONLY; that grant does not authorize source edits.
Physical execution remains exactly one Physical Mac Owner.

## Premium model routing

Do not spend Claude/Opus on publication or routine prep.
Escalate only if post-publish exact-byte review exposes a genuinely unresolved high-risk correctness decision.

## Stop repeating

Do not repeat:
- remote absence discovery;
- local runner discovery;
- acceptance-harness false-proof finding;
- frozen Ledger work.

Next useful trigger is publication of the exact local stack or an explicit non-publication ruling.
