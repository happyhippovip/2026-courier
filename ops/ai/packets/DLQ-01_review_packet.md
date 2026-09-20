# REVIEW PACKET — DLQ-01 (Codex-ready, COMPLETE)

CURRENT_HEAD=50810001a4eec3bc431a4d3412666f850bf0c3c7
COMMITS_UNDER_REVIEW=none (scripts/agent_handoff_ledger.py unchanged since
7c495f8c; reviewed against code_base_head 0c8d1edd at HEAD 50810001)
TASK_ID=DLQ-01
PRIORITY=P0
OWNER=Google (attester protocol design)

INVARIANT (decided 2026-09-18, MUSE packet QA)=Self-created evidence NEVER
graduates to trusted prior evidence without independent attestation. Concrete:
a MACHINE_ARTIFACT counts toward has_physical_proof only if (a) producer_id and
verifier_id are pairwise distinct (already enforced), AND (b) neither equals any
updated_by recorded in ledger history since that evidence URL first appeared
(writer-independence across updates — the missing check), AND (c) producer /
verifier come from a server-derived attester authority, not self-asserted
strings ("arbitrary" rejection already exists; extend to authenticated
attester identity). Google owns threshold/policy design; (b) is the minimal
enforceable core.

BUG=Two-step self-acceptance via direct ledger writes. update() only rejects
caller-created evidence when the guard CHANGES in the same update
(agent_handoff_ledger.py:743-766). Evidence planted in step 1 (with compliant
distinct producer/verifier IDs and a pre-declared RUNTIME_ARTIFACT PASS citing
the planted URL) becomes "prior evidence" in step 2, when has_physical_proof
is computed from prior_evidence only (:681-688) — promoting to
CANONICAL_ACCEPTED + CLEAN_IDLE=YES with zero independent attestation.

EVIDENCE=/tmp/dlq01_refresh.py run 2026-09-18 at HEAD 50810001 — STEP1
PROVISIONAL, STEP2 CANONICAL_ACCEPTED + CLEAN_IDLE=YES on self-made VALID
MACHINE_ARTIFACT (exit 0, reproduced).

EXACT_FILE=scripts/agent_handoff_ledger.py
EXACT_FUNCTION=update() prior_evidence rule (:681-688) + caller checks
(:743-766) + acceptance branch (:715-726)

REPRODUCER=/tmp/dlq01_refresh.py (tmp ledger, unproven=[]; update1 plants
artifact with RUNTIME_ARTIFACT PASS pre-declared; update2 changes only a
record field with guard=None)

CURRENT_BAD_BEHAVIOR=Step-2 update with no new evidence accepts on planted
self-made proof.
EXPECTED_BEHAVIOR=Step-2 raises LedgerError (unattested prior evidence cannot
satisfy has_physical_proof); ledger stays PROVISIONAL.

TARGETED_TEST_COMMAND=python3 -m pytest tests/test_ledger_self_cert_rejection.py -q
(NEW — Google to implement: two-update self-cert rejection test, fails today)
NEGATIVE_TEST=Legitimate multi-writer evidence (independent producer/verifier
authority) still accepted; existing
tests/test_agent_handoff_ledger.py::test_reject_caller_created_machine_artifact
stays green.
AFFECTED_SUITE=tests/test_agent_handoff_ledger.py
tests/test_ledger_false_green_attack.py
tests/test_ledger_edge_conservation_regression.py (T2: 24 passed 2026-09-18)

REPLAY_CASE=Replayed identical plant blocked by history URL/SHA binding
(:738-758); new-URL plant per cycle is the open hole.
RESTART_CASE=N/A (single-process ledger file; history persists in bundle).
CONCURRENCY_CASE=writer_lock serializes; two writers planting distinct URLs
both enter history — independence check must cover all introducers.
PROVIDER_WAIT_CASE=N/A.

T0=py_compile scripts/agent_handoff_ledger.py OK 2026-09-18
T1=targeted test does not exist yet (this packet orders it)
T2=24 passed (3 ledger files, 2026-09-18)
T3=test_ledger_false_green_attack.py + test_ledger_edge_conservation_regression.py
green (in T2 run); node --test tests/test_execution_truth.mjs pass 1 fail 0

KNOWN_ATTACKS=test_same_update_evidence (blocked), test_replayed_evidence
(blocked), test_wrong_runtime (blocked), test_reject_caller_created_machine_artifact
(same-update only — bypassed cross-update, THIS packet)
FILES_TO_READ=scripts/agent_handoff_ledger.py:634-793
tests/test_agent_handoff_ledger.py:364-520
QUESTIONS_TO_ANSWER=1. Does writer-independence check (b) break the
Google-Antigravity motor path (:159/:386 strip MACHINE_ARTIFACT before update)?
2. Who derives the attester authority for check (c)? 3. Confirm NO production
ledger currently holds CANONICAL_ACCEPTED reached via self-planted evidence.

DEPENDENCIES=Google attester protocol design; no central-state change needed.
CAN_BATCH_WITH=DLQ-02 (same function, shared guard-validation tests)
READY_TO_IMPLEMENT=NO (design owned by Google; packet is complete and attacks live)

## IMPLEMENTATION FORGE (2026-09-18, HEAD d00a00a8 — additive, review above unchanged)

EXACT_GOOGLE_EDIT_SITES (scripts/agent_handoff_ledger.py, read-only refs):
- :681 prior_evidence comprehension — build introducer map alongside it by
  scanning bundle history exactly like :738-741 (url -> (first_rev,
  introducer_updated_by, operation)).
- :682-688 has_physical_proof — add conjunct: for evidence e counting toward
  proof, e.producer_id and e.verifier_id must not be in {updated_by of every
  history entry since e first appeared} and updated_by(current update) must
  not equal the introducer of e's URL. NO init exemption (see forensics).
- :743-766 caller checks — unchanged (same-update path already closed).

AFFECTED_CALLERS (all verified at HEAD):
- scripts/courier_continue.py:159/:384 (updated_by Google-Antigravity):
  strips MACHINE_ARTIFACT before update → introduces nothing → unaffected.
- scripts/feed_evidence.py:38 (updated_by System-Integration): introduces
  artifact producer MAC-MACBOOK-PRO-VON-USER-EDEA96 / verifier VERIFIER-01 →
  later promotion by Google-Antigravity stays legal (rev-81 shape). Promotion
  by System-Integration itself becomes illegal (intended).
- CLI update: operator promoting own plant with same --updated-by becomes
  illegal (intended — that IS the attack).
- CLI init with operator JSON: INIT-introduced URLs record the init writer as
  introducer; see DLQ-07 forge interaction (INIT stays PROVISIONAL AND its
  evidence stays non-promotable by the same writer).

NEGATIVE_TEST_MATRIX (executable guards, all green 2026-09-18):
- tests/test_ledger_fix_guards.py::test_legit_two_writer_accumulation_accepted
  (introducer A / promoter B / producer P / verifier V all distinct → promotes)
- existing test_reject_caller_created_machine_artifact (same-update → raises)
- existing test_replayed_evidence + copied-proof tests (unchanged behavior)

MIGRATION_MATRIX (live ledger forensics, /tmp/ledger_forensic.py, read-only):
- Root ledger rev 1227 PROVISIONAL: 4 past CANONICAL promotions (revs
  75/77/81/82, 2026-09-17). Revs 75/77/82 promoted by Google-Antigravity on
  evidence INTRODUCED at rev 0 by Google-Antigravity → flag under check (b).
  Rev 81 (System-Integration promoting Google-introduced evidence) = healthy
  shape the fix preserves.
- Consequence: after the fix, NO future promotion may rely on runs/1
  evidence promoted by Google-Antigravity; next acceptance needs fresh
  independently-introduced evidence. Nothing breaks immediately (ledger is
  PROVISIONAL with unproven work; fix gates future promotions only).
- tests/guard.json + record.json fixtures: PROVISIONAL/TEST → unaffected.
- tests/agent_handoff_ledger.json: TRACKED, corrupt (parse fails char 4584),
  referenced by zero tests → hygiene: Google confirms delete (Muse does not
  touch).

RESTART_REPLAY_CONCURRENCY:
- History-derived introducer map is bundle-persisted → restart-safe, no new
  state file, no cursor.
- Same-writer replay of a plant → blocked at promotion (intended).
- Concurrent distinct-URL plants → each URL checked against its own
  introducer; writer_lock serialization unchanged.
- DLQ-07 interaction: INIT-PROVISIONAL fix does NOT deduplicate this check —
  INIT plants are covered HERE at promotion time (no init exemption).

WAITING_FOR_CODEX_DECISION=attester-authority shape for check (c):
allowlist vs PKI vs server-derived role; quorum/threshold (1-of-N?);
whether producer/verifier registries live in central_state.json or config.
Check (b) above is implementable WITHOUT that decision — Google may ship (b)
first.

GOOGLE_ZERO_ARCHAEOLOGY=YES for check (b): sites, callers, negatives,
migration, and forensic evidence all above; only check (c) awaits Codex.

## CURRENT RED-TEAM RESULT — 2026-09-18

CODE_SHA=b0f6cec5e7a8e3ca64c9039792d239d2e67fe5ea

The landed T3 suite does not close check (c).  Two tests explicitly tolerate
the unsafe result instead of requiring fail-closed behavior:

- `TestRenamedIdentities.test_renamed_writer_still_blocked`
- `TestVerifierEqualsIntroducer.test_verifier_introduced_in_earlier_update_blocked`

A direct two-update reproduction with an `ISSUE_STATE` acceptance predicate
still reaches all of the following using only caller-selected identity
strings: `CANONICAL_ACCEPTED`, `CLEAN_IDLE=YES`, and
`QUEUE_INDEPENDENT=YES`.

REPRODUCED_VARIANTS=
- introducer `actor-v1`, acceptance writer `actor-v2`, arbitrary distinct
  producer/verifier aliases
- introducer `introducer`, acceptance writer `acceptor`, arbitrary
  `producer-string` / `verifier-string`

ROOT_CAUSE=`producer_id`, `verifier_id`, and `updated_by` are compared as
untrusted strings.  A different string is treated as independence even though
no authenticated principal or server-owned attestation record exists.

MINIMUM_GOOGLE_REPAIR=Fail closed for MACHINE_ARTIFACT proof unless it resolves
to a server-owned immutable attestation whose authenticated producer,
authenticated verifier, introducer, and acceptance-writer actor domains meet
the independence policy.  Ledger history may consume that verdict but must not
create or authenticate it.  Historical string-only evidence remains auditable
but cannot count toward acceptance.

TEST_GOOGLE_MUST_CORRECT=Both tests above must assert rejection of the current
bypass.  Add a positive control backed by the real server-owned attestation
trust root; do not substitute another collection of caller-provided names.

STATUS=OPEN_P0_TRUST_ROOT; current green T3 count is not closure evidence.
