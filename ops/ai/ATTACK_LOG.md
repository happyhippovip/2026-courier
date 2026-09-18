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
