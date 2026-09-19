# CANNON_LOCAL_ACCEPTANCE_PACKET (Master 2/4)

No reruns for this master (reuse rule). Evidence: turbo 4/4 exit 0, probe 33/33 exit 0, ws 38/38 exit 0 (all at HEAD 970eae52). MODEL_CALLS=0.

IMPORT_10/IMPORT_100/IMPORT_10K=NOT_PROVEN (no importer exists; 12-record fixture is SPEC only).
PREFETCH_MAX_OBSERVED=NOT_IMPLEMENTED (no prefetch component; bounds are slots/maxBytes).
MODE1=PROVEN fake (NORMAL1 slots + driver-poll probe chain to goal DONE).
MODE2_LOCAL=PROVEN fake (barrier overlap + 2 slots + dup-verify single release).
MODE3_LOCAL=MISSING (no 3-lane governor; no live approval).
RESULT_BINDING=PROVEN fake (full chain incl. binding, 33/33). DUPLICATE_RESULT=PROVEN (DLQ-03 + redelivery ACK). LATE_RESULT=PROVEN (DLQ-03 stale/attempt).
RESTART=PARTIAL (controller OFF + PENDING persist proven; server retry/file-state foreign).
429=PARTIAL (server provider-wait exists foreign; no explicit 429 fake-test here). 503=PROVEN fake (3 transport tests + adapter TIMEOUT). CIRCUIT=PROVEN fake (persistent PENDING, no auto-retry, reconciliation-gated probe).
RESOURCE_GREEN/YELLOW/RED=MISSING (no governor; bounds only).
HUMAN_GATE=PARTIAL (grant matrix proven; A/B/C-branch topology not run here).
UPDATE_PRESERVATION=NOT_DONE (checkout behind; sync run blocked).
SECURITY_INPUT_CONTROL=PARTIAL (argv-no-shell proven; artifact shape proven; unsafe-path/tamper via server contract referenced; prompt-privilege draft-only per fixture SPEC).
NIGHT_SIMULATION=MISSING (no runner/dispatcher; 20-task night not run). MORNING_REPORT=MISSING (no component).

TESTS=turbo 4/4, probe 33/33, ws-suite 38/38, DLQ-03 committed, portable-lock/smoke historical. EXITCODES=0,0,0.
FAILURES=none red in own scope; PENDING-wedge + runner-dir-quirk documented as behavior/tooling, fixed helpers (donePromise, stub-drain).
GOOGLE_FIXES_REQUIRED=G1 turbo isolation+asserts+mismatch; G2 sync source+honest exit; G3 Windows smoke run; G4 live verify evidence.
FIRST_BLOCKER=live + machine evidence for verify contract incl. Windows smoke. OWNER=GOOGLE.
