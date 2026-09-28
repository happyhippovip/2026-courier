# GLEDGER-106 Result — Execution Lifecycle

TASK_ID=GLEDGER-106
STATUS=NEEDS_VERIFICATION (transition rules PROVEN by reused evidence; exact daemon state-enum member names not re-verified — runtime_state.py is outside this queue's allowed inputs, so names are deliberately not asserted)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=GLEDGER-105 (claim acceptance starts execution; STOP fencing); P5 recovery map (9 daemon tests, all behavior-specified); PHYS-003 (no re-execution after restart); GLEDGER-102 (RESULT_STATES {SUCCESS, FAILED})

## Lifecycle (normative transitions, names abstracted)
claimed → running → terminal(succeeded | failed). Execution begins ONLY at claim acceptance (GLEDGER-105); a claimed-but-not-started unit executes exactly once (no double-start across restart — STOP-fenced durable run record).
Terminal states: succeeded (result produced + submitted), failed (terminal worker failure; result may still be submitted as FAILED for verification — FAILED execution invalidates the run, never converts to PASS).
Nonterminal (retryable WITHOUT new attempt): transport failure and 5xx on submit — retry with byte-identical payload under the same (attempt, dispatch) generation (duplicate-ACK eligible, GLEDGER-104). Stored-result resend after restart reuses the stored payload without recompute.

## Invalid transitions (rejected, never silently accepted)
- claimed → terminal without passing through running (no phantom completion).
- Any transition after terminal (no post-terminal mutation; late submits carry superseded generations → rejected per GLEDGER-104).
- running → claimed (no un-start); terminal → running (no resurrection; retry requires server resume → new attempt).
- 4xx submit rejection → must NOT retry (kept as evidence); exception during execution → must NOT retry blindly (observed recovery-test rules).
- Stopped/fenced execution → any binding transition (STOP fencing wins over in-flight work).

## State-machine ownership
Worker owns execution transitions; server owns task status; the two meet ONLY at result-submit (binding checked) and resume (new attempt). Execution state is durable (atomic run record) so restart resumes observation without re-execution.

MISSING=Exact daemon state-enum member names + STOP-prime conditions verbatim (requires runtime_state.py read — explicitly out of GLEDGER-10x allowed inputs; recommend GLEDGER-127 acceptance tests or writer packet cite it if normative names are needed).
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-107 (terminal succeeded/failed feeds result identity); GLEDGER-127 (acceptance tests pin the transitions above).
DO_NOT_REPEAT_FINGERPRINT=gledger-106-execution-lifecycle-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-7cb202eeb924e35b

DO_NOT_REPEAT_FINGERPRINT=sha256-4faed4859f07a76f

DO_NOT_REPEAT_FINGERPRINT=sha256-7ac20716938c3f34
