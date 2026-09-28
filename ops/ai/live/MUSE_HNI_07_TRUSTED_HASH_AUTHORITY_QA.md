# MUSE-HNI-07 checkpoint — TRUSTED_HASH_AUTHORITY_QA (read-only)

TASK_ID=MUSE-HNI-07 / OWNER=MUSE_C2_LAPIS_DUBHE / HOST=MAC / 2026-09-28T12:20Z
GATE=PRE_CODEX DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated).
CLAIM=ops/ai/wall_claims/MUSE_HNI_07_TRUSTED_HASH_AUTHORITY_QA.claim.json (atomic noclobber).
NOTE=scripts/local_swarm_claim.py absent repo-wide; wall-file convention used instead.

REUSED (not re-proven): MUSE_MAC_01_RUN1 subcase 3 (hash-glob boundary);
MUSE_SRC_TRUTH_STATES (state truth, G195 owner-action); result_id triple-authority
(known — cited only). MT-01..05 PASS (peer, do-not-repeat). No PRE_CODEX revalidation.

SUBCASES (source > prose; 0 executions, 0 source edits, ledger untouched):
S1 Expected-chain unbound: RUN1_EXPECTED_HASH_CHAIN has {{FINAL_SHA}}, zero minted
  values. Authority = future RUN_1 operator. Candidate-independent: BOUNDARY only.
S2 Upload authority = server: artifact_store.put re-hashes bytes (:94), rejects
  worker-claimed mismatch (:95-96). SOUND.
S3 Verify gate = equality only: app.py:490-491 compares artifacts, no re-hash.
  Independent witness = verifier process (verifier_id != worker_id :485) +
  verifier-lane re-hash of server copy. Boundary = artifact_store.py:6-8. SOUND.
S4 Adapter lane re-hashes locally (github_worker_adapter.py:99) — different trust
  root (adapter host FS) than server lane. No contradiction; evidence must name lane.
  A1 path-escape = known, cited only.
S5 Timeless bindings: no created_at in artifact records; idempotent re-upload
  within dispatch by design (artifact_id_for :43-49); cross-dispatch reuse blocked
  by BINDING_FIELDS check (:139). SOUND with boundary.
S6 result_id triple-authority = known finding, explicitly NOT repeated.

VERDICT=COMPLETE as candidate-independent QA (boundaries, not per-SHA values).
No FINAL_SHA needed. 0 contradictions. NEXT=MUSE-HNI-08 (replay equivalence).
