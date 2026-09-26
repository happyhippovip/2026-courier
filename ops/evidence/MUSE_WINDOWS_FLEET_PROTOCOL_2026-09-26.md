# Muse Windows Fleet Evidence Protocol — 2026-09-26

Purpose: keep read-only/prep Muse work useful without requiring the user to relay reports manually.

Branch: `evidence/muse-windows-20260926`

Rules:
- This branch is evidence-only. Never merge or push source/runtime changes here.
- One publisher process is the only writer to this branch.
- Workers write unique reports under `C:\Users\lol\courier_work\muse_fleet\reports`.
- Critical snapshots go under `C:\Users\lol\courier_work\muse_fleet\snapshots`.
- Publisher mirrors safe report/snapshot artifacts into `ops/evidence/muse/windows/2026-09-26/`.
- Never publish secrets, .env files, tokens, credentials, account data, or private user data.
- No force push, no main push, no merges to production branches.
- No busywork: duplicate tasks are skipped, UNKNOWN stays UNKNOWN, empty queue means low-cost sleep/wait.
- Critical path: bound candidate -> artifact/content verification -> duplicate/replay safety -> physical A->VERIFY->B -> restart/no-replay.
- Physical Canary execution itself requires explicit authorization; fleet workers only prepare/inspect unless separately assigned.
