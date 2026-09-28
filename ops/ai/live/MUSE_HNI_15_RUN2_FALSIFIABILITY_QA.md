# MUSE-HNI-15 checkpoint — RUN2_FALSIFIABILITY_QA (read-only, static)

TASK_ID=MUSE-HNI-15 / OWNER=MUSE_C2_LAPIS_DUBHE / HOST=MAC / 2026-09-28T13:26Z
GATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated).
CLAIM=ops/ai/wall_claims/MUSE_HNI_15_RUN2_FALSIFIABILITY_QA.claim.json (atomic).
Contracts read this run: all 4 RUN2_* + run_physical_restart.py:47-57+88+147-151.
0 executions, ledger untouched.

SUBCASES (RUN2 proof-sufficiency; same self-report class as RUN1 + 2 new mechanics):
S1 NO_A_REPLAY (==0): replay+counter-reset passes. FALSIFIED as sufficient proof.
  Sound: missing key -> -1 -> FAIL closed.
S2 A_PERSISTENCE ('COMPLETE'): snapshot asserts own provenance; NO contract binds
  run2.initial_state to RUN1's snapshot or falsifiability hash. Cross-snapshot
  binding gap (NEW, precise).
S3 B_CONTINUATION: VERIFY-absence + 'HUMAN'-substring + B_START-presence on
  self-authored log. FALSIFIED as sufficient proof. Mechanical: t['state'] direct
  access -> KeyError (crash) instead of clean FAIL on malformed entries.
S4 GLOBAL COUNT: total_b==1 passes r1_b==1/r2_b==0 — B ran in RUN1, never in RUN2,
  yet contract passes, contradicting continuation narrative. Logic gap (NEW).
  r1_a==1 asserted; r1_b unconstrained beyond the sum.
S5 Restart dir-hash (run_physical_restart.py:47-57) covers all files except
  *hash*.txt (broader than RUN1 glob) BUT mixes no FINAL_SHA: identical evidence
  dirs under different SHAs hash identically. SHA-binding gap (NEW, precise).

VERDICT=OPEN (5 gaps: 3 same-class + S2/S4/S5 new mechanics; owner decisions).
Static only; dynamic RUN_2 PENDING (RUN_1 PASS required first).
NEXT=MUSE-HNI-16 (restart race window).
