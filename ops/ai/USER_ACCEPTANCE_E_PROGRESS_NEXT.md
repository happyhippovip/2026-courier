# User Acceptance E — Progress / Next Action: "Was passiert als Nächstes?"

Status: OPERATOR ACCEPTANCE (USER WINDOW) — 2026-09-28
Product Shell: NOT unlocked. Prep-only, no implementation.

## USER_PROBLEM
A normal user asking "was passiert als Nächstes?" finds three different answers:
"await Mac canary" (gate), "blocked until Codex ack + main push" (critical path),
and a playbook pointing at files that do not exist — plus binding docs claiming
YES for things that are false.

## CURRENT_RUNTIME_TRUTH (verified by reads, shell down, no execution)
- AGREEING: `NEXT_ACTION: AWAIT_MAC_CANARY / PHYSICAL_PROOF_RUNNER`
  (`ops/ai/GATE_STATE_CURRENT.md:20`) matches TRUE_IDLE/awaiting-canary
  (`ops/ai/WALL_QUEUE_CURRENT.md:15-16`).
- TENSION: `ops/ai/CRITICAL_PATH_SYNTHESIS.md:17-18` says CORE_FREEZE_PREP is
  BLOCKED until "CODEX HIGH strictly acknowledges FINAL_SHA" AND "FINAL_SHA exact
  authoritative push to main must occur for Codex to accept" — i.e. review+push
  come BEFORE any canary/RUN, but no ordered list with owners exists, and
  `AUTHORITATIVE_READY=YES` (GATE:21) reads as if nothing blocks.
- DEAD REFS: playbook Phase 0 requires `ops/ai/WALL_BUILD_QUEUE_V1.md` and
  `ops/ai/WALL_SYSTEM.md`
  (`ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md:56-59`) — NEITHER
  exists (absent from full `ops/ai/*.md` enumeration; direct read of WALL_SYSTEM
  fails). The Google pre-Codex gate repeats the dead queue ref
  (`ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md:6`). An operator following the
  playbook hits missing files on step one.
- FALSE YES: `ops/ai/MAC_EXACT_BINDING_INPUTS.md` marks server (`:4-9`), worker
  (`:41-46`) and verifier (`:48-53`) CURRENTLY_BINDABLE=YES — all three are false
  per code (ignored `--db`, no-op worker module, ignored `--target`, see item C).

## ACCEPTANCE_REQUIREMENT
E-1: ONE ordered NEXT list: each item has owner, precondition, done-evidence, and
  explicit successor. "Ready" and "blocked" MUST NOT both be true without naming
  the ordering (e.g. review+push BEFORE canary).
E-2: Every file referenced by an operator procedure MUST exist at the referenced
  path; dead refs are P0 doc defects, not follow-ups.
E-3: Binding/readiness claims MUST be re-verifiable by a stated check (command +
  expected output), not asserted YES.

## MISSING_SYSTEM_SUPPORT
- Derived-readiness rule (see D-2) applied to the NEXT list.
- Dead-ref sweep across playbook + gates + command sheets.
- Binding re-verification after writer repair (item C).

## PREPARABLE_NOW (no code, this pass)
- NEXT-list schema + this dead-ref/false-YES inventory as acceptance input.

## BLOCKED_UNTIL
- Writer fixes refs/scripts; review lane confirms Codex-before-canary order.

## NEXT
F — Onboarding/Permissions (item F file).
