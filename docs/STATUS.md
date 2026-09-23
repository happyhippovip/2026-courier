# Courier Symphony — STATUS

Stand: 23.09.2026

## Current stage

**Stufe 1 — Cannon V1 fertig und einfrieren**

Strategic source: `docs/MASTERPLAN_COURIER.md`

## Known evidence

- `pre-yolo-patch(-v2)` = `49150d3f`
- `yolo-patch-applied-v2` = `e98ce2cc`
- Official baseline between those references: **UNKNOWN**
- Exact live-text failure: **UNKNOWN** until reproduced with evidence
- Target acceptance includes Mac + Windows evidence, 5-run Cannon acceptance, and evaluation of the infinite run
- Freeze target: tag `courier-cannon-v1` + bundle backup; canonical push/release requires Dennis approval

## Cannon V1 acceptance

Required evidence:
- Mac run
- Windows run
- `result_id == full commit hash`
- `DUPLICATE_EXECUTIONS = 0`
- `LOST_RESULTS = 0`
- emergency stop < 15 seconds
- 5-run acceptance green
- infinite-run result evaluated

## Next single step

Determine and prove the official `pre-yolo-patch` baseline before changing tests merely to make them green.

## Status rule

Every update must classify claims as:
- BELEGT
- BEHAUPTET
- VERMUTET
- UNKNOWN

Do not place funding, Jobcenter, billing, account, credentials, secrets, or customer-private material in this public repository.
