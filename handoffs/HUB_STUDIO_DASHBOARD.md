# Handoff: Visual Multi-Agent Operations Dashboard (HUB)

## Mission Context
The `CHIEF-WEBSITE-VERIFICATION` is currently blocked by manual DNS configurations (STRATO Apex-A and SPF). In accordance with the "CONTINUOUS EXECUTION" directive, I am passing this unblocked task to the appropriate writer.

## Target Workkey
**P1 | PLANNED | Visual multi-agent operations dashboard / studio**
- **Dependency / evidence boundary**: Consume existing machine-readable Courier state. It must label native local Codex evidence separately from unverified Work, GitHub Actions, and normal-Chief-chat stages.
- **Lane**: L5 Desktop Hub / Replay

## Current State
- The `dashboard/` directory contains an MVP node/python server (`server.py`) and UI (`app.js`, `index.html`, `style.css`).
- `studio/` contains `execution_truth.js` and a separate studio interface.
- `server.py` currently reads from `events/` and provides status payloads via `/api/status`.

## Next Action for the L5 Writer
1. **Unify Dashboard and Studio:** Ensure that `execution_truth.js` or `app.js` can differentiate between verified local Codex evidence and unverified CI/GH actions.
2. **Read Ledger Events:** Render the `events/` payload in real-time, matching the schema defined in `scripts/coordination_ledger.py` and `scripts/coordination_resume.py`.
3. **Verify:** Launch `dashboard/server.py` and confirm that it visually represents the multi-agent operations without errors and accurately distinguishes verified from unverified states.

## Writer Assignment
**Target Agent:** L5 Desktop Hub Writer (or Windows AntiGravity/Muse if designated).
**Action:** Claim this task, implement the verified UI layers, and commit the changes to `integration/v1`.
