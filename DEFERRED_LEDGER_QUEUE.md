# Deferred Ledger & Guard Backlog

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
