# MUSE-B-G195 — Evidence-Doc Correction Packet (Wave B, no source touch)

TASK_ID=MUSE-B-G195
AREA=EVIDENCE_DOC_DEFECT_PACKET
OWNER=MUSE_C2_SAFFRON_OCCULT / HOST=MAC / 2026-09-28
STATUS=FAMILY_COMPLETE
REUSED_FINDING=ops/ai/wall_results/MUSE_SRC_TRUTH_STATES_result.md subcase (4)
 (fingerprint sha256-muse-src-truth-states-20260928) — converted, not re-proven.
LIVE_CHECK_THIS_RUN=ops/ai/wall_results/G195_result.md:9 still contains the
 over-claim (single grep, 0 executions, 0 edits).

## Causal defect
CLASS=EVIDENCE_DOC_DEFECT (source is correct; prose is wrong).
G195_result.md:9 asserts accepted-result survival requires `status=VERIFIED`
 plus `verified_at`, "All fields verified in state file and ledger".
Source truth (Wave A, reused): `VERIFIED` as task status occurs NOWHERE in
 server/ (only `FAILED_VERIFICATION`); canon set is `TASK_STATES` in
 scripts/integration_contract.py:16-23
 (QUEUED/DISPATCHED/RESULT_RECEIVED/RECONCILED/FAILED_VERIFICATION/
 FAILED_TERMINAL/HUMAN_REQUIRED). Server never writes `verified_at`:
 verification dict server/app.py:496-501 =
 {verifier_id, result_id, verdict, artifacts} only.

## Minimal fix scope
MIN_FIX_SCOPE=1 file, 1 line. In ops/ai/wall_results/G195_result.md:9:
 replace `status=VERIFIED` with `status=RECONCILED` AND drop `verified_at`
 from "verified in state file" (or mark MISSING=verified_at persistence).
NEXT_OWNER=GOOGLE_CLI (file owner; foreign file — packet author does not edit).

## Minimal acceptance criteria
AC1: post-fix `grep -n "VERIFIED\|verified_at" G195_result.md` == 0 hits
 (excluding this packet's own references, if quoted).
AC2: line 9 names only canon states from integration_contract.py:16-23.
AC3: no other line in G195 asserts persistence of fields outside the
 app.py:496-501 verification dict without a MISSING marker.

## Minimal retest
MIN_RETEST=2 greps, 0 executions, 0 server starts, 0 pytest:
 R1: `grep -n "VERIFIED\|verified_at" ops/ai/wall_results/G195_result.md`
 R2 (reuse, already green in Wave A): `grep -rn '"VERIFIED"' server/`
 == 0 hits as task status. No re-proof of transitions (SUBCASES 1-2 reused).

## Evidence requirement
EVIDENCE=post-fix G195 file bytes + R1/R2 transcripts attached to the
 applying owner's result note. No snapshot, no ledger write, no gate touch.

## Classification
BEFORE_CODEX=NO (docs-only prose; codex gate consumes source bytes +
 checklist verdicts, not this line; no gate revalidation performed here).
BEFORE_RUN1=NO (runtime behavior unaffected).
CAN_DEFER=YES — with flag: must precede any evidence-index harvest that
 ingests G195 (else false-green propagates into DURABLE_EVIDENCE_INDEX);
 routed to CODEX_GATE_CHECKLIST_OWNER as watch-item, not as gate blocker.

DO_NOT_REPEAT_FINGERPRINT=sha256-muse-b-g195-packet-01
