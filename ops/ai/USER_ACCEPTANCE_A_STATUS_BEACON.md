# User Acceptance A — Status / Phase: "Was macht Courier gerade?"

Status: OPERATOR ACCEPTANCE (USER WINDOW) — 2026-09-28
Product Shell: NOT unlocked. Prep-only, no implementation.

## USER_PROBLEM
A normal user cannot answer "Was macht Courier gerade? Ist es noch aktiv?
In welcher Phase sind wir?" without reading 5+ state files
(GATE_STATE, WALL_QUEUE, PROOF_CARD, CRITICAL_PATH_SYNTHESIS, playbook),
which partly contradict each other (see items D and E).

## CURRENT_RUNTIME_TRUTH (verified by reads, shell down, no execution)
- Beacon contract exists but is DEFERRED: `docs/COURIER_PROGRESS_BEACON_CONTRACT.md:4,16`.
  Required founder line `docs/COURIER_PROGRESS_BEACON_CONTRACT.md:22` does not exist at runtime.
- Only beacon implementation `scripts/courier_beacon.py:24-31` polls `GET /system/metrics`,
  which has no server route (only client reference). It always prints
  "Failed to fetch metrics" every 5s (`scripts/courier_beacon.py:74-77`).
  Its halt call `POST /system/halt` (`scripts/courier_beacon.py:36`) also has no route.
- `GET /status` returns 4 counters only (`server/app.py:83-92`); no phase, no state,
  no relay count, no next action. `GET /health` is a static ping (`server/app.py:79-81`).
- Wall slot states (e.g. `runtime/slots/MUSE-01/state.json` = DONE/process null)
  describe stale agent slots, not product status.
- Overheat gate says "PRODUCTION WORK IS BLOCKED UNTIL THIS GATE IS SATISFIED"
  (`docs/HOST_OVERHEAT_INCIDENT_AND_RESUME_GATE.md:5`), but no satisfaction record
  exists anywhere (0 hits for OVERHEAT_SATISFIED/RESUME_GATE PASS/GREEN in ops/ai + docs).
  The user cannot know whether running anything is currently allowed.

## ACCEPTANCE_REQUIREMENT
A-1: One derived, read-only status record answers: phase, state, last real progress
  (+ evidence ref), active work, open blockers, human relays, next safe action.
  It MUST be derived from canonical state; it MUST NOT declare PASS by itself
  (beacon contract core rule).
A-2: Status MUST expose whether the overheat resume gate is satisfied or still blocking.
A-3: Status MUST work against routes that exist; references to vapor endpoints
  (`/system/metrics`, `/system/halt`) MUST be resolved (implement or remove refs).

## MISSING_SYSTEM_SUPPORT
- Beacon implementation against real routes/state (contract is doc-only).
- Durable overheat-gate satisfaction record (pass/fail + evidence + date).
- Canonical "current phase" field (playbook phase vs gate files disagree on Codex stage).

## PREPARABLE_NOW (no code, this pass)
- This requirement + a status-record JSON schema sketch (fields per beacon contract).
- Contradiction pointers to items D (proof) and E (next action).

## BLOCKED_UNTIL
- Runtime implementation: after Core Freeze (server API must be stable first,
  incl. the `/system/metrics` decision). Rollout gated on pilot signal (item J).
- Gate satisfaction record: Mac owner observation (human evidence, not this window).

## NEXT
B — "Braucht dich" (item B file).
