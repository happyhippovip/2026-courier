# CODEX REVIEW PACKET — DLQ-05 cluster-wide provider quota backoff (COMPLETE)

CURRENT_HEAD=9837e5ae735f3075bffa9d3bdf6509002692e1ca
COMMITS_UNDER_REVIEW=
- 0c8d1edd feat(ledger): implement cluster-wide isolated provider quota backoff (DLQ-05)

INVARIANTS=
1. A 429/quota-exhaustion applies a cluster-wide lock to the quota resource
   key; no dispatch for that key until backoff expires.
2. Unrelated providers and workers keep processing READY tasks.
3. Same-dispatch auto-resume preserves attempt_id/dispatch_id/execution_ref
   after lock expiry (no new attempt).
4. Concurrent 429s extend the lock idempotently (max, never shorten).

DIFF_SCOPE=server/app.py (+20/-2): claim_task auto-resume gated on
provider_locks[lock_key] instead of per-task next_retry_at; new
PROVIDER_QUOTA_LOCKED gate before QUEUED scan; provider_wait writes
max(existing, new) backoff and mirrors it into task next_retry_at.
tests/test_provider_wait_isolation.py (+164, scenarios 1-7).

EXACT_FILES=server/app.py (claim_task ~:715-747, provider_wait ~:1312-1321)
EXACT_FUNCTIONS=claim_task(), provider_wait(), calculate_backoff()

REPRODUCERS=
- python3 -m pytest tests/test_provider_wait_isolation.py -q (scenarios:
  same pool+provider locked out; independent pool continues; restart
  persistence; expiry resume; concurrent-429 idempotence; forged provider
  string containment).
- /tmp/motor_hang_bound.py pattern N/A (separate DLQ-08 item, fixed in bbc86b56).

T0_RESULTS=py_compile server/app.py OK (Muse, HEAD 9837e5ae)
T1_RESULTS=tests/test_provider_wait_isolation.py 1 passed;
tests/test_provider_wait.py 3 passed (incl. Muse lock-aware resume update);
tests/test_global_queue_stall.py 1 passed (Muse W1-locked/W2-continues update);
tests/test_motor_eligibility_v1.py 23 passed (incl. Muse W2 true-negative and
verifier-auth header updates). All re-run single-file per TEST_MAP lane
discipline at HEAD 9837e5ae.
T2_RESULTS=Same files are the affected suite (server claim/provider surface).
Motor continue suite unaffected (no motor content in this batch).
T3_RESULTS=Ledger attack suites unaffected (no ledger content in this batch).

KNOWN_ATTACKS=
- Forged provider string (isolation scenario 7: contained — forger only locks
  worker-4:anthropic, cannot touch pool-A).
- Same-worker starvation (BY DESIGN: worker's own pool locked; independent
  workers continue — pinned by W2 assertions in stall + eligibility tests).
- Stale-test bypass: three pre-DLQ-05 tests encoded per-task semantics and
  failed post-fix; updated by Muse to the lock semantic WITHOUT weakening
  (resume still asserts same dispatch; stall/eligibility assert W1-locked AND
  W2-continues). Bisect-proven: global stall passed pre-0c8d1edd, failed
  after; protected-code failure separately bisected to 058be78c (verifier
  auth, header updated accordingly).
- Import-order fragility (pre-existing, NOT introduced here):
  test_provider_wait_isolation sets COURIER_API_KEY at module import, so it
  passes standalone but 401s in multi-file batches where another module
  imports server.app first. TEST_MAP mandates single-file runs; document,
  do not batch.

BYPASSES_ALREADY_TRIED=
- Zeroing task next_retry_at to force resume (now insufficient by design;
  lock expiry is the only resume path).
- Claiming unrelated READY work on the LOCKED worker (blocked by design;
  use an independent worker).
- worker_quota_pools seeding to widen a lock (server-owned map; only the
  isolation test seeds it — see open question 1).

FILES_TO_READ (bounded)=
- server/app.py:710-750, 1305-1325
- tests/test_provider_wait_isolation.py (whole file, ~165 lines)
- ops/ai/packets/DLQ-08_review_packet.md (adjacent motor-boundedness context)

QUESTIONS_TO_ANSWER=
1. worker_quota_pools is NEVER populated by production code (only .get with
   worker_id fallback; only tests seed it) — so the effective key is
   worker_id:provider, NOT pool:provider. Is per-worker granularity the
   DESIGN (each worker = own quota), or must deployment populate the map?
   Two workers sharing one real credential pool do NOT share a lock today.
2. Same-worker-different-task blocking confirmed intentional? (Muse treats as
   yes per queue negative_test wording; needs owner confirmation.)
3. W08 physical precheck still open: restart persistence + expiry resume +
   replay-no-shorten on a real server-owned pool configuration.
4. Pool-mapping authority: who writes worker_quota_pools in production, and
   can a worker influence its own mapping (self-assignment was the original
   DLQ-05 UNKNOWN)?

EXPECTED_FAILURE_MODE=If the lock is bypassed: uncoordinated per-task 429
storms (original DLQ-05). If over-applied: same-worker READY work stalls
until expiry (bounded, max 300s backoff) while independent workers continue.

CODEX_READY=YES (implementation reviewed line-level, tests re-run at HEAD,
stale tests updated without weakening, open points asked not assumed).
PHYSICAL_PENDING=W08 server-owned pool precheck on Windows.
