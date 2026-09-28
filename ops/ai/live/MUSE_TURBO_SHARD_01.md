# Turbo Shard 01 — A1 adapter-confinement (post-Codex package, Codex absent)

SHARD=01
STATUS=SHARD_COMPLETE (package prepared; Codex verdict pending, no wave opened)
OWNER=MUSE_C2_SAFFRON_OCCULT / HOST=MAC / 2026-09-28
MODE=READ_ONLY_C2, 0 edits, 0 runs, 0 ledger. Master prompt ENOENT → inline
 table used. No second shard taken (per orders).
FILES=scripts/github_worker_adapter.py (~:98 escape),
 scripts/integration_contract.py:88 + :166-169 (guard template),
 tests/test_github_worker_adapter.py (no traversal test),
 server backstop reused (HNI-07 upload re-hash, HNI-12 server traversal
 reject — cited, not re-read).
SUBCASES (4, narrow):
 S1 Escape live: `evidence_file = directory / artifact.get("path","")`
 followed by `.read_bytes()` with no is_absolute/`..` check → absolute
 path escapes `directory` (pathlib `/` semantics), `..` traverses.
 S2 No pinning test: grep traversal/`..` in tests/test_github_worker_adapter.py
 == 0 hits → regression unguarded.
 S3 Template exists in-repo: contract:88 (`is_absolute() or ".." in parts`)
 and :166-169 (+ Windows drive/root variant) → 3-line port, no new design.
 S4 Containment (reuse): server re-hashes on upload and rejects traversal
 server-lane → adapter escape reads arbitrary local bytes into hash check
 but cannot inject unhashed bytes past server verify; severity bounded,
 hardening not gate-blocking.
CAUSAL_RISK=worker-influenced `path` makes the adapter read outside
 `directory` (info-disclosure into hash comparison / local file probe);
 no server-side injection (backstop holds).
MIN_FIX=port contract:88 guard (plus :169 Windows-drive variant) ahead of
 `directory / artifact.get("path","")`; raise ValueError on violation.
 1 file, ~4 lines. OWNER=WINDOWS_CENTRAL_WRITER (adapter lane).
MIN_TEST=2 cases in tests/test_github_worker_adapter.py: absolute-path
 artifact → ValueError; `../`-traversal artifact → ValueError.
EVIDENCE=post-fix adapter bytes + 2 new tests green + existing adapter suite
 green (no full suite).
OWNER=WINDOWS_CENTRAL_WRITER
BEFORE_RUN1|RUN2|FREEZE|PILOT=FREEZE (hardening before Core Freeze closeout;
 NOT required before RUN_1/RUN_2 — server backstop contains blast radius;
 NOT before Codex — adapter file outside gate fingerprint).
DO_NOT_REPEAT_FINGERPRINT=sha256-muse-turbo-01-a1-01
