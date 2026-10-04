# 2026-Courier — Autonomous Engineering & Control Plane (Computer A)

> **Central Motto:** *"WIR MÜSSEN JEDEN TAG BESSER WERDEN WIE DIE ANDEREN."*
> **Permanent Research Question:** *"Wie können wir aus Werkzeugen, die uns heute helfen, Werkzeuge und Agenten bauen, die morgen selbst herausfinden, wie sie uns noch besser helfen können?"*

`2026-courier` is the deterministic, safe, zero-spend autonomous operations and engineering engine for **Computer A** (Primary Builder: Google / Antigravity).

---

## 🏛️ V1 System Architecture

Courier v1 is structured around a centralized event journal, a bounded worker, and a desktop-native Hub.

### Core Components

1. **`courier-core` (Controller)** — Owns goals and task orchestration. Enforces the integration contract and append-only event journal.
2. **`courier-worker` (Worker Daemon)** — Independent host agent that claims tasks, executes adapters (e.g. Gemini), and reports results.
3. **`courier-hub` (Desktop Hub)** — The human-in-the-loop desktop interface. Displays canonical task state (Needs You, Working, Done).

### Startup & CLI

Courier v1 provides standardized entrypoints via `pyproject.toml`:

| Command | Purpose |
|---|---|
| `courier-core` | Start the central controller (`courier_core.cli:main`). |
| `courier-worker` | Start the local worker daemon (`courier_worker.cli:main`). |
| `courier-hub` | Start the desktop Hub UI server (`courier_hub.cli:main`). |

*Note: The legacy `scripts/` and `server/` components are currently preserved during the migration to V1.*

---

## 🔒 Hard Safety & Operational Policies

- **Autonomous Spend Limit:** Strictly **0.00 EUR**. No paid API credits, subscriptions, or external charges without explicit human payment authorization.
- **Single Heavy Job Limit:** Exactly **1** heavy compute job at a time.
- **Fail-Closed Security:** Corrupt state files, missing PIDs, or unverified tokens fail closed immediately.
- **No Blind Replay:** Ambiguous reboot state routes to `WAITING_HUMAN`.
- **No Publication Without Authority:** Social media and creator publication remain hard-gated behind explicit Human Gates.

---

## 🚀 Key Commands

### 1. Run the v1 Test Suite (Golden + Hub + Core + Worker)
```bash
python3 -m pytest tests/ -v
```

### 2. Local physical acceptance harness
```bash
COURIER_API_KEY=... COURIER_VERIFIER_API_KEY=... python3 scripts/acceptance/run_final_acceptance.py
```

---

## 📁 Repository Directory Structure

- `courier_core/` — Central state machine, journal, and controller.
- `courier_worker/` — Host worker daemon, adapter runner, and execution boundary.
- `courier_hub/` — Local HTTP server and API for the Desktop UI.
- `desktop/` — Web/UI assets for the Courier Hub.
- `adapters/` — Execution implementations (Gemini, CLI, etc.).
- `deploy/` — Legacy Linux/macOS install scripts.
- `tests/` — Unified test suite for V1 and legacy boundaries.

---

## Canonical Courier Symphony Product Plan

Product priority, proof levels, Autonomy Grades, Goal Contracts, pilot metrics, Scope Freeze and gate transitions are governed by [docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md](docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md).
