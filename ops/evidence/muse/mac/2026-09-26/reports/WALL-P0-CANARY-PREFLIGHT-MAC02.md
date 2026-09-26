# WALL-P0-CANARY-PREFLIGHT — consolidated pre-flight checklist (PREP ONLY, no canary executed)

WORKER=MAC-02 (MUSE) · HOST=MAC · MODE=READ_ONLY · 2026-09-26
TASK_FILE=queue/claimed/MAC-02/WALL-P0-CANARY-PREFLIGHT.md
CONSOLIDATED_FROM (read-only, no new probing):
- burn30/reports/GOOGLE_MAC_CANARY_PREFLIGHT.md (runtime/isolation inventory)
- burn30/reports/GM1_CANARY_MASTER.md (master prep + env + restart design)
- burn30/reports/MMAC2_CANARY_READY.md (GO-gate + prohibitions)
- burn30/reports/MUSE_MMAC2_CANARY_READY.md (isolation spec + 7 readiness checks)
- burn30/reports/MAC_REAL_MUSE_BINDING.md (effort values, exit codes, timeout)

## 1. Command template (Muse-bound worker)
`muse exec --provider meta --json --workspace <ABS_WORKTREE> --reasoning-effort medium --approval-mode on-request --session-id <UUID> --prompt-file <TASK_FILE>`
(BINDING source. Note: GM1 records CLI version 1.4.0-R4161.1 at
/Users/user/.local/bin/muse — re-verify version at GO; flags may drift.)

## 2. Effort values (binding: PARTIAL match)
Valid: none|minimal|low|medium|high|xhigh|max|ultra (default high).
`auto` is REJECTED by the real CLI but hardcoded in scripts/muse_wall_supervisor.py
(GM1 §2, preflight BLOCKERS). Checklist rule: pre-flight MUST grep the
supervisor/adapter for `--reasoning-effort auto` and refuse GO until cleared.
Use `medium` unless the task handoff names another value in writing.

## 3. Exit-code parsing rule
EXIT_CODE_BEHAVIOR=0 on terminal-completed EVEN WITH inner task failure
(BINDING source). Rule: exit code alone is NEVER the verdict. Verdict comes
only from parsed `--json` output + artifact sha256 recompute + state Rick.
BLOCKER_FOR_CANARY #2 until a parser for inner-failure nuance is in the run
workspace (shim/ allowed per MMAC2, logged as run-scoped, never committed).

## 4. External timeout wrapper (REQUIRED)
TIMEOUT_BEHAVIOR=UNKNOWN — no timeout flag in CLI help (BINDING source).
Canary MUST wrap every `muse exec` in an external timeout (e.g. `timeout`/`gtimeout`
or a supervisor deadline) and treat expiry as task-failed + evidence (log the
kill, keep workspace for forensics). BLOCKER_FOR_CANARY #3.

## 5. Isolation + GO-gate (unchanged, restated for the runner)
- Workspace/state/artifacts/evidence ALL under a fresh per-run dir
  (/tmp/mmac2_canary_<runid>/, mode 0700); COURIER_STATE_FILE asserted inside
  it; port ephemeral or env-provided, NEVER 8080 while live server may exist
  (PID 69407 on 8080 per MAC-CORE-WORKER-001 baseline — re-check at GO).
- Fresh runtime ids per run (MMAC2-A / MMAC2-B / MMAC2-VER pattern); verifier
  key distinct from worker key; throwaway per-run API keys via env only.
- GATE=CLOSED until exact 40-hex candidate SHA arrives in writing (branch
  names / "latest" / partial SHAs do not open it); verify via `git cat-file -t`.
- 7 readiness checks (MMAC2 §readiness validation): fresh workspace, state
  prefix, port free + !=8080 + /health, ids unused, single server instance,
  ledger writable, keys distinct. Any red → ABORT, keep workspace, report gate.
- Evidence: append-only JSONL (every request/response + state sha256 per
  mutation) + pre/post snapshots; satisfy MUSE_A2B_EVIDENCE_CARD E-fields,
  restart variant MUSE_MAC3_RESTART_PROOF E1–E9 with zero F-violations.
- Verify = exact expected_sha256 on deterministic fixtures ONLY — never claim
  semantic verification (GM1/GM5 clarification).

## 6. Pre-existing known blockers carried into the checklist
- effort `auto` in supervisor (see §2). - exit-code-only parsing (see §3).
- unmapped CLI timeout (see §4). - verifier-400-before-verdict on writer tip
  (server/app.py:476-480 per WALL_STATUS FIRST_CORE_BLOCKER; owned by
  WALL-P0-VERIFY-400 / MUSE-MAC-1de2 — not re-verified here, no duplicate work).

STATUS=CHECKLIST_COMPLETE · no canary started · no source touched · no model work
NEXT_TASK_PER_QUEUE=claim next pending per priority (P1 restart matrix, then P2s)
