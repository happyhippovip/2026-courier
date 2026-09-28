# TURBO SHARD 06 — TIMEOUT→FAILED (read-only C2, post-codex packet prep)

SHARD=06 / OWNER=MUSE_C2_LAPIS_DUBHE / 2026-09-28T15:00Z / CODEX absent → packet only.
Reads: daemon.py:300-327+365-372, adapter timeout/conclusion greps, HNI-09 S2 reuse.
FILES=server/app.py(validate), scripts/mac_worker/daemon.py, scripts/github_worker_adapter.py
CAUSAL_RISK=(a) server has no TIMEOUT result status (400 by design); mapping burden
on adapters. (b) mac run_agy 300s timeout → broad-except FAILED (implicit, works)
BUT child not killed in this window (orphan risk; G06 kill+reap cited, unported).
(c) muse-ambiguous timeout raises, posts nothing → stale-quarantine path (consistent).
(d) github-lane execution-conclusion→status mapping unverified (grep empty).
MIN_FIX=(owner, NOT applied): explicit except TimeoutExpired → proc.kill+reap →
FAILED w/ reason TIMEOUT (mac); document gh conclusion→status table (github lane).
MIN_TEST=(post-Codex, FINAL_SHA-bound): TIMEOUT-status POST → 400; forced agy
timeout → FAILED result + quarantine path; gh timed_out → FAILED evidenceless.
EVIDENCE=daemon.py:305+326-327, :368-372; contract:147; adapter:123 (transport only).
OWNER=mac-worker owner (b), github-adapter owner (d); server mapping = intentional 400.
BEFORE_RUN1=no (adapter-lane robustness + retest spec; server contract intentional).
DO_NOT_REPEAT=sha256-muse-turbo-06-timeout-failed-20260928 (+ session prints).
STATUS=SHARD_COMPLETE (single shard; no second taken).
