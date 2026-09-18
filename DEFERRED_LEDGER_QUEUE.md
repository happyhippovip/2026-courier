# Deferred Ledger & Guard Backlog

## P0: False-Green / Corruption

ID=LEDGER-01
TITLE=Non-Atomic State Persistence Risks Total Corruption
BUG/EDGE=The server's `save_state()` function overwrites `central_state.json` directly using `with open(STATE_FILE, "w")`. If the server process is killed or power is lost exactly during the write, the file becomes truncated (0 bytes) or corrupted, destroying the entire canonical queue.
WHY_IT_MATTERS=A corrupted central ledger violates the fundamental durability requirement. Temporary OS issues could destroy all historical execution identity.
FILES=`server/app.py` (`save_state` and `custom_save_state`)
REPRODUCTION=Inject a `sys.exit(1)` inside the `json.dump` execution in `save_state`. Reboot server and attempt to load state.
EXPECTED_INVARIANT=Writes to the ledger are strictly atomic. The state is either entirely the old state or entirely the new state.
TARGETED_TEST=Create a test that interrupts the Python process mid-write and verifies state integrity.
DEPENDENCIES=None
OWNERSHIP=Ledger (Server)
ESTIMATED_SCOPE=Small (Implement temporary file write + `os.replace`).
BLOCKED_BY=None

## P1: Replay / Identity / Duplicate

ID=LEDGER-02
TITLE=Unauthenticated Human Approval Gate (P8)
BUG/EDGE=The `/tasks/<task_id>/approve_merge` endpoint accepts an `approver` string field but does not cryptographically verify that the caller possesses an administrator or specific human-verifier key.
WHY_IT_MATTERS=A compromised standard worker or malicious network actor could bypass the human gate, pushing protected code.
FILES=`server/app.py`
REPRODUCTION=Send a POST to `/tasks/X/approve_merge` using a standard worker `COURIER_API_KEY`.
EXPECTED_INVARIANT=Human approvals require a specialized `VERIFIER` or `ADMIN` role embedded in the authentication token.
TARGETED_TEST=Test authorization boundaries for the `approve_merge` route, ensuring standard workers get `403 Forbidden`.
DEPENDENCIES=None
OWNERSHIP=Guard (Verifier)
ESTIMATED_SCOPE=Medium
BLOCKED_BY=None

## P2: Restart / Concurrency / Provider Wait

ID=LEDGER-03
TITLE=Uncoordinated Provider Quota Backoff
BUG/EDGE=Workers handle `WAITING_PROVIDER` isolation individually per task (via `next_retry_at`). If an API is globally exhausted (e.g., OpenAI 429), the server does not enforce a global lock for that provider. 50 tasks might independently retry at independent times, worsening the provider rate limit.
WHY_IT_MATTERS=Violates polite API usage and causes extreme latency in queue recovery across the entire cluster.
FILES=`server/app.py`
REPRODUCTION=Dispatch 10 tasks requiring the same provider. Mock a 429. Watch 10 tasks retry at independent times instead of adhering to a global provider sleep.
EXPECTED_INVARIANT=A provider 429 delays ALL tasks requiring that specific provider globally.
TARGETED_TEST=Dispatch multiple tasks hitting the same mock provider, return 429, and assert subsequent claims yield `WORKER_BUSY` or `WAITING_PROVIDER` without re-dispatching instantly.
DEPENDENCIES=None
OWNERSHIP=Ledger / Motor
ESTIMATED_SCOPE=Medium (Add `provider_locks` tracking to central state).
BLOCKED_BY=None
