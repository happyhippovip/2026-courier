# Courier Symphony — Agent Bootstrap

This repository has a locked V1 destination. Before changing code or orchestrating work, read:

1. `docs/V1_RULE_0.md`
2. `docs/V1_PRODUCT_QUALITY_BAR.md
- docs/V1_AUTOMATION_ADVANTAGE.md
- docs/V1_DOMAIN_ASSURANCE_PROFILES.md`
3. `docs/V1_ORCHESTRATION_PLAYBOOK.md`
4. `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`
5. `docs/NEXT_CHAT_HANDOFF.md`
6. newest relevant rules in GitHub Issue #54
7. CURRENT `integration/v1`
8. `docs/v1/INTEGRATION_LOG.md`

RULE 0.000000000: **FINISH THE PRODUCT.**

Locked route:

**ACTIVE LEDGER -> RELIABLE AUTOMATION -> GOLDEN PATH -> DESKTOP HUB -> WINDOWS EXE -> CLEAN-MACHINE ACCEPTANCE -> REAL ADAPTERS -> DESKTOP ROBOT OVERLAY**

Only six V1 writer lanes exist:
- L1 Integration / CI / Golden Harness
- L2 Journal / Controller / API
- L3 Bounded Worker Host
- L4 Verifier / Synthetic Adapter
- L5 Desktop Hub / Replay
- L6 Packaging / Launcher / Paths / Logging / Diagnostics

Do not create a seventh writer lane. Read-only review/factory/scout work is allowed.

Orchestration rules:
- verify CURRENT repo state before assigning work;
- use deep queued workflows/skills instead of repeated identical prompt storms;
- HUMAN-TIME RULE: when related read-only tasks can safely share context, give the owner one master prompt per window instead of many small copy/paste prompts; split only for a concrete technical reason;
- preserve bounded live concurrency;
- prompt length or queue count does NOT guarantee runtime; use Muse `/loop`/goals/workflows for real continuation rather than manual duplicate queues;
- on Windows, default to one retained Muse steward for recurring read-only work; use Antigravity bounded background subagents for real parallel read-only fan-out;
- Mac resource history means EMFILE/host pressure is a hard signal to stop new helper spawning;
- no active window/workflow may be cleared, closed, or repurposed until custody is proven;
- unknown custody => not safe to clear/close;
- L1 is the only lane that promotes/merges work into `integration/v1`;
- historical branches are evidence, not current truth;
- no architecture churn without a concrete contradiction in CURRENT implementation.

Customers never operate prompts, agents, lanes, branches, model settings, or developer recovery procedures.

When in doubt: choose the action that shortens the locked route without weakening correctness, replay, process safety, customer simplicity, or clean-machine acceptance.

## Cursor Cloud specific instructions

- Python 3.12 is already installed as `python3`, and Node is already installed for `node --test`. Courier has no database and no process that must stay up across boots. The environment install links `python` to `python3`, runs `python3 -m pip install --user -e ".[test]"`, and links `pytest`, `courier-core`, `courier-hub`, `courier-worker`, and `courier-listclean` into `/usr/local/bin`. A user-site install places those console scripts in `~/.local/bin`.
- From the repository root, run `python -m pytest -q --timeout=180 tests`. The suite takes about seven minutes and must leave the worktree clean. Desktop logic: `node --test tests/desktop/*.test.mjs`. Safety ratchet: `python scripts/check_local_safety.py . --baseline acceptance/local_safety_baseline.json`.
- Product check: `python -m courier_hub.demo` starts the controller, a worker, and the hub, submits three synthetic tasks (checked, needs a person, still working), and prints a hub URL on `127.0.0.1`. Stop that process with Ctrl+C. The hub HTTP server does not need a display. Leave `courier-hub --with-overlay` for a machine with a GUI.
- Run the default tests without API keys. Keep provider credentials out of the environment.
