# User Acceptance F — Onboarding / Permissions: "Welche Daten/Berechtigungen nutzt Courier?"

Status: OPERATOR ACCEPTANCE (USER WINDOW) — 2026-09-28
Product Shell: NOT unlocked. Prep-only, no implementation.

## USER_PROBLEM
A normal user cannot answer "welche Daten/Berechtigungen nutzt Courier, und wie
komme ich in 5 Minuten zu einem laufenden System?" There is no permission/data
inventory, the server listens on all interfaces by default, and key separation is
asserted but not pinned to enforcement.

## CURRENT_RUNTIME_TRUTH (verified by reads, shell down, no execution)
- `server/app.py:559-560` binds `0.0.0.0:8080` — reachable from the whole LAN by
  default, not localhost-only. No bind-address configuration observed.
- Auth is bearer keys from environment (client side: `scripts/courier_beacon.py:18`,
  verifier/daemon env usage); routes are guarded by `@require_auth`
  (e.g. `server/app.py:85,96`). Key-SEPARATION (worker key ≠ verifier key) is
  required by run prep (`ops/ai/RUN_PREP_AND_CORE_FREEZE_PACK.md:9` + key-separation
  notes) but no separation check was observed in the code read — enforcement
  status UNVERIFIED, must be pinned, not assumed.
- Playbook Phase 6 demands permission/data scope, deletion/retention note, and
  provider/data-flow inventory before pilot
  (`ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md:256-271`) — NO such
  inventory file exists in the `docs/*.md` or `ops/ai/*.md` listings.
- `ops/ai/PROVIDER_ISOLATION_SPEC.md` covers capability routing + failure
  isolation only — no data scopes, no retention, no permission prompts.
- Setup target <5 min (`ops/ai/PILOT_METRICS_AND_SIGNAL_SPEC.md:6`) with no
  measured value and (by design, pre-pilot) no installer; manual setup is allowed
  but unmeasured.

## ACCEPTANCE_REQUIREMENT
F-1: Onboarding MUST state up front: listening sockets (host:port + interface),
  key provisioning + rotation, worker/verifier key-separation enforcement,
  data stores (state JSON, artifact dir, logs, evidence) + retention/deletion,
  provider data flows (what leaves the machine, to whom), permission prompts.
F-2: Defaults MUST be least-privilege (localhost bind unless LAN is explicitly
  needed) or the LAN exposure MUST be an explicit, logged operator choice.
F-3: First-setup time MUST be measured per pilot (setup minutes are a pilot metric).

## MISSING_SYSTEM_SUPPORT
- Data/permission inventory file (pilot-prep owner scope).
- Key-separation enforcement: verify-or-implement (writer scope).
- Measured manual-setup runbook (allowed pre-pilot; must record minutes).

## PREPARABLE_NOW (no code, this pass)
- Inventory template + onboarding acceptance checklist (this file).

## BLOCKED_UNTIL
- Pilot-prep owner fills inventory; writer pins bind-address + key separation.

## NEXT
G — Update/Rollback/Last Known Good (item G file).
