# Muse Mac Progress Wall — 30-window plan — 2026-09-26

Purpose: use available Muse capacity for long-running, non-conflicting progress while preserving the Courier critical path.

## Allocation

- 1 WALL_MASTER
- 18 CORE_EVIDENCE_WORKERS
- 4 WEBSITE/PILOT_LAUNCH_PREP workers
- 3 COMMERCIAL_PREP workers
- 2 MAC_CANARY_PREP workers
- 1 SNAPSHOT_SENTINEL
- 1 EVIDENCE_PUBLISHER

Total: 30 windows.

## Laws

- No duplicate architecture.
- No new scheduler/ledger/wall implementation.
- No source writes to the final candidate unless explicitly assigned to the authorized writer.
- Product Shell remains locked; website work is limited to public landing/pilot/download-preparation that does not claim unproven capabilities.
- No fake metrics, no fake customer claims.
- No busywork.
- UNKNOWN stays UNKNOWN.
- Prefer long-running queue consumption over human relay.
- If a queue is empty, sleep cheaply and re-check rather than inventing tasks.

## Current critical path

Bound candidate -> Codex review -> Mac Muse/runtime binding -> physical A->VERIFY->B -> restart/no-replay -> pilot.

## Website / launch lane

Allowed before pilot:
- static landing page preparation;
- public copy based on already-proven claims;
- FAQ;
- waitlist/pilot-interest form design;
- download/install information architecture;
- privacy/data-flow prep;
- manual onboarding guide;
- pilot pricing/payment preparation;
- screenshots/demo storyboard only from real evidence.

Not allowed before proof:
- claim that zero-human/restart is proven when it is not;
- full Product Shell;
- billing platform;
- installer claims without a real installer;
- enterprise/admin/marketplace work.

## Progress wall behavior

The WALL_MASTER maintains a durable queue under the Mac report root. Workers claim independent tasks and write unique reports. One publisher syncs safe evidence/reports to the Muse Mac evidence branch so the coordinator can later read progress without manual relay.
