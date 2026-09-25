# COURIER SYMPHONY MUSE — START HERE

This directory is the canonical shared engineering memory for ChatGPT, MUSE,
Google Antigravity, Codex, NEWSY/read-only scouts, and human operators.

CODE_BASE_HEAD: 0c8d1eddacb15dedbebb8406e475917dc2ab1c2b
UPDATED_AT: 2026-09-18T09:23:33+02:00

`CODE_BASE_HEAD` is the last runtime-affecting commit reviewed by this memory
update. Memory-only commits may follow it without invalidating the code binding.

## Startup

1. Read this file.
2. Fetch and verify local HEAD and `origin/release-candidate-integration`.
3. Read `OWNERSHIP_MAP.yaml` and `TEST_MAP.yaml`.
4. Read only the artifact and prepared packet relevant to the assigned task.
5. Inspect only the delta since the packet's `CURRENT_HEAD`.

Do not rediscover documented facts unless newer executable evidence contradicts
them. The historical `.agents/knowledge/*` pack is non-authoritative; it points
here.

## Canonical read order

`MASTER_OPERATING_SYSTEM.md` → `CLOUD_ALIGNMENT_2026-09-18.md` →
`OWNERSHIP_MAP.yaml` → task-specific source/test map → prepared packet.

## Permanent rules

PACKET FIRST. ONE WRITER. T0 → T1 → T2. T3 BEFORE CODEX. CODEX ONLY WHEN
INDEPENDENCE MATTERS. T4 ONLY AT BOUNDARIES. BLOCKED TASK != BLOCKED PROJECT.
LEDGER LAST. NO FAKE GREEN.

REAL EVENT → DURABLE STATE → EVIDENCE → INDEPENDENT VALIDATION →
SHA/RUNTIME/FRESHNESS CHECK → ACCEPTANCE GUARD → LEDGER.

## Review packet required for Codex

`CURRENT_HEAD`, `COMMITS_UNDER_REVIEW`, `INVARIANTS`, `REPRODUCERS`,
`T2_RESULTS`, `T3_RESULTS`, `KNOWN_ATTACKS`, `FILES_TO_READ`, and
`QUESTIONS_TO_ANSWER` are mandatory. Missing data means `PACKET_INCOMPLETE`.

## Session record 2026-09-25 (cloud chat)

Cloud sessions cannot reach the Mac or the Windows PC: they read/analyse the repo, prepare code and
handoffs; machine evidence comes from the operator or local agents and is labelled as such.

Branches pushed (main untouched, main = 3e2fe24):
- `staging/cannon-v1-extra-high-convergence` (dd3d2644): canonical Cannon V1 candidate =
  main + claude/courier-integration-ready (task02-10) + Motor cost fix + 7 standalone Muse fixes +
  `docs/p3/server-idempotency-cutover.patch` (keen-gates fixes; server/app.py stays P3 read-only).
  281 tests pass; simulated cutover with both P3 patches: 253 real-server tests pass.
- `supervisor/canonical-muse-runtime` (823172e9): Muse slot supervisor on the canonical worker path
  (one scripts/mac_worker/daemon.py per slot; register -> claim -> CLAIMED/STARTED/RESULT_READY ->
  result). Restart after exit, backoff, PAUSED_ERROR, locks, ramp 1-4-8-16-32 held without metrics.
  Muse prompt method must be declared (MUSE_CLI prompt_via arg|stdin), else MUSE_PROMPT_METHOD_UNCONFIRMED.
  290 tests pass (simulated; no Mac proof).
- `windows/antigravity-open-starter` (f26a0338): `Open-GoogleAntigravity.ps1` one-click starter,
  opens only a live HTTPS-200 port; static only, not run on Windows.
- `staging/cannon-v1-candidate`, `claude/determined-hypatia-uvybo5` (Motor cost fix: no 5-min cron,
  push/manual trigger + precheck), reference only: `supervisor/wall-slot-restart`,
  `staging/cannon-v1-muse-harvest`.

Decisions: canonical line = main + integration-ready; the Muse lineage (~370 commits, own
work_queue/Cannon motor/P4-P6 server) is not adopted wholesale. result_id stays bound to
goal/task/attempt/dispatch/worker and is persisted before first send (resend identical).

Muse target: 16/32/64 Auto, staged 1 -> 4 -> 8 -> 16 -> 32 -> 64; 64 only after a stable 32 proof.
READY directories are not live Muse sessions. Do not overwrite a scope while Muse is its writer.

Routing (cheap first): Google and Muse for logs, inventories, searches, branch comparison, small
fixes; Codex only for proven hard P0 (process tree, timeout, crash/resume, duplicates, lost
results); Opus only for hard architecture/integration.

Shield / Shield Items: SHIELD_DEFINITION=UNRESOLVED. Repo-wide search found only shields.io
badges; do not invent a definition.

Open / local only: confirm Codex resource guard; Muse CLI prompt-method audit; review/merge PR of
the convergence branch (human gate); apply both P3 patches + Mac/Windows canaries; Windows
Antigravity UI_VISIBLE + GOOGLE_E2E; push local commit e5e7da17 and
docs/windows/ANTIGRAVITY_RECOVERY_2026-09-25.md (not on GitHub as of this record).
