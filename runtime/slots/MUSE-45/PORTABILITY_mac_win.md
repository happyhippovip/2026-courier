# PORTABILITY REPORT — mac_worker vs windows_worker daemon drift (static)

Scope: scripts/mac_worker/daemon.py vs scripts/windows_worker/daemon.py.
Both are worker implementations; neither edited (read-only mission).

## P-1 (MEDIUM) Divergent duplicate-result semantics
- Windows http_post_result: retries 5x (backoff), treats ACK_DUPLICATE
  (200/409 + body token) as SUCCESS, CONTRADICTORY_DUPLICATE (409) as fatal.
- Mac result loop: single http_post per 5s tick; ANY 409/404/400 substring in
  the error => "Permanent rejection", clears current_result.json +
  current_task.json and drops the result.
- Risk: the same server verdict (e.g. 409 ACK_DUPLICATE) is SUCCESS on
  Windows but SILENT-DROP on Mac. Mixed-platform acceptance runs (>=2 real
  workers per RC) would have asymmetric delivery guarantees. Owner to unify
  (suggest: both daemons parse the server's duplicate tokens, not bare codes).

## P-2 (MEDIUM) Secret-hygiene asymmetry + keychain bypass
- Mac load_config lines 53-58: keychain lookup for the API key is BYPASSED
  (`pass # Bypass keychain to fix 401`); key comes from config.json (secret
  on disk) or env. Only the SERVER URL still comes from keychain.
- Windows: keyring/env ONLY, config.json keys refused by design.
- Tests: test_daemon_secret_hygiene.py covers MAC ONLY (log redaction +
  fail-closed). Windows has no redaction pass (single static "(redacted)"
  print) and no hygiene test — safe today by construction (key never
  printed), but unpinned.
- Owner actions: re-enable keychain-or-equivalent on Mac (remove disk-secret
  path), add Windows hygiene test mirroring the Mac one.

## P-3 (LOW-MEDIUM) Default worker_id collision on Windows
- Mac: auto-generates unique MAC-<host>-<rand6> when unconfigured.
- Windows: static default "default-win-worker".
- Server /workers/register (app.py:609+) does NOT reject duplicate IDs: it
  merges into the existing worker record, and a mismatched current_task on
  re-register flips the server-side task to
  HUMAN_REQUIRED/WORKER_RESTARTED_AND_LOST_STATE.
- Two unconfigured Windows workers would alias: heartbeat/last_seen collide,
  claims flap, spurious HUMAN_REQUIRED possible. Owner fix: unique default
  (hostname+rand like Mac) or server-side duplicate detection.

## P-4 (LOW) Crash-recovery implementation gap
- Windows: atomic marker writes (tmp+fsync+replace) for effect/result markers.
- Mac: direct open('w') writes for current_task/result/provider_wait state —
  crash-torn JSON possible; resume path json.loads without a corruption guard
  (a torn file would crash the daemon loop iteration — check). Owner: adopt
  atomic writes on Mac too.

## P-5 (LOW) Log management asymmetry
- Mac: 5MB rotation + secret redaction in write_log.
- Windows: no rotation (run_loop.bat appends unbounded), no redaction pass.

## Corroborated parity (no action)
- Both send runtime_sha at register; server enforces SHA match (426 on drift).
- Both fail closed on missing key/server (FATAL + exit 1).
- Both persist pending results across restarts (different mechanisms, P-4).
- Bootstrap handshake strings intact on Windows (T8/F-T8-5).

No edits made. All items are owner-triage suggestions with file:line evidence.
