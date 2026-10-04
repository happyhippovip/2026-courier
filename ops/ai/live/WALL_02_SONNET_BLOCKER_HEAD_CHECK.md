# WALL 02 — Sonnet-Blocker vs. Current-HEAD Check (READ_ONLY)

WALL_ID=02 (first-free; no WALL checkpoints existed)
ROLE=UNASSIGNED (no ROLE_FROM_ASSIGNMENT arrived; executed only the universally
authorized read-only verification below)
DATE=2026-09-28
HEAD=e57517833c57eb3dd336c92e629e4a2db53da498 (branch fix-cb1-new, via .git/HEAD + loose ref)

## Sonnet input (accepted, not re-reviewed)
REVIEW_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
SONNET_VERDICT=BLOCKED
CLAIMED_DEFECT=scripts/courier_verifier.py::verify_artifacts(): dict-shaped task
artifact definitions trigger unhashable-dict exception instead of clean FAIL.
OWNER_OF_FIX=SOLE_WINDOWS_WRITER (no source edits from this window)

## Phase-change record
OLD_REVIEW_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
NEW_SHA=e57517833c57eb3dd336c92e629e4a2db53da498 (current checkout)
GATE_CANDIDATE_SHA=3c2aa5160002bdb7e2647ab87a0cef2a6f2a3ec4 (GATE_STATE_CURRENT.md:7)
MATERIAL_DELTA=UNKNOWN (no git/shell; packed-refs contains neither 34b0a42 nor 3c2aa51)
EVIDENCE_INVALIDATED=NONE_BY_THIS_WINDOW (no replacement gate review performed)
EVIDENCE_REUSABLE=All candidate-independent source reads below
VERDICT_TRANSFER=NONE (BLOCKED on 34b0a42 is NOT asserted for e5751783; only the
defect PATTERN was re-checked on current source)

## Current-source verification (HEAD e5751783, read-only)
SITE=scripts/courier_verifier.py:114-117
MECHANISM_CONFIRMED=YES:
- :114 builds `result_paths` as a SET of result-side paths.
- :117 tests `expected_art.get("path") not in result_paths` → hashes the TASK-side
  path. A dict/list-shaped task path raises `TypeError: unhashable type` instead
  of returning FAIL. (:79 uses == and is safe; :115-116 guard only dict-ness of
  the ARTIFACT, not hashability of its "path".)
INTAKE_GAP_CONFIRMED=YES: POST /goals stores workflow_plan steps opaquely
(server/app.py:110-118, no artifact-schema validation); planner-built steps carry
no artifacts key (:140-147). Malformed task artifact definitions are reachable.
BLAST_RADIUS (static): run_loop catches per-task exceptions (verifier :133ff/:168-169),
so the crash becomes a skipped verification, never a FAIL post → task wedges in
RESULT_RECEIVED (no reaper path for that state observed). No clean FAIL, no alert.
ADJACENT_NOTE (not a finding): string-form task artifact definitions are silently
skipped by the verifier (:79,:116 isinstance-dict guards) while the mac daemon
explicitly supports them (daemon.py:234) → daemon/verifier vocabulary drift.
MIN_FIX_DIRECTION (for owner, not this window): validate/hash-guard task-side paths
before set membership (fail closed); optionally schema-validate artifacts at intake.
MIN_TEST (for owner): task with artifact {"path": {"nested": 1}, "expected_sha256": "x"}
→ expect FAIL, no exception.

## Pool / queue state (bounded check)
POOL_SCRIPT=scripts/local_swarm_claim.py MISSING (read attempt: not found)
SHELL=DOWN (sandbox setup failure; claim/complete/block commands not executable)
WALL_CHECKPOINTS_EXISTING=NONE (ops/ai/live glob for WALL_ID|CLAIM_TOKEN: 0 hits)
POOL_STATUS=UNAVAILABLE (script missing AND shell down; NOT the same as NO_TASK)

## Ownership / waiting
WAITING_FOR=SOLE_WINDOWS_WRITER (blocker fix + new candidate SHA)
NO_MAC_ACTION=YES (no physical evidence requested or touched)

## Resume
EXACT_RESUME_TRIGGER=New candidate SHA from Central Writer (re-run this check on the
new HEAD), or ROLE_FROM_ASSIGNMENT + working pool (script restored + shell up).
