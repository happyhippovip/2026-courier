# Findings Pack (2026-09-18)

ID=FND-01
TITLE=Worker Crash Replay Prevention
STATUS=FIXED
SOURCE_FILES=scripts/windows_worker/daemon.py, scripts/windows_worker/run_loop.bat
FUNCTIONS=loop(), run_task()
OBSERVED_BEHAVIOR=If the worker process dies during shell execution, restarting it caused a blind replay of the side-effecting task.
EXPECTED_INVARIANT=Crash during execution yields AMBIGUOUS_CRASH; no duplicate external effects.
REPRODUCTION=Kill Python mid-task.
FAILURE_SIGNATURE=Orphaned effect_marker.json exists on boot.
FIX_COMMIT=d645c8a3
TESTS=tests/test_windows_runtime_torture.py
NEGATIVE_CASES=Graceful exit.
REPLAY_CASE=Blocked by AMBIGUOUS_CRASH state transition.
RESTART_CASE=run_loop.bat infinitely restarts the daemon.
OWNER=Google
DEPENDENCIES=OS File System (Markers)
RUNTIME_SHA_IF_RELEVANT=f71ff070
NEXT_SAFE_ACTION=N/A

ID=FND-02
TITLE=Stale/Rogue Worker Identity via SHA Mismatch
STATUS=FIXED
SOURCE_FILES=server/app.py, scripts/mac_worker/daemon.py, scripts/windows_worker/daemon.py
FUNCTIONS=register_worker(), loop()
OBSERVED_BEHAVIOR=Workers with outdated code could connect and pollute the canonical ledger.
EXPECTED_INVARIANT=Server and Worker must run the exact same commit SHA for physical validity.
REPRODUCTION=Connect with missing/old runtime_sha in payload.
FAILURE_SIGNATURE=HTTP 426 Upgrade Required.
FIX_COMMIT=f71ff070
TESTS=N/A (Manually verified in app.py logic)
OWNER=Google
DEPENDENCIES=git rev-parse HEAD

ID=FND-03
TITLE=Provider Quota Global Freeze
STATUS=FIXED
SOURCE_FILES=server/app.py
FUNCTIONS=result() -> WAITING_PROVIDER branch
OBSERVED_BEHAVIOR=A worker reporting WAITING_PROVIDER for Task A would remain bound to Task A, freezing its capacity for other unrelated tasks.
EXPECTED_INVARIANT=Worker is instantly freed for independent tasks while the rate-limited task sleeps in the central queue.
FAILURE_SIGNATURE=Worker log repeatedly polling the same blocked task.
FIX_COMMIT=N/A (Behavior verified natively correct in current app.py logic where `worker["current_task"] = None` is set).
