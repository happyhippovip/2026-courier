# PACKET SPOT-VERIFICATION — DLQ-07 / DLQ-08 vs current code (read-only)

## DLQ-07 (init acceptance gate): CLOSED — fix PRESENT in current code
File: scripts/agent_handoff_ledger.py (GOOGLE-owned; read-only, no edits).
- initialize() lines 678-679: raises InitializationError when guard starts
  as CANONICAL_ACCEPTED. Line 680-681: same for preset CLEAN_IDLE=YES.
  Line 683: forces transition_state=PROVISIONAL.
- Matches W07 completion (init-with-preset rejected, normal init unchanged,
  preset CLEAN_IDLE cannot bypass Guard).
- Verdict: CLOSED status corroborated statically. (Executable re-proof needs
  shell; tests/test_ledger_self_cert_rejection.py exists for that.)

## DLQ-08 (hung-task bounded drain): CLOSED with one RESIDUAL note
File: scripts/courier_continue.py (GOOGLE-owned; read-only, no edits).
- Present: 8s hang detector (line 528-539) abandons hung futures, records
  TIMEOUT_HUNG_TASK durably via update_ledger, loop continues. Single-hung-
  task wedge: FIXED as claimed.
- Residual (new observation, LOW-MEDIUM, owner to triage):
  abandoned futures are untracked (del running_tasks) but NEVER cancelled:
  no future.cancel()/shutdown() anywhere in the file; pool is
  ThreadPoolExecutor(max_workers=5) (line 418). Five cumulative never-
  returning tasks would permanently exhaust the pool (submits queue forever),
  and a late-finishing abandoned thread could still produce effects after
  TIMEOUT was recorded.
  Mitigating (OBSERVED): current execute_task branches (lines 198-316) are
  all fast/local (file writes, git with timeout=10, immediate fail-closed
  returns) — no unbounded wait exists on any visible path today. So this is
  a latent robustness gap, NOT an active wedge. Suggested owner hardening
  (not applied): cancel abandoned futures + guard execute_task with an
  internal deadline when network/agent delegation paths are added.

## Method note
Static read-only verification (shell down). No code, test, or shared-doc
edits. SHAs 8918bc8f/bbc86b56 cited in checkpoint could not be git-verified
(no git access); code-state verdicts above are HEAD-agnostic ("present now").
