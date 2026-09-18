# Source Map

RESULT INGESTION
FILE=server/app.py
FUNCTION=result()
ROLE=Central canonical truth for task completion, handles idempotency and provider waits.

QUEUE CLAIM
FILE=server/app.py
FUNCTION=claim_task()
ROLE=Binds a READY task to exactly one healthy worker_id.

WORKER IDENTITY & RUNTIME SHA
FILE=server/app.py
FUNCTION=register_worker()
ROLE=Validates `worker_id` and `runtime_sha`, preventing rogue or stale code from executing tasks.

CHECKPOINT (WINDOWS)
FILE=scripts/windows_worker/daemon.py
FUNCTION=loop() / run_task()
ROLE=Maintains OS-level `effect_marker.json` and `result_marker.json` to prevent replay attacks during process assassination.

WINDOWS RUNTIME (PERSISTENCE)
FILE=scripts/windows_worker/run_loop.bat
ROLE=Infinite `while %ERRORLEVEL%` restart loop guaranteeing process durability.
