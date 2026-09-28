# MUSE-HNI-12 checkpoint — CHANGED_ARTIFACT_RESULT_QA (read-only)

TASK_ID=MUSE-HNI-12 / OWNER=MUSE_C2_LAPIS_DUBHE / HOST=MAC / 2026-09-28T13:02Z
GATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated).
CLAIM=ops/ai/wall_claims/MUSE_HNI_12_CHANGED_ARTIFACT_RESULT_QA.claim.json (atomic).
REUSED: contract:148-171, artifact_store put/check_reference, app.py:377-379+490-491,
adapter:98-100 (prior reads); A1 adapter-escape + RUN1 glob boundary (known, cited).

SUBCASES (changed artifact/result; 0 executions, ledger untouched):
S1 Changed sha256 vs uploaded bytes -> put rejects (artifact_store:95-96). SOUND.
S2 Absolute/traversal path -> 400 unsafe path (contract:165-169; server lane).
  Adapter-lane A1 escape = known, cited only. No new claim.
S3 Changed artifact list between intake and verify -> 400 (app.py:490-491). SOUND.
S4 artifact_id shape art-[hex64] (:159-160) + size non-neg int (:161-162) enforced.
  SOUND.
S5 SUCCESS evidenceless -> 400 (:150-151). SOUND (HNI-09 reuse).
S6 Unknown artifact keys -> invalid evidence (:154-156 set-membership). SOUND.
S7 Falsifiability-chain glob (*.log/*.json only) boundary -> HNI-07 S1 cite.

VERDICT=COMPLETE (candidate-independent; 0 contradictions, 0 false-greens).
NEXT=MUSE-HNI-13 (RUN1 falsifiability — static only, no physical).
