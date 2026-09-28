# Result for MUSE-SRC-TRUTH-01 — Source-truth state hunt (code = truth)

TASK_ID=MUSE-SRC-TRUTH-01
AREA=SOURCE_TRUTH_STATE_HUNT
STATUS=OPEN (1 new doc correction proposed; 2 transitions confirmed; 1 peer correction verified hands-off)
RESULTS_REUSED=server/app.py (lines 352-514), scripts/integration_contract.py (TASK_STATES lines 16-23), scripts/courier_verifier.py (run_loop lines 94-151), ops/ai/wall_results/G195_result.md, ops/ai/wall_results/G233_result.md (working-tree correction observed), ops/ai/live/MUSE_MAC_STATE_TRUTH.md (peer subcases 1-4, not duplicated)
DELIVERABLE_OR_VERDICT=4 subcases against executable source (0 server starts, 0 pytest, 0 edits to source/ledger/foreign files):
(1) POST /tasks/result -> RESULT_RECEIVED CONFIRMED (app.py:382; :386 SUCCESS re-assert with "wait for independent /verify"; non-SUCCESS -> QUEUED retry / FAILED_TERMINAL at :388-392; guards 409 at :369-370/:373-374; ACK_RESULT_RECEIVED at :411; byte-identical 6-tuple -> ACK_DUPLICATE at :367-368). No source error.
(2) Verifier PASS -> RECONCILED CONFIRMED (app.py:503-504; FAIL -> FAILED_VERIFICATION :509). Guards verified real: must be RESULT_RECEIVED (:481), independent verifier_id != worker_id (:485), result_id + artifacts match (:488-491), verdict in {PASS,FAIL} (:493); RECONCILED resend same result_id -> ACK_DUPLICATE (:476-479). No source error. Missing timestamp fields (received_at/verified_at) are peer-owned (MUSE_MAC_STATE_TRUTH.md subcase 4) — cited, not repeated.
(3) VALIDATED_PENDING_VERIFY: 0 hits repo-wide in *.py/*.sh/*.json outside ops/ai; sole ops occurrence G233_result.md:9. Working tree 11:54-11:56 shows peer correction already applied to G233 (state-name replaced by RESULT_RECEIVED + pending_verification mechanism, with CORRECTION appendix) and full S1-S9 matrix rewrite to code truth (S3=RESULT_RECEIVED). Verified accurate via git diff (source lines match). HANDS OFF both files — SUPERSEDED_BY_PEER, no duplicate edit.
(4) NEW: G195_result.md over-claims `status=VERIFIED` + `verified_at` "All fields verified in state file and ledger" (MISSING=None). Source truth: "VERIFIED" as task status occurs NOWHERE in server/ (only FAILED_VERIFICATION); canon set is TASK_STATES in integration_contract.py:16-23 (QUEUED/DISPATCHED/RESULT_RECEIVED/RECONCILED/FAILED_VERIFICATION/FAILED_TERMINAL/HUMAN_REQUIRED). Server never writes verified_at (verification dict app.py:496-501 = verifier_id/result_id/verdict/artifacts only). "VERIFIED" literals exist only in physical-run snapshot scripts (run_physical.py:98, run_physical_restart.py:106 — different schema, not courier task state). File stable since 01:16, committed, foreign (GOOGLE_CLI) — NOT edited; correction text for owner: replace `status=VERIFIED` with `status=RECONCILED` and drop `verified_at` from "verified in state file" (or mark MISSING=verified_at persistence).
MISSING=Owner application of G195 correction text; Writer schema decision on timestamps (already peer-proposed, not re-proposed).
BLOCKER=None for QA (gate untouched; dynamic RUNs still PENDING by construction).
NEXT_EXACT_ACTION=Owner applies G195 one-line correction; C2 follow-up claims MUSE-HNI-07 (trusted-hash authority).
DO_NOT_REPEAT_FINGERPRINT=sha256-muse-src-truth-states-20260928

Inputs actually read (minimum-necessary): server/app.py:352-514, integration_contract.py:16-23+60-61, courier_verifier.py:94-151, wall_results/G195 + G233 (committed + working-tree diff), live/MUSE_MAC_STATE_TRUTH.md (peer scope check), grep repo-wide for VALIDATED_PENDING_VERIFY and "VERIFIED".
Commands/tests run: none (read-only grep + line reads; MAX_HEAVY_JOBS respected by abstention).
Source edits: 0 (source truth correct on all checked transitions). Foreign edits: 0 (peer-active files untouched). Ledger: untouched.
