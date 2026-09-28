# OWNER DEFECT PACKET — RUN2 contract mechanics (Wave B, from HNI-15)

SOURCE_FINDINGS: ops/ai/live/MUSE_HNI_15_RUN2_FALSIFIABILITY_QA.md (S2/S4/S5);
contracts: scripts/run2_physical/RUN2_A_PERSISTENCE_PROOF_CONTRACT.md,
RUN2_EXECUTION_COUNT_PROOF_CONTRACT.md, scripts/run_physical_restart.py:47-57.
No new search; no source edits; no revalidation; static only.

1) Global-count passes B-never-in-RUN2 (S4): total_b==1 holds for r1_b==1/r2_b==0.
   Add assert r2_b == 1 (and keep r1_a == 1, total_a == 1).
2) No run1→run2 snapshot binding (S2): run2.initial_state never compared against
   RUN1 snapshot/falsifiability hash. Add: initial_state must equal (or hash-match)
   RUN1's persisted A-state; require run1_falsifiability_hash.txt as input.
3) Restart dir-hash unbound to FINAL_SHA (S5): mix FINAL_SHA into compute_dir_hash
   (as RUN1 chain does) so identical dirs under different SHAs differ.

MIN ACCEPTANCE: contracts updated (3 asserts) + mirror updated in
verify_proof_contracts.py (sync per MAC_01 keep-note); static re-read of the 3 diffs.
MIN RETEST: targeted contract re-read on patched SHA (no physical run needed for
acceptance of the text fix; dynamic proof still needs RUN_1 PASS + RUN_2 auth).
EVIDENCE REQUIRED: unified diff of the 3 contracts + mirror; per-item before/after
verdict line referencing this packet.
BEFORE_CODEX=NO (RUN2-gated, post-RUN_1 logic; codex durability unaffected).
BEFORE_RUN1=NO. BEFORE_RUN2=YES (all three).
CAN_DEFER=NO for (1)(2) — correctness of RUN_2 verdict; YES for (3) only if RUN_2
evidence dirs are SHA-segregated by path (then hash-scope is implicit).
OWNER=RUN2-contract owner (Central Writer lane).
DO_NOT_REPEAT=sha256-muse-hni-15-run2-falsifiability-20260928.
