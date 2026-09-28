# Result for MUSE-HNI-15 — RUN2_FALSIFIABILITY_QA (static)

TASK_ID=MUSE-HNI-15
AREA=RUN2_FALSIFIABILITY_QA
STATUS=OPEN
RESULTS_REUSED=RUN1 falsification class (MUSE_MAC_01_RUN1, HNI-13 — same self-report root cause, cited)
DELIVERABLE_OR_VERDICT=5 RUN2 proof-sufficiency gaps against contract text (0 executions, 0 source edits, ledger untouched): S1 no-replay counter resettable; S2 no run1->run2 snapshot/hash binding (NEW); S3 label-denylist + KeyError-on-malformed (mechanical); S4 global-count passes B-never-ran-in-RUN2 (NEW logic gap); S5 restart dir-hash unbound to FINAL_SHA (NEW). 2 sound elements (missing-key FAIL-closed; last-wins/order strictness by inheritance). Static only; dynamic RUN_2 PENDING (needs RUN_1 PASS first).
MISSING=Owner decisions on S2/S4/S5 mechanics + independent-witness binding (same class as RUN1).
BLOCKER=RUN_1 PASS (construction) + FINAL_SHA durability + READY_FOR_PHYSICAL_RUN (gate untouched).
NEXT_EXACT_ACTION=Claim MUSE-HNI-16 (restart race window).
DO_NOT_REPEAT_FINGERPRINT=sha256-muse-hni-15-run2-falsifiability-20260928

Inputs read (minimum-necessary): 4 RUN2 contracts (full) + run_physical_restart.py:47-57+88+147-151 (this run); prompt task line.
Commands/tests run: none (read-only; MAX_HEAVY_JOBS respected).
Ledger writes: none. Source edits: 0.
