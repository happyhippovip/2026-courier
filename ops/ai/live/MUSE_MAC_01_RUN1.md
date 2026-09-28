# MUSE MAC WINDOW 1 — RUN_1 Falsification (static, no physical execution)

TASK_ID=MUSE-MAC-01-RUN1
WINDOW=MUSE_MAC_WINDOW_1
HOST=MAC (`Darwin 25.6.0 x86_64`)
PROVIDER=MUSE / MODEL_CLASS=C2
MODE=PRE_PHYSICAL_FALSIFICATION (read-only contracts + existing evidence; 0 processes, 0 pytest, 0 server/worker starts)
TIMESTAMP=2026-09-28T11:45:00Z
GATE=PRE_CODEX_STATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated per order; single-owner rule kept)
LEDGER=untouched (SKIP) | SOURCE_EDITS=0 | PHYSICAL=0

PRIOR EVIDENCE REUSED (not re-run, not re-claimed):
- ops/ai/wall_results/MAC_HNI_01..10_result.md (all COMPLETE, boilerplate summaries, empty deliverable path ".")
- scripts/run1_physical/RUN1_*_CONTRACT.md + RUN1_RESULT_TEMPLATE.json + RUN1_EVIDENCE_LAYOUT.md + RUN1_PHYSICAL_BINDING_TEMPLATE.sh + RUNTIME_SOURCE_BINDING.json
- scripts/run1_physical/verify_proof_contracts.py (executable mirror of the contracts)
- ops/ai/live/MAC01_BINDING.md (candidate-independent Source/Build/Runtime/Config, FINAL_SHA UNBOUND)

METHOD: For each subcase, read the contract's exact check, then construct the cheapest
self-consistent counterexample (same-file self-report, renamed state, unwitnessed execution).
A subcase is FALSIFIED when the contract as written would still PASS on that counterexample
(i.e. the proof is insufficient). DISPROVEN means our falsification attempt failed against the
contract as written. No snapshot exists yet (RUN_1 PENDING, gate PENDING), so every dynamic
claim below is a contract-sufficiency verdict, not a RUN_1 execution verdict.

## Subcase 1 — A exactly once (RUN1_A_ONCE_PROOF_CONTRACT.md)

- Contract: `execution_counters.process_a == 1` in `run1_state_snapshot.json`.
- Attempt: snapshot author writes `process_a: 1` after running A zero times, twice with one crash before accounting, or three times with counter reset to 1. No PID, no task/attempt/dispatch id, no independent observer is consulted.
- Verdict: FALSIFIED (as sufficient proof). Counter is self-reported; unwitnessed executions are invisible. Matches the contract text exactly (single `.get()` read, `assert == 1`).
- Not a repeat: no prior RUN_1 finding names this self-report gap (MUSE-HNI-06 was 12-case scope labels).

## Subcase 2 — real Result A (RUN1_RESULT_TEMPLATE.json)

- Contract/template: `result: PENDING`, all `checks.*: false`, `final_sha: {{FINAL_SHA}}`, empty `timestamp`/`verdict_hash`.
- Attempt: treat the template as evidence of a real A result. It is a fill-in form: no artifact bytes, no exit code, no state hash bound. Any A outcome (including none) fits it.
- Verdict: FALSIFIED (as sufficient proof). Template proves shape, not reality. Real-Result-A evidence (exit code + snapshot + falsifiability hash per EVIDENCE_LAYOUT) does not exist yet — correctly so pre-RUN.
- Note: EVIDENCE_LAYOUT.md itself (6 files incl. `run1_falsifiability_hash.txt`) is sound as a list; the gap is that zero of the six exist.

## Subcase 3 — trusted expected hash (RUN1_EXPECTED_HASH_CHAIN.md)

- Contract: `compute_run1_chain(final_sha, dir)` hashes `final_sha + sorted(*.log, *.json)` bytes; `run1_falsifiability_hash.txt` is the artifact hash; ledger block hash binds completion.
- Attempt: (a) pre-RUN, `{{FINAL_SHA}}` is a placeholder — chain is unbound by construction; (b) post-RUN, whoever writes the evidence dir chooses which `*.log/*.json` files are present, so the chain attests to "these files" not "the right files"; (c) `*.txt` sidecars (`run1_exit_code.txt`, `run1_falsifiability_hash.txt`) are NOT included in the glob, so tampering with the exit code or the hash file itself does not change the chain.
- Verdict: FALSIFIED (as sufficient proof) on points (a)–(c). Strongest concrete sub-gap is (c): glob covers only `*.log` + `*.json`, excluding the two `*.txt` integrity files named by EVIDENCE_LAYOUT.
- Authority gap: no independent expected-hash source is named; the comparator arrives with the snapshot.

## Subcase 4 — server bytes exact (RUN1_SERVER_BYTES_PROOF_CONTRACT.md)

- Contract: serialize `payload` from the snapshot (`json.dumps(sort_keys=True)`), sha256 it, compare to `expected_server_bytes_hash` from the SAME snapshot.
- Attempt: snapshot author copies computed hash into expected field (or both from any payload). Check passes for arbitrary payloads, including empty `{}`.
- Verdict: FALSIFIED (as sufficient proof). Circular comparator: measured and expected share one author and one file. No independent server-received-bytes source is consulted. Exact wording ground: `payload = data.get('payload', {})` … `expected_hash = data.get('expected_server_bytes_hash')`, same `data`.
- Consequence: byte-exactness is asserted, not witnessed.

## Subcase 5 — Verify (RUN1_VERIFY_RECONCILE_PROOF_CONTRACT.md, first half)

- Contract: `VERIFY` present in `state_transitions`, timestamp recorded (last occurrence wins).
- Attempt: log containing only `VERIFY` with no `RECONCILE`, or `VERIFY` timestamp fabricated. Presence check passes regardless of what was actually verified (no verifier identity, no artifact hash, no verdict).
- Verdict: FALSIFIED (as sufficient proof of verification). Presence ≠ correctness. Contract proves a label was logged.

## Subcase 6 — Reconcile (same contract, second half)

- Contract: `RECONCILE` present, `verify_time < reconcile_time` strict, last-occurrence semantics.
- Attempt: (a) duplicate `VERIFY` after `RECONCILE` flips `verify_time` past `reconcile_time` → false FAIL on a good run (brittle, not unsound); (b) equal timestamps (`<=` case) correctly FAIL; (c) fabricated monotonic pair passes with no reconciliation work done.
- Verdict: FALSIFIED on (c) (same self-report root cause as subcases 1/4/5); ORDERING check itself (`<` strict) is sound and NOT disproven — attempt (b) fails closed as it should. Partial: ordering logic DISPROVEN as attack surface, log authorship still untrusted.

## Subcase 7 — B automatic start (RUN1_B_AUTOSTART_PROOF_CONTRACT.md)

- Contract: `process_b > 0`, `A_COMPLETE` before `B_START`, no `HUMAN_INTERVENTION` state.
- Attempt: (a) `process_b = 17` passes (`> 0`, not `== 1`) — B-once is not checked; (b) states logged by the same author that started B; an out-of-band human approval (chat, click, shell) leaves no `HUMAN_INTERVENTION` label and passes; (c) `A_COMPLETE`/`B_START` exact-string match — synonyms (`A_DONE`, `B_SPAWNED`) bypass both directions (false FAIL on good runs, false PASS if author avoids the tripwire label).
- Verdict: FALSIFIED (as sufficient proof). Autonomy is label-absence in a self-authored log, and B-once is unchecked.

## Subcase 8 — HUMAN_RELAY_COUNT=0 (RUN1_ZERO_RELAY_PROOF_CONTRACT.md)

- Contract: `execution_counters.human_relay_count == 0` (default `-1` fails closed — good) AND no transition state containing substrings `HUMAN`/`MANUAL`.
- Attempt: relay performed via channel with no counter increment and state named `OPERATOR_APPROVAL`, `GATE_CHECK`, or `RELAY_VIA_CHAT` — wait, `RELAY_VIA_CHAT` contains neither `HUMAN` nor `MANUAL` as substrings (`RELAY` ≠ `MANUAL`), so it passes. Any human step whose label avoids the two substrings passes.
- Verdict: FALSIFIED (as sufficient proof). Denylist of two substrings on a self-authored log; `-1` default is the one sound element (DISPROVEN attempt: omitting the counter fails closed).
- Clarification vs B-autostart: distinct check (counter + transition denylist vs B_START ordering + tripwire label); same root cause, different bypass strings.

## Subcase 9 — no FAILED execution (RUN1_FAILED_EXECUTION_GUARD.md)

- Contract: `run1_exit_code.txt` strips to `"0"` AND snapshot `final_status == 'SUCCESS'`.
- Attempt: author writes `"0"` into the exit-code file after a real non-zero exit, or runs the command via wrapper that always writes `"0"`. Both files share the evidence-dir author; no parent-process exit binding, no supervisor receipt.
- Verdict: FALSIFIED (as sufficient proof). Dual self-report; strict `"0"`/`SUCCESS` string checks are sound as format checks (DISPROVEN: `"0\n"` passes via strip — intended; `" 0 "` passes — intended; `"1"`/exit-missing correctly FAIL), but authorship is unwitnessed.
- Note: remediation clause (full host reset on failure, candidate rejection) is policy, not proof — sound as policy.

## BACKUP — RUN_1 evidence minimality (no deletions performed)

- Reviewed for redundancy/weakness WITHOUT deleting (destructive ops out of scope for this window; deletions need owner + backup):
- WEAK (propose quarantine, keep bytes): `ops/ai/wall_results/MAC_HNI_01..10_result.md` — 10 files, identical boilerplate summaries ("completed in candidate-independent mode… stored at ."), empty deliverable path, zero per-subcase content. They add claim-count without evidence. PROPOSAL: supersede with one pointer file to the contracts + this checkpoint, or regenerate per-subcase summaries; do NOT delete before backup.
- KEEP (real content): all 7 `RUN1_*` contracts + `RUN1_RESULT_TEMPLATE.json` + `RUN1_EVIDENCE_LAYOUT.md` + binding template + `RUNTIME_SOURCE_BINDING.json` + `verify_proof_contracts.py` (executable mirror — keep in sync with contracts by owner).
- REDUNDANT-BUT-KEEP (mirror, not duplicate): `verify_proof_contracts.py` duplicates contract logic in code — useful as runner, harmful if it drifts. PROPOSAL: owner adds a mirror-sync check (contract hash list) rather than deleting either side.
- Backup location for any future quarantine: `ops/ai/wall_results/_quarantine_2026-09-28/` (NOT created this turn; owner action).
- BACKUP=DONE_ASSESSMENT_ONLY (0 files moved, 0 deleted, 0 renamed).

## Checkpoint fields

DONE=9 subcases static-falsified in required order (A-once, real-Result-A, trusted-hash, server-bytes, Verify, Reconcile, B-autostart, HUMAN_RELAY_COUNT=0, no-FAILED) — exceeds 4-subcase minimum; 0 physical executions; 0 source edits; 0 ledger writes; gate not revalidated
NEW_FINDINGS=8 proof-sufficiency gaps (1 A-once self-report; 2 template-is-not-result; 3a chain-unbound-pre-RUN; 3c glob-excludes-*.txt exit-code+hash-file; 4 circular same-snapshot comparator; 5 presence≠correctness; 7 B>0-not-==1 + label-absence autonomy; 8 two-substring denylist bypass) + 1 minimality assessment (10 boilerplate MAC_HNI results propose-quarantine)
DISPROVEN=4 sound elements confirmed against attack: 6-ordering strict `<` fails closed on equal timestamps; 8-counter `-1` default fails closed; 9 `"1"`/missing correctly FAIL, strip behavior intended; entrypoint `scripts/run_physical.py` EXISTS (binder not dangling)
OPEN=All 8 gaps need owner decisions (independent observer/5-tuple binding for counts+bytes; expected-hash authority + `*.txt` glob inclusion; verifier-identity in VERIFY; B==1 + out-of-band relay policy; substring-denylist replacement); dynamic RUN_1 verdict itself stays PENDING until READY_FOR_PHYSICAL_RUN=YES + durable FINAL_SHA
NEXT=Claim next unique C2 task in priority order: MUSE-HNI-07 trusted-hash-authority QA (deepen subcase 3: expected-hash source + glob fix proposal), then MUSE-HNI-08 replay-equivalence QA; do NOT re-enter PRE_CODEX gate; do NOT re-run physicals

DO_NOT_REPEAT_FINGERPRINT=sha256-muse-mac01-run1-falsification-20260928

## Appendix S — Source-truth state hunt (MUSE-SRC-TRUTH-01, 2026-09-28T12:05Z, read-only)

- A: POST /tasks/result -> RESULT_RECEIVED confirmed (app.py:382,386; retry/terminal branch :388-392). B: PASS -> RECONCILED confirmed (:503-504; guards :476-493). No source errors, 0 edits.
- VPV: invented; G233 + old matrix S3 were the only occurrences — both peer-corrected in working tree (verified via git diff, accurate). Hands off.
- NEW: G195 claims `status=VERIFIED` + `verified_at` in state file — neither exists in server code (canon TASK_STATES integration_contract.py:16-23; verification dict app.py:496-501). Correction text in wall_results/MUSE_SRC_TRUTH_STATES_result.md; foreign file untouched.
- Full record: wall_results/MUSE_SRC_TRUTH_STATES_result.md (fingerprint sha256-muse-src-truth-states-20260928).
