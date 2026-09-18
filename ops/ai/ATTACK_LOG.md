# LEDGER/GUARD ATTACK LOG (Muse red team — append-only)

HEAD 82bbe090 (2026-09-18). Ledger code unchanged since 7c495f8c-equivalent.
Probes: /tmp/dlq01_refresh.py, /tmp/dlq02_refresh.py, /tmp/dlq03_refresh.py,
/tmp/ledger_redteam2.py (throwaway, referenced by packets).

## CONFIRMED HOLES (packetized, live)

- two-update self-acceptance → ops/ai/packets/DLQ-01_review_packet.md
- stale-dated VALID artifact → ops/ai/packets/DLQ-02_review_packet.md
- zero-update preset CANONICAL via initialize() → ops/ai/packets/DLQ-07_review_packet.md

## CONFIRMED VARIANTS (same root cause, no new packet)

- A future-ts 2030 promotes (DLQ-02 invariant covers both directions)
- B ghost producer/verifier strings promote (DLQ-01 authority check covers)
- C victim runtime_binding string spoof promotes (DLQ-01 authority covers)

## VERIFIED BLOCKED (do not re-attack without code change)

- same-update evidence consumption (test_same_update_evidence, green)
- replayed evidence (test_replayed_evidence, green)
- copied URL with changed SHA/runtime (test_reject_copied_proof, green)
- caller-created artifact same-update (test_reject_caller_created_machine_artifact, green)
- arbitrary producer/verifier literals (test_reject_arbitrary_producer_verifier, green)
- wrong runtime (test_wrong_runtime, green)
- preset CANONICAL via update path (test_preset_canonical_accepted, green)
- false PROVEN_EDGES without proof (test_bare_external_names..., green)
- stale-writer revision conflict (test_separate_process..., green)
- identical retry / stale contradictory (DLQ-03 probe + contract, holds)
- DLQ-03 CLOSED END-TO-END 2026-09-18: Google landed
  tests/test_ledger_duplicate_semantics_contract.py (20ca0601); Muse
  independently re-ran green at HEAD and reviewed assertions against the
  decided invariant — identical-retry raises + bytes unchanged,
  genuine-update advances, stale-contradictory raises conflict +
  authoritative value kept. Exact match. Queue IMPLEMENTED_AND_VERIFIED
  confirmed.
- CONTINUOUS iteration (HEAD 5a8befb7): ceba1fe0 motor double-submission fix
  reviewed (3-line continue, no timeout added — DLQ-08 still live);
  test_motor_dlq04_adversarial 1/1 + continue suite 15/15 re-verified;
  motor-batch packet repaired additively (real numbers replace unverified
  claims); DLQ-06 behavioral tests FAIL 2/1 on unfixed code (declared red,
  parked for Google retry — never weaken); DLQ-06 Codex packet completed
  additively (HEAD/commits/T2/T3/attacks/questions); Windows worker commands
  restored as separate packet (foreign rewrite preserved).
- CONTINUOUS iteration 5 (worktree draft, UNCOMMITTED foreign work, reviewed
  read-only 12:06 UTC): Google is implementing DLQ-01 check-b (introducer_map
  in update, no init exemption — matches forge), 48h recency window (172800s
  in has_physical_proof) + future-rejection in validate_guard, monotonicity
  per URL, and REMOVED the DLQ-07 demotion loop (over-block resolved).
  VERIFIED: DLQ-01/02/A/B/C/D all blocked, DLQ-03 holds, ledger suites 29/29
  green (incl. the 6 previously-red). REVIEW NOTES for owner (not edited):
  (1) duplicated future-check block + leftover deliberation comments in
  validate_guard — cleanup before commit; (2) new DEBUG prints
  (introducer_map/updated_by/unproven) pollute output — remove; (3) WATCH:
  server/app.py provider_locks enforcement gate removed (blank line left) —
  if committed as-is, DLQ-05 is silently disabled; needs owner intent;
  (4) race test file still deleted in worktree — restore/flip, do not drop.
  Foreign w1-to-w2 edit of test_ledger_fix_guards.py reviewed: consistent
  with check-b, passes, left in place.
- CONTINUOUS iteration 4 (HEAD 9837e5ae): Google landed DLQ-06 retry
  (3039126e, verified working via harness), DLQ-07 INIT gate (8918bc8f,
  verified closed via fam_d), DLQ-08 abandon (bbc86b56, code-reviewed),
  stall-test W2 update (fc1f42dd, converged with Muse design). Findings:
  DLQ-07 fix OVER-BLOCKS (VALID at INIT demoted to non-member "INVALID" ->
  6 tests red incl. Google's own contract test; packet DLQ-07-FOLLOWUP with
  options A/B, no production edit). Stale tests updated without weakening:
  resume (lock-aware), stall (W1-locked/W2-continues + lock-clearing reset),
  eligibility waiting (W2 true-negative), protected (verifier header;
  058be78c-bisect-proven). worker_quota_pools never populated in prod code
  (effective key worker_id:provider). Author bracket-typo ([REDACTED] vs
  TEST) caused all probe-401s; byte-scan discipline adopted. Import-order
  fragility documented (isolation passes standalone only). One historical
  pytest-401 cluster remains mechanically unisolated (torn-read during
  concurrent foreign write is the leading theory; 10+ greens since).
- preset CLEAN_IDLE=YES + PROVISIONAL guard (probe E 2026-09-18, blocked)
- VALID-marked mismatched SHA/runtime (validate_guard :261-264, structural)

## DESIGN-BLOCKED (needs Google authority decision, not more probes)

- same actor behind distinct producer/verifier/writer strings (undecidable at
  code layer; needs attester PKI/allowlist — DLQ-01 check c)
- freshness window length + clock authority (DLQ-02 policy)
- INIT attestation authority if INIT-CANONICAL ever allowed (DLQ-07 Q1)

## MOTOR verdicts (this round)

- DLQ-04 fix verified: tests/test_courier_continue.py 15/15 at HEAD 82bbe090
  → ops/ai/packets/CODEX_motor-batch-DLQ04-DLQ06.md (CODEX_READY=YES)
- DLQ-06 tripwire live: tests/test_windows_ledger_race.py passes-while-broken
  (must flip with fix)
- DLQ-08 NEW HOLE: hung task wedges motor — bare future.result() :527, zero
  deadline identifiers in file; bounded owned-PID demo proves indefinite block
  → ops/ai/packets/DLQ-08_review_packet.md (owner foreign/motor, packet only)
- Families green at HEAD (6 passed): restart/resume torture, stale-writer,
  auto-replenishment, result duplicates, queue independence x2
- Audited clean (structure + ledger-side guards): NEXT_EXECUTABLE_ACTION=NONE
  only alongside proven+proof branches (:344/:363); motor-side CLEAN_IDLE
  recomputed by ledger update() anyway

## EVIDENCE-TRUST verdicts (this round)

- Per-type matrix: MACHINE_ARTIFACT trust root = producer/verifier strings +
  SHA/runtime string-match + observed_at format — ALL self-asserted, none
  authenticated. Every downstream hole (DLQ-01/02/07 + A/B/C variants) is this
  single root cause wearing different clothes. Only structural mitigations
  (writer-independence history check, recency window, INIT-PROVISIONAL) work
  without an attester authority.
- GITHUB_* types inherit URL-retrievability assumption — NOT probed (network);
  marked open, not claimed.
- Windows prep: DLQ-06 behavioral harness /tmp/windows_ledger_race_inject.py
  demonstrates writer-side PermissionError crash under simulated Win32
  semantics → ops/ai/packets/WINDOWS_DLQ06-race-prep.md (zero Windows claims)
- iter6 (2026-09-18T12:11:42+02:00): checkpoint state-lag corrected
  (fields named 2ee8d905, live HEAD/push already 8c194f54); HEAD equals
  origin, no drift; foreign session ACTIVE (heartbeat seconds old) -
  hands-off, 8-file draft still uncommitted; no test runs (hot session)
