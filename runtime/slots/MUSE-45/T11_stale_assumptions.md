# T11 RESULT — Stale-assumptions sweep (docs vs code, read-only)

MODE: shell-less LIGHT. Current-HEAD evidence: .git/HEAD names
refs/heads/ledger-reconciliation-final (not detached); loose ref reads
b927f106cc45b9e69be81df81baa2dada55066fa. Worktree-dirt UNKNOWN (no shell).

## Findings

S-T11-1 (MEDIUM) COORDINATION DOCS BOUND TO 8-DAY-OLD SHAs.
- ops/ai/MUSE_CONTINUOUS_WORK.yaml: last_verified_head 955c1261 (2026-09-18)
- ops/ai/NEXT_WORK.yaml: code_base_head eba56edb (2026-09-18)
- ops/ai/OWNERSHIP_MAP.yaml + TEST_MAP.yaml: bound 0c8d1edd (2026-09-18)
Current loose ref: b927f106. OWNERSHIP_MAP's own rule says
ownership_must_be_revalidated=true — revalidation is 8 days overdue.
Content may still be right; the BINDINGS are stale. Owner: doc stewards.

S-T11-2 (MEDIUM-LOW) TEST_MAP NAMES A TEST THAT DOES NOT EXIST.
TEST_MAP.yaml:35-37 assigns lane T1 to test_windows_ledger_race.py.
Repo-wide filename search: 0 hits. NEXT_WORK MEMORY-NEXT-08 shows the DLQ-06
test now lives as tests/test_ledger_windows_permission_retry.py (exists) —
the file was renamed and TEST_MAP never followed. The other TEST_MAP pins
are VALID: test_provider_wait_isolation.py, T3 trio
(test_ledger_false_green_attack.py + test_ledger_edge_conservation_regression.py
+ test_execution_truth.mjs) all exist.

S-T11-3 (LOW) LINE-PINNED DLQ EVIDENCE DRIFTED.
- DLQ-01 note: "introducer_map + writer-independence at update() lines 697-747".
  Today: def update( at agent_handoff_ledger.py:715, introducer_map at 734-804.
  Content PRESENT, pins off by ~40-60 lines.
- DLQ-03 evidence: "motor split at courier_continue.py lines 537-544".
  Today: 537-544 shows hung-task abandon/future.done; the "meaningful change"
  split sits at ~554+. Content PRESENT, pins off by ~10-20 lines.
Cited DLQ-01/DLQ-02 test files all exist (attestation_trust_root,
self_cert_rejection, freshness_binding_epoch, freshness_rejection).
Fix direction: re-pin line numbers at current HEAD. Owner: packet stewards.

S-T11-4 (LOW) WINDOWS_CONTINUOUS_WORK CHECKPOINT BODY CONTRADICTS ITS FOOTER.
Body (lines 35-55): iteration 0, current_lane UNSTARTED, next_action
VERIFY_CURRENT_REALITY. Footer comments (lines 291-293): COMPLETED W01..W08,
PENDING W09. Antigravity updated only the footer. Any reader trusting the
body misroutes to W01. Owner: Windows-lane steward (Google/Antigravity —
flagged, NOT touched: foreign scope).

S-T11-5 (INFO) RC CHECKPOINT "UNKNOWN" NOW HAS STATIC EVIDENCE AVAILABLE.
RELEASE_CANDIDATE.md says MOTOR_OS_START_PATH=UNKNOWN_FROM_CURRENT_EVIDENCE.
T8 has since mapped the installer paths (ScheduledTasks AtLogon + HKCU Run +
WMI start) statically. Process-liveness proof still needs shell. No RC edit
made here (release-doc scope); note for the proof runner: start from the T8 map.

## Disposition
Read-only mission: NO DOC EDITS (several affected docs are foreign-owned:
Google/Antigravity + release scope). Findings handed to stewards.
No files outside runtime/slots/MUSE-45 touched.
