# User Acceptance H — Support / Diagnose / Privacy: "Was ist kaputt, und was darf ich teilen?"

Status: OPERATOR ACCEPTANCE (USER WINDOW) — 2026-09-28
Product Shell: NOT unlocked. Prep-only, no implementation.

## USER_PROBLEM
A normal user with a failure can neither diagnose ("was ist kaputt?") nor share
safely ("was davon ist privat?"): the server logs nothing, the evidence checker
greps for strings that never occur, and no diagnostic-bundle / redaction /
retention rule exists.

## CURRENT_RUNTIME_TRUTH (verified by reads, shell down, no execution)
- `server/app.py` contains NO logging/prints (only Werkzeug access lines reach
  stderr implicitly). Claim/result/verify/reconcile transitions leave no
  server-side log line with IDs — post-mortem diagnosis from logs is impossible.
- `scripts/verify_run1_evidence.py:30-35` greps server logs for "Claimed task A" /
  "Result for task A", which the server never emits (see item D) — diagnosis via
  the official checker always reports absence, even on a healthy run.
- GOOD PRECEDENT: `docs/CANONICAL_MUSE_CANARY.md:37` warns that `muse.stdout` /
  `muse.stderr` may contain private provider output and must not be published
  wholesale. No equivalent privacy classification exists for server/worker/
  verifier logs, artifacts, or state dumps.
- No diagnostic-bundle definition, no redaction rule, no retention rule found in
  `docs/*.md` or `ops/ai/*.md` listings.
- Safety-advice gap carried from item A: overheat resume gate has no satisfaction
  record, so support cannot tell a user "it is safe/allowed to run" either.

## ACCEPTANCE_REQUIREMENT
H-1: Per-component log minimum: claim/result/verify/reconcile/reclaim/resume MUST
  each emit one line with goal/task/attempt/dispatch ids + outcome. No silent
  state transitions.
H-2: A support-bundle definition MUST exist: which files (logs, state snapshot,
  evidence, bindings), redaction rules (keys, tokens, private provider output),
  retention/deletion note. Privacy classes: PUBLIC / SHAREABLE-WITH-SUPPORT /
  SENSITIVE-NEVER-SHARE.
H-3: Before any heavy RUN, the overheat-gate satisfaction record (item A) MUST be
  published; support MUST be able to cite it.

## MISSING_SYSTEM_SUPPORT
- Server/component logging (writer scope).
- Bundle spec + redaction rule + retention note (support/pilot-prep scope).
- Gate satisfaction record (Mac owner, human evidence).

## PREPARABLE_NOW (no code, this pass)
- Bundle spec sketch + log-line acceptance (this file).

## BLOCKED_UNTIL
- Writer (logging); Mac owner (gate record). No implementation here.

## NEXT
I — Pilot Feedback / Signal (item I file).
