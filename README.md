# 2026-Courier — Autonomous Engineering & Control Plane (Computer A)

> **Central Motto:** *"WIR MÜSSEN JEDEN TAG BESSER WERDEN WIE DIE ANDEREN."*
> **Permanent Research Question:** *"Wie können wir aus Werkzeugen, die uns heute helfen, Werkzeuge und Agenten bauen, die morgen selbst herausfinden, wie sie uns noch besser helfen können?"*

`2026-courier` is the deterministic, safe, zero-spend autonomous operations and engineering engine for **Computer A** (Primary Builder: Google / Antigravity).

---

## 🏛️ System Architecture

```
            goals / operator                     GitHub Actions runners
                   │                                      ▲
                   ▼                                      │ workflow dispatch
┌──────────────────────────────────┐        ┌──────────────────────────────┐
│  server/app.py  (state server)   │◀──────▶│ courier_github_dispatcher.py │
│  goals · claim · result · verify │        └──────────────────────────────┘
│  scripts/integration_contract.py │        ┌──────────────────────────────┐
└──────┬──────────────┬────────────┘◀──────▶│ courier_verifier.py          │
       │              │                     │ (independent effect check)   │
       │              │                     └──────────────────────────────┘
       │              │                     ┌──────────────────────────────┐
       │              └────────────────────▶│ courier_watchdog.py          │
       │                                    │ (stale-claim quarantine)     │
       ▼                                    └──────────────────────────────┘
  Workers: scripts/mac_worker/ · scripts/windows_worker/ · github_worker_adapter.py
```

### Core Components

1. **State server (`server/app.py`)** — owns goals, tasks and workers; serves
   `/goals`, `/workers/*`, `/tasks/claim`, `/tasks/result`, `/tasks/verify`.
   Worker success alone never advances a goal.
2. **Integration contract (`scripts/integration_contract.py`)** — task packets
   carry `goal_id`, `task_id`, `attempt_id`, `dispatch_id` and `worker_id`;
   results and evidence must match that identity exactly or fail closed.
3. **Verifier (`scripts/courier_verifier.py`)** — separately authenticated;
   observes the artifact/effect before a task is marked verified.
4. **GitHub dispatcher (`scripts/courier_github_dispatcher.py`)** — routes
   GitHub-capable tasks to hosted runners.
5. **Watchdog (`scripts/courier_watchdog.py`)** — reclaims or quarantines stale
   claims without blind replay.
6. **Workers** — Mac and Windows daemons plus the GitHub worker adapter; all
   credentials come from the environment (`COURIER_API_KEY`).

### Startup authorities

| Component | Production start | Notes |
|---|---|---|
| Server (`server.app`) | `deploy/run-supervisor.sh` (gunicorn) via `deploy/courier.service` (Linux) or the `com.courier.server` LaunchAgent from `deploy/install_mac_runtime.sh` / `scripts/setup_local_autonomy.sh` (macOS) | `scripts/start_daemon.sh` / `stop_daemon.sh` are a dev-only alternative (Flask dev server) |
| Verifier, GitHub dispatcher, watchdog | started by the same `run-supervisor.sh` | need `COURIER_API_KEY` and a different `COURIER_VERIFIER_API_KEY` |
| Mac worker | LaunchAgent `com.courier.mac_worker` from `scripts/mac_worker/install.sh` | key and server URL from the macOS Keychain (`setup_keychain.sh`) or environment |
| Windows worker | Scheduled Task `CourierWindowsWorker` from `scripts/windows_worker/bootstrap.ps1` | key and server URL from environment or the local `config.json` written by bootstrap |
| GitHub worker | `.github/workflows/courier_worker.yml`, dispatched per task | results collected by `github_worker_adapter.py` |

All components read the server address from `COURIER_SERVER`.

The earlier Studio HQ / autonomous-supervisor stack (canonical authority, host
survival, snitch observer, opportunity queue, flywheel) is **not** part of the
current Courier and was retired from this repository.

---

## 🔒 Hard Safety & Operational Policies

- **Autonomous Spend Limit:** Strictly **0.00 EUR**. No paid API credits, subscriptions, or external charges without explicit human payment authorization.
- **Single Heavy Job Limit:** Exactly **1** heavy compute job at a time.
- **Fail-Closed Security:** Corrupt state files, missing PIDs, or unverified tokens fail closed immediately.
- **No Blind Replay:** Ambiguous reboot state routes to `WAITING_HUMAN`.
- **No Publication Without Authority:** Social media and creator publication remain hard-gated behind explicit Human Gates.

---

## 🚀 Key Commands

### 1. Run the runtime (server + verifier + dispatcher + watchdog)
```bash
export COURIER_API_KEY=...            # never commit real keys
export COURIER_VERIFIER_API_KEY=...
deploy/run-supervisor.sh
```

### 2. Contract and integration tests
```bash
python3 -m pytest -q \
  tests/test_integration_contract.py \
  tests/test_server_integration_contract.py \
  tests/test_result_identity_binding.py \
  tests/test_github_worker_adapter.py
```

### 3. Local acceptance harness (throwaway server on port 8081)
```bash
COURIER_API_KEY=... COURIER_VERIFIER_API_KEY=... python3 scripts/acceptance/run_final_acceptance.py
```

---

## 📁 Repository Directory Structure

- `server/` — State server (`app.py`) and its launchers.
- `scripts/` — Integration contract, verifier, dispatcher, watchdog, worker adapters.
- `scripts/mac_worker/`, `scripts/windows_worker/` — Host worker daemons.
- `deploy/` — Linux/macOS install scripts and `run-supervisor.sh`.
- `tests/` — Unit, contract and acceptance tests.
- `dashboard/` — Status dashboard.
- `docs/` — Product plan, protocols and brand system.

---

## Canonical Courier Symphony Product Plan

Product priority, proof levels, Autonomy Grades, Goal Contracts, pilot metrics, Scope Freeze and gate transitions are governed by [docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md](docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md).

This plan is governance, not runtime evidence. Current code/runtime/acceptance evidence still decides what is actually implemented or proven. Personal payment/account identifiers are never stored in this public repository.
