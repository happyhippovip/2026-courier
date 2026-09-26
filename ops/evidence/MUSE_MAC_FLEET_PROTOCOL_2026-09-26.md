# Muse Mac Fleet Evidence Protocol — 2026-09-26

Purpose: parallelize physical Mac Canary preparation without requiring manual relay.

Current bound Windows candidate:
- branch: candidate-b-1
- SHA: 4c1e24ccc522042af826bc4c2b595daf85d097f9
- base: e7d047d9771bc8f0dd7d1f296983dd8171940b7d

Rules:
- Evidence-only branch. No Courier source changes here.
- One Fleet Master creates bounded tasks.
- Many workers claim unique tasks and write unique local reports.
- One Publisher mirrors safe reports into this branch.
- Never publish secrets/.env/tokens/credentials/private user data.
- No Canary execution until exact candidate review + runtime preflight permit it.
- No process kills/restarts unless separately authorized.
- No busywork; duplicate work is skipped.
- UNKNOWN stays UNKNOWN.
- Critical path: exact candidate review -> Mac Muse/adapter binding -> runtime/isolation -> physical A->VERIFY->B -> restart/no-replay.
