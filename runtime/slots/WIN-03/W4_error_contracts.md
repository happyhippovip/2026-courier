# W4 RESULT — Error-contract audit (static, read-only)

MODE: shell-less LIGHT. Scope: exception taxonomy (18 classes) vs raise sites
vs catch sites vs test pins vs server mapping (server/app.py P3: read-only
observed, never edited). No execution.

## Taxonomy (OBSERVED)
- agent_handoff_ledger.py:116-160: LedgerError(RuntimeError) + 11 subclasses:
  RevisionConflict, NoMeaningfulChange, Validation, Binding, Freshness,
  Monotonicity, SelfCertification, EdgeConservation, CleanIdle,
  Initialization, Storage.
- TWO ContractErrors, same name, unrelated: attestation_contract.py:16 and
  integration_contract.py:35 (both ValueError).
- Singles: operating_ledger.NotAuthoritativeError, revenue_worker_adapter.
  ResultPostError, run_autonomous_loop.WorkflowLockedError,
  slot_state.StateCorruptionError.

## Findings
E-W4-1 (MEDIUM) MOTOR MATCHES LEDGER ERRORS BY MESSAGE STRING, TERMINAL WRITE
SILENTLY SWALLOWED. courier_continue.py:553-559 catches bare Exception from
update_ledger then branches on "meaningful change"/"revision conflict" in
str(e) — the typed NoMeaningfulChangeError/RevisionConflictError subclasses
are ignored, so a message rewording silently changes break-vs-retry control
flow. PLUS courier_continue.py:497-498 `except Exception: pass` on the
CLEAN_IDLE_ACHIEVED terminal ledger write: if the DONE-claim write fails,
nobody is told. Owner: motor scope.

E-W4-2 (LOW) ZERO PRECISE LEDGER CATCHERS ANYWHERE. No `except LedgerError`
(or subclass) in scripts/ nor server/. All ledger failures land in generic
handlers (motor string-match, queue_processor print-and-retry, daemon
FAILED-marking). Raise-side precision has no consumer; a wrong-subclass bug
is invisible in prod paths. Tests mirror this: subclass pins exist ONLY for
StateCorruptionError (wall tests); ledger tests pin base LedgerError + message.

E-W4-3 (LOW, latent) DUAL ContractError — NO LIVE CONFUSION OBSERVED. Server
imports+catches the integration one (app.py:5,823,873,925) and calls the
attestation raisers uncaught (principal/fingerprint/current_receipt at
1102/1108/1255-56) — but those escape only on corrupt-state/misconfig
inputs (fail-loud 500, defensible). No request-driven 4xx-vs-500 mishandling
in sampled lines; full route audit is follow-up work. Owner may still map
attestation.ContractError explicitly. P3 file untouched (read-only rule).

E-W4-4 (OK) TAXONOMY FULLY LIVE. All 12 ledger classes have raise sites
(sampled: Validation x12+ :183-250, CleanIdle :231-235, Binding :321-386+863-865,
Storage x8+ :521-614, Init :679-690, Monotonicity :861, Freshness :303, Edge
:763, SelfCert :869-873, Revision :747, NoMeaningful :877) and all 4 singles
raise. Zero dead exception classes.

E-W4-5 (INFO, dedupe) BARE-EXCEPT SURFACE = 39 files under scripts/ (inventory
for owners; not triaged per-site here). queue_processor bare-except poison
retry already canonical T10-G-3 (MUSE-45) — cited, not redone.

## Evidence (mission RESULTS format)
BRANCH=ledger-reconciliation-final (.git/HEAD, fresh read this turn)
SHA=UNKNOWN this session (no shell; last documented worktree HEAD 27b22d7e,
Google checkpoint 2026-09-26T07:45+02:00 — cited, not re-verified)
TASK=W4 error-contract audit
WRITE_SCOPE=NONE
FILES_CHANGED=0 repo files (own-slot artifacts only)
TEST_COMMAND=none (shell runner DOWN — sandbox setup fails pre-exec)
TESTS_PASSED=0 / TESTS_FAILED=0 (none run; static analysis only)
FAILED_TEST_NAMES=none
ARTIFACT=runtime/slots/WIN-03/W4_error_contracts.md
RESULT_STATE=ANALYSIS_COMPLETE

## Disposition
READ ONLY (no WRITE_SCOPE). E-W4-1..3 to motor/server owners. No files outside
runtime/slots/WIN-03 touched. No Mac scope touched. No peer slots touched.
