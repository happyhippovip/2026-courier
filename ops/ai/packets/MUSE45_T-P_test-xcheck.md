# MUSE-45 T-P — Test cross-check for M-/O-findings (read-only)

Branch fix-cb1-new @ 329abd80. Static only. No edits but this packet.

## T-N refinement: fail-closed PINNED, prompt_via half-built

- tests/test_muse_supervisor.py:286-296 test_unconfirmed_prompt_method_fails_closed
  pins: empty caps -> raise; prompt_via=arg WITHOUT protocol -> raise ("flag not
  confirmed"); protocol=headless-v1 -> argv with prompt last, stdin None.
- So the SUITE knows prompt_via as vocabulary, but PRODUCTION
  (muse_adapter.py) never reads it: the flag is half-built — asserted as
  insufficient-alone, never asserted as declared-with-protocol.
- T-N verdict stands with this refinement (see pointer in T-N packet):
  mechanism arg-OBSERVED, declaration UNCONFIRMED, fail-closed on missing
  protocol TEST-PINNED. Close = prod reads prompt_via + test asserts the pair.

## O4 (NATIVE echo shell sink): UNPINNED — boundary test misses the gap

- run_native is monkeypatched out in contract/recovery/upload tests (real
  implementation untested there).
- tests/boundaries/run_boundaries.py:218 calls the REAL run_native with
  action="rm_rf_slash" / instruction="rm -rf /" and expects FAILED/not-allowed.
  That pins the REJECTION path (unknown action) only.
- NO test covers the smuggling path: allowlisted action (echo, incl. first-word
  parse :259-262) with a malicious tail ("echo ok; <anything>") still executes
  the full string via shell=True (:275). The boundary test demonstrates the
  author's mental model (allowlist=safe) while missing the first-word/full-string
  gap. O4 stands open and unpinned. Owner: constrain echo to argv/no-shell or
  pin the smuggling case as a regression test first (shell session needed).

## M1/M3/O-path: unpinned LOWs stand

- M1 (bash -c f-string spawn): tests stub the muse binary (:61 muse.sh); no
  quoting test. LOW stands.
- M3 (int(argv) unguarded): no CLI-arg robustness test seen. LOW stands.
- O1/O2/O3/O5/O6: no pinning tests seen (daemon internals mocked at boundaries).
  O3's reroute (:522-524) + O4's sink (:275) chain remains the notable pair.

## muse_prompt.md: GOOD, no finding

- 6-line template: bound-task-only, no invented IDs/refs/commits/work,
  evidence-only branch/commit/next_task, fenced-json SUCCESS/FAILED.
  Tight contract matching the adapter's no-guessing discipline.
