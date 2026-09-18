# ATTACK PACKET — DLQ-07 fix over-blocks legitimate INIT (REGRESSION from 8918bc8f)

CURRENT_HEAD=9837e5ae735f3075bffa9d3bdf6509002692e1ca
COMMITS_UNDER_REVIEW=
- 8918bc8f Fix DLQ-07: INIT is never CANONICAL_ACCEPTED, reject planted validation
TASK_ID=DLQ-07-FOLLOWUP (regression on a Muse-ordered fix; not a new hole)
PRIORITY=P0 (red suite: 6 tests)
OWNER=Google (ledger production file — PACKET ONLY, no Muse edit)

INVARIANT (required)=INIT must refuse CANONICAL_ACCEPTED/CLEAN_IDLE starts
(DLQ-07, holds) WITHOUT making INIT-with-well-formed-VALID-evidence
impossible. Well-formed PROVISIONAL bundles carrying VALID artifacts must keep
initializing; attestation is enforced at PROMOTION time (DLQ-01 check b),
not by destroying evidence at creation.

BUG=8918bc8f demotes every VALID MACHINE_ARTIFACT at INIT to validity
"INVALID" — but "INVALID" is not a member of EVIDENCE_VALIDITY
({"VALID","STALE","UNKNOWN"}, scripts/agent_handoff_ledger.py:82), so
validate_guard raises "evidence validity is invalid" for ANY bundle that
carries a VALID artifact at INIT. The demotion loop is dead code in effect:
it never produces a loadable bundle, only a different error. Consequence:
6 committed tests fail at SETUP (all initialize with VALID artifacts):
tests/test_ledger_false_green_attack.py (5: preset_canonical,
same_update_evidence, replayed_evidence, wrong_runtime, substring_success)
and tests/test_ledger_duplicate_semantics_contract.py (Google's own DLQ-03
test). The false-green suite CANNOT be restructured to comply — planting
VALID artifacts at INIT is precisely what those attacks must test.

EVIDENCE=pytest at HEAD 9837e5ae: 6 failed (all at initialize/setup with
"validity is invalid"); DLQ-07 hole itself verified CLOSED via
/tmp/ledger_redteam2.py fam_d ("INIT cannot start with CANONICAL_ACCEPTED").
DLQ-01/02 probes (update-path plants) still reproduce — unaffected.

EXACT_FILE=scripts/agent_handoff_ledger.py
EXACT_FUNCTION=initialize() demotion loop (8918bc8f hunk) vs
EVIDENCE_VALIDITY set (:82) vs validate_guard validity check

REPRODUCER=python3 -m pytest tests/test_ledger_duplicate_semantics_contract.py -q
(fails at initialize) or any false-green test above.

CURRENT_BAD_BEHAVIOR=Legitimate INIT with VALID evidence raises; 6 tests red.
EXPECTED_BEHAVIOR=INIT with VALID evidence + PROVISIONAL transition succeeds;
CANONICAL/CLEAN_IDLE starts still raise; the 6 tests return green unmodified.

TARGETED_TEST_COMMAND=The 6 failing tests ARE the targeted tests (no new file
needed — they fail today, must be green post-repair).
NEGATIVE_TEST=fam_d stays blocked (INIT-CANONICAL raises); preset
CLEAN_IDLE=YES still raises; tests/test_ledger_fix_guards.py 4/4 stays green
(verified at HEAD — guards use artifact-free INIT, unaffected).
AFFECTED_SUITE=tests/test_ledger_false_green_attack.py,
tests/test_ledger_duplicate_semantics_contract.py

REPLAY_CASE=Unchanged (history/URL binding untouched by this hunk).
RESTART_CASE=Unchanged (no new persisted state).
CONCURRENCY_CASE=Unchanged (writer_lock untouched).
PROVIDER_WAIT_CASE=N/A.

T0=py_compile OK (no syntax issue — logic error).
T1=6 tests fail at setup (this packet).
T2=Unaffected suites green: fix_guards 4/4, agent_handoff_ledger,
edge_conservation (23 passed combined at HEAD).
T3=Same statement (attack suites partially red ONLY via setup).

KNOWN_ATTACKS=Zero-update CANONICAL (closed, stays closed under either
repair); INIT-plant-then-promote (DLQ-01 check b territory, orthogonal).

EXACT_REPAIR_OPTIONS (Google picks; Muse does not edit):
- Option A (recommended, matches evident intent): add "INVALID" to
  EVIDENCE_VALIDITY. Demoted evidence becomes inert-but-loadable; INIT
  succeeds PROVISIONAL; has_physical_proof (validity=="VALID" check)
  still excludes it; the 6 tests go green unmodified.
- Option B: drop the demotion loop, keep the two raises. INIT with VALID
  evidence succeeds PROVISIONAL with the plant intact; promotion-time
  checks (DLQ-01 b) remain the enforcement point. Smaller diff, weaker
  defense in depth.
- Explicitly NOT recommended: restructuring the 6 tests to avoid VALID
  artifacts at INIT (would gut attack coverage — forbidden weakening).

FILES_TO_READ=scripts/agent_handoff_ledger.py:82, 616-650 (initialize)
QUESTIONS_TO_ANSWER=
1. Option A or B (or a third shape)?
2. Should demoted-"INVALID" evidence remain visible in history for forensics,
   or be stripped at INIT?
3. Grandfather: any persisted bundles already containing "INVALID" (from the
   brief window this code is live)?

DEPENDENCIES=None.
CAN_BATCH_WITH=DLQ-01 check-b implementation (shared promotion-time logic).
READY_TO_IMPLEMENT=YES (one-line set addition under Option A).
