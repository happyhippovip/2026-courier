# SLOT 01 — LANE 01 EXPECTED_HASH_AUTHORITY (GOOGLE WINDOWS WALL, READ_ONLY)

STALENESS=SUPERSEDED — gathered on 34b0a42; HEAD is now 9dba150 (verified this session). Re-verify cites before reuse.
SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf (HEAD via .git/refs/heads/fix-cb1-new)
RUN_ID=NONE (no RUN1/RUN2 evidence: artifacts/ absent, logs/ no matches)
PHASE=SONNET_BLOCKED_PRE_RUN1 (Sonnet HIGH BLOCKED on this SHA; fix owned by sole writer)
GATE_NOTE=GATE_STATE_CURRENT.md ABSENT on this tree; WALL_QUEUE_CURRENT.md=TRUE_IDLE, PRE_CODEX_READY=NO
PRIOR fingerprints (e5751783-era: OVERNIGHT 01-03, M1_M9, MUSE9, TRUSTED_HASH line refs) treated as STALE for cites; mechanisms re-verified below on current reads.

## Subcases (complete lane, all 6)

CASE=A_TASK_OWNED_EXPECTATION_AUTHORITY
SHA=34b0a42 RUN_ID=NONE
SOURCE_TRUTH=scripts/courier_verifier.py:78 task_expected from task.get("expected_artifacts",{}).get(path) or task.get("expected_sha256"); server bytes re-hashed :80 and compared; worker value never read as expectation
ACTUAL_EVIDENCE=NONE (no live verification observed)
REUSED_EVIDENCE=TRUSTED_HASH Fall A/E (mechanism agrees; old line refs discarded)
VERDICT=PROVEN (source) FALSE_GREEN_RISK=LOW (static-only) MISSING=live PASS observation
SOURCE_FIX_REQUIRED=NO PHYSICAL_ACTION_REQUIRED=NO OWNER=N/A

CASE=B_WORKER_SHA_IS_VERIFIED_CLAIM_NEVER_EXPECTATION
SHA=34b0a42 RUN_ID=NONE
SOURCE_TRUTH=artifact_store.py:150 worker-claimed sha must EQUAL independently recomputed server-bytes hash (plus size/name/binding :152-158); local branch :90 recomputes from disk :24-34 and compares. Worker sha is always the compared value, never the comparator.
ACTUAL_EVIDENCE=NONE
REUSED_EVIDENCE=TRUSTED_HASH Fall B (mechanism agrees; stale refs discarded)
VERDICT=PROVEN (source) FALSE_GREEN_RISK=LOW MISSING=live tamper-case observation
SOURCE_FIX_REQUIRED=NO PHYSICAL_ACTION_REQUIRED=NO OWNER=N/A

CASE=C_OMISSION_FAILS_CLOSED
SHA=34b0a42 RUN_ID=NONE
SOURCE_TRUTH=courier_verifier.py:63 expected-paths subset check → FAIL; :66-68 empty artifacts → FAIL
ACTUAL_EVIDENCE=NONE
REUSED_EVIDENCE=TRUSTED_HASH Fall C (mechanism agrees)
VERDICT=PROVEN (source) FALSE_GREEN_RISK=LOW MISSING=live omission observation
SOURCE_FIX_REQUIRED=NO PHYSICAL_ACTION_REQUIRED=NO OWNER=N/A

CASE=D_MISSING_EXPECTATION_INTEGRITY_ONLY
SHA=34b0a42 RUN_ID=NONE
SOURCE_TRUTH=:78-82 expectation check skipped when task carries none; :83 verify_uploaded_artifact still enforces hash/size/name/binding self-consistency (:147-159). Legacy = absence-driven, no separate flag.
ACTUAL_EVIDENCE=NONE
REUSED_EVIDENCE=TRUSTED_HASH Fall D + Q009 LEGACY_NO_TASK_EXPECTATION (semantics agree)
VERDICT=PROVEN-structure (source) FALSE_GREEN_RISK=LOW MISSING=live legacy-case observation
SOURCE_FIX_REQUIRED=NO PHYSICAL_ACTION_REQUIRED=NO OWNER=N/A

CASE=E_DICT_TASK_ARTIFACTS_EXCEPTION_NOT_FAIL
SHA=34b0a42 RUN_ID=NONE
SOURCE_TRUTH=courier_verifier.py:62 set(task.get("artifacts") or []) raises TypeError on dict entries; run_loop :145-147 catches per-task → log + skip WITHOUT verdict post → task wedges RESULT_RECEIVED. Authority NOT bypassed (no PASS reachable); availability breaks. == Sonnet BLOCKED defect, re-grounded on current SHA.
ACTUAL_EVIDENCE=NONE (no live crash observed; static mechanism proof)
REUSED_EVIDENCE=WALL_02 head-check (same mechanism on e5751783; site moved :114-117→:62 on this SHA); Sonnet BLOCKED verdict (accepted, not re-reviewed)
VERDICT=PROVEN-defect (source) FALSE_GREEN_RISK=LOW MISSING=live crash instance (must never occur post-fix)
SOURCE_FIX_REQUIRED=YES (SOLE_WINDOWS_WRITER owns; see WRITER_PACKET below) PHYSICAL_ACTION_REQUIRED=NO OWNER=SOLE_WINDOWS_WRITER

CASE=F_BUILD_GUARD_DOES_NOT_PROTECT_VERIFIER_PATH
SHA=34b0a42 RUN_ID=NONE
SOURCE_TRUTH=integration_contract.py:84-89 requires str artifact entries (ContractError otherwise) — build flow only. POST /goals stores workflow_plan opaquely, zero artifact validation (server/app.py:110-118); planner steps carry no artifacts key (:140-147). Dict-shaped defs reach verifier :62 via intake.
ACTUAL_EVIDENCE=NONE
REUSED_EVIDENCE=WALL_02 INTAKE_GAP (re-verified current lines)
VERDICT=PROVEN (source) FALSE_GREEN_RISK=LOW MISSING=live malformed-intake instance
SOURCE_FIX_REQUIRED=YES (same owner; intake validation = optional hardening, guard at :62 = required) PHYSICAL_ACTION_REQUIRED=NO OWNER=SOLE_WINDOWS_WRITER

## WRITER_PACKET (reference, no design duplication; Sonnet BLOCKED already owns this)
WRITER_PACKET=REF_CASE_E_DICT_TASK_ARTIFACTS
SHA=34b0a42 FILES=scripts/courier_verifier.py:62 (+optional server/app.py:110-118)
CAUSAL_DEFECT=set() over task artifact definitions assumes hashable (str) entries; dict entries raise TypeError before any FAIL path; run_loop skip leaves RESULT_RECEIVED without verdict
REPRO=goal with step artifacts=[{"path": "x.txt", "sha256": "y"}] + posted SUCCESS result → verifier task poll → exception + skip, never FAIL/PASS
MIN_SAFE_FIX=normalize/guard task-side entries before set membership (non-str → FAIL closed); optionally schema-validate artifacts at intake (400)
NEGATIVE_TEST=dict-artifact task → expect FAIL verdict posted, zero exception
POSITIVE_TEST=str-artifact task + matching bytes → PASS unchanged
REGRESSION_SCOPE=verifier subset/omissionFAIL paths (:63,:66-68); upload-flow suite; intake suites (if intake validation added)

## PHYSICAL_PACKET
NONE (no runtime action needed; fix + tests are writer-side)
