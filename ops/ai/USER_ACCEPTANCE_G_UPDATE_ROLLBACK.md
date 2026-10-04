# User Acceptance G — Update / Rollback / Last Known Good

Status: OPERATOR ACCEPTANCE (USER WINDOW) — 2026-09-28
Product Shell: NOT unlocked. Prep-only, no implementation (packaging is playbook Phase 9,
explicitly post-pilot).

## USER_PROBLEM
A normal user cannot update safely or roll back: there is no Last Known Good,
no snapshot/restore procedure, no single-instance guard, and no update channel.
Any failed update today means hand-editing state.

## CURRENT_RUNTIME_TRUTH (verified by reads, shell down, no execution)
- 0 hits for rollback/LAST_KNOWN_GOOD/last_known_good in `server/`+`scripts/` —
  no rollback mechanism exists in code.
- `ops/ai/CRITICAL_PATH_SYNTHESIS.md:26-27` ("FINAL_SHA as Last-Known-Good baseline",
  "`state/` directory snapshotting will serve as the rollback package") is
  future tense — plan only, no procedure, no tooling.
- No single-instance guard observed: nothing prevents two servers (different
  checkouts/ports) from diverging the same state file; the in-process RLock
  cannot help across processes. RUN scripts check only port 8080.
- Playbook Phase 9 (`ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md:315-331`)
  correctly defers reproducible build, identity, signed update, rollback, LKG,
  state compatibility, no-lost-in-flight-work until after Core + pilot proof.

## ACCEPTANCE_REQUIREMENT
G-1: LKG MUST be defined as a triple: (FINAL_SHA, state snapshot, artifact-dir
  snapshot), captured atomically with a compatibility marker.
G-2: Snapshot/restore MUST be a documented procedure with pre/post checks
  (state loads, task vocabulary matches, no in-flight task lost or duplicated —
  drain rule before update).
G-3: Updates MUST be explicit (no silent auto-update before the pilot proves the
  mechanism); later: signed/safe update per playbook Phase 9.
G-4: Single-instance MUST be enforced for any state file (one writer per state).

## MISSING_SYSTEM_SUPPORT
- Everything runtime (by design, post-pilot): snapshot tool, LKG record, update
  channel, instance guard.

## PREPARABLE_NOW (no code, this pass)
- LKG definition + snapshot/restore acceptance (this file). No implementation.

## BLOCKED_UNTIL
- Post-pilot per playbook Phase 9. Do NOT implement now.

## NEXT
H — Support/Diagnose/Privacy (item H file).
