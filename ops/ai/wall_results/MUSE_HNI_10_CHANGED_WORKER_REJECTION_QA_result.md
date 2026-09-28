# Result for MUSE-HNI-10 — CHANGED_WORKER_REJECTION_QA

TASK_ID=MUSE-HNI-10
AREA=CHANGED_WORKER_REJECTION_QA
STATUS=COMPLETE
RESULTS_REUSED=server/app.py:21-43+264-300 (this run) + result-binding sections (prior); cross-proc residual + liveness limit (known, cited only)
DELIVERABLE_OR_VERDICT=7/7 changed-worker subcases resolved against executable source (0 executions, 0 source edits, ledger untouched): wrong-worker result -> 400; unknown/busy claim -> 404/None; QUEUED-only claiming; verifier independence enforced at request + config level; post-resume late results -> 400. One documented BOUNDARY (no finding): shared-key auth binds result<->task, caller<->worker trust = key-holder set. 0 contradictions, 0 false-greens. COMPLETE candidate-independent.
MISSING=None in-lane.
BLOCKER=None for QA (gate untouched; dynamic RUNs PENDING by construction).
NEXT_EXACT_ACTION=Claim MUSE-HNI-11 (changed attempt/dispatch rejection).
DO_NOT_REPEAT_FINGERPRINT=sha256-muse-hni-10-changed-worker-rejection-20260928

Inputs read (minimum-necessary): MUSE_HNI_10 task line (family template); server/app.py:21-43 (auth), :236-300 (unregister/heartbeat/claim); remainder via prior reads.
Commands/tests run: none (read-only; MAX_HEAVY_JOBS respected).
Ledger writes: none. Source edits: 0.
