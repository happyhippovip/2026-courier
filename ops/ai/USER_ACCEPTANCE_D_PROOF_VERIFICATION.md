# User Acceptance D — Proof / Verifikation: "Was wurde wirklich verifiziert?"

Status: OPERATOR ACCEPTANCE (USER WINDOW) — 2026-09-28
Product Shell: NOT unlocked. Prep-only. NO revalidation in this pass (observation only).

## USER_PROBLEM
A normal user asking "was wurde wirklich verifiziert?" gets contradictory numbers,
evidence that lives outside the repo, and a proof checker that cannot pass against
the real server. Trustworthy proof is currently indistinguishable from stale claims.

## CURRENT_RUNTIME_TRUTH (verified by reads, shell down, no execution)
- Count conflict: "51 targeted assertions GREEN" (`ops/ai/PRE_CODEX_HANDOFF.md:30`,
  `ops/ai/PROOF_CARD.md:12`) vs "57 passed, 1 skipped, 0 failed"
  (`ops/ai/GATE_STATE_CURRENT.md:10`, `ops/ai/WALL_QUEUE_CURRENT.md:9`) vs
  "SKIPPED_COUNT 0 within the target boundary" (`ops/ai/PRE_CODEX_HANDOFF.md:33`).
  Units (assertions vs tests) and skip counts disagree across canonical files.
- Gate criteria vs READY claim: `ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md`
  requires 5-file scope (:15-20), SKIPPED_COUNT=0 (:23), clean `git diff --check`
  (:24), durable remote resolvability (:28) — but scope check says SCOPE_OK=NO
  with 6th file `tests/test_integration_contract.py` (`ops/ai/SCOPE_CHECK_EVIDENCE.md:19-25`),
  diff check FAILED/whitespace-only (HANDOFF:36-37, GATE:12), 1 test skipped
  (GATE:10), remote durability UNKNOWN (`ops/ai/PROOF_CARD.md:42`) —
  while `REPORTED_PRE_CODEX_READY=YES` / `AUTHORITATIVE_READY=YES` (GATE:6,21).
- Evidence outside repo: all 12 "PROVEN" refs point to
  `c:\Users\lol\courier_work\google_windows_ledger_queue\results\*.result.md`
  (HANDOFF:16-27); fingerprint report counts 369 such files
  (`ops/ai/EVIDENCE_FINGERPRINT_REPORT.md:7`). Not in repo, not portable to Mac.
- Evidence checker detached: `scripts/verify_run1_evidence.py:19-35` expects a
  sqlite `tasks` table with `task_id='A'` plus server log strings "Claimed task A" /
  "Result for task A" — but the server persists JSON (`server/app.py:11,66-72`),
  mints `task-<uuid>` ids (`server/app.py:118,142`), and emits NO log lines at all
  (no logging/prints in `server/app.py`). The checker can NEVER pass as written.
- False DONE: `ops/ai/CRITICAL_PATH_SYNTHESIS.md:7` lists "RUN_1 and RUN_2 Mac
  specific evidence verification and collection" as DONE although RUN_1/RUN_2 are
  pending (PROOF_CARD:13 `[PENDING]`, GATE:20 AWAIT_MAC_CANARY).
- Codex review status contradictory: `be2a394e-CODEX-REVIEW-GREEN` (OTHER sha)
  in `ops/ai/EVIDENCE_FINGERPRINT_REPORT.md:30` vs FINAL_SHA
  `[PENDING_CODEX_CONFIRMATION]` (`ops/ai/PROOF_CARD.md:8`) vs BLOCKED-until-CODEX-HIGH-ack
  (`ops/ai/CRITICAL_PATH_SYNTHESIS.md:17`). No Codex verdict for 3c2aa516 observed.
- Doc-code drift: `docs/p3/README.md:4-5,17` says the server "needs the patch" and
  "`git apply --check` is part of that test", but cutover code is LIVE
  (`server/app.py:6,75` imports + registers the artifact blueprint).

## ACCEPTANCE_REQUIREMENT
D-1: One proof record per claim: claim, method, exact command, SHA, counts in BOTH
  units (tests + assertions, skipped NAMED), evidence paths IN the repo or a named
  durable bundle, checker name + exit code against REAL artifacts.
D-2: Readiness flags MUST be derived from sub-conditions (scope ok? skips? diff?
  durability? review for THIS sha?) — never hand-set while sub-checks fail.
D-3: No DONE claim for unexecuted runs; preparation DONE ≠ verification DONE.
D-4: Review verdicts MUST name their exact SHA; a green for another SHA MUST NOT
  transfer silently.

## MISSING_SYSTEM_SUPPORT
- Durable in-repo (or bundled) evidence for the 369 external result files.
- Checker rewritten against JSON state + real routes/ids/log vocabulary.
- Scope disposition for the 6th file (writer decision) + count reconciliation.
- Codex verdict for 3c2aa516 (review lane, not this window).

## PREPARABLE_NOW (no code, this pass)
- Proof-record schema + this contradiction ledger as acceptance input.

## BLOCKED_UNTIL
- Writer/review lanes resolve scope, counts, checker, review. No revalidation here.

## NEXT
E — Progress/Next Action (item E file).
