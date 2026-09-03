# 2026-Courier — Autonomous Engineering & Control Plane (Computer A)

> **Central Motto:** *"WIR MÜSSEN JEDEN TAG BESSER WERDEN WIE DIE ANDEREN."*
> **Permanent Research Question:** *"Wie können wir aus Werkzeugen, die uns heute helfen, Werkzeuge und Agenten bauen, die morgen selbst herausfinden, wie sie uns noch besser helfen können?"*

`2026-courier` is the deterministic, safe, zero-spend autonomous operations and engineering engine for **Computer A** (Primary Builder: Google / Antigravity).

---

## 🏛️ System Architecture

```
                                  ┌───────────────────────────────┐
                                  │      CHIEF & HQ DASHBOARD     │
                                  │   (Visual Agent HQ, Port 8080)│
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                                  ┌───────────────────────────────┐
                                  │     CANONICAL AUTHORITY       │
                                  │ (OS-level flock, epoch lease) │
                                  └───────────────┬───────────────┘
                                                  │
          ┌───────────────────────────────────────┼───────────────────────────────────────┐
          │                                       │                                       │
          ▼                                       ▼                                       ▼
┌──────────────────┐                    ┌──────────────────┐                    ┌──────────────────┐
│  LIVE WORKER     │                    │  HOST SURVIVAL   │                    │ CONTINUOUS SAFE  │
│  REGISTRY        │                    │  & DR ENGINE     │                    │ WORK DISPATCHER  │
│(PID truth, audit)│                    │(Fencing, reboot) │                    │(Opportunity queue│
└─────────┬────────┘                    └─────────┬────────┘                    └─────────┬────────┘
          │                                       │                                       │
          └───────────────────────────────────────┼───────────────────────────────────────┘
                                                  │
                                                  ▼
                                  ┌───────────────────────────────┐
                                  │ COMPOUND INTELLIGENCE FLYWHEEL│
                                  │  (Challenge, Exp, Distill)    │
                                  └───────────────────────────────┘
```

### Core Subsystems

1. **Canonical Mutation Authority (`scripts/canonical_authority.py`)**
   - Single-machine OS-level `flock` exclusive boundary.
   - Monotonically increasing fencing tokens (generations) protecting against split-brain mutations.
   - Fail-closed validation for corrupt or zero-byte lock records.

2. **Host Survival & Reboot Recovery Engine (`scripts/host_survival_engine.py`)**
   - Host generation fencing token to protect against old-host return.
   - Cryptographically hashed Disaster Recovery (DR) manifest verification.
   - Zero-blind-replay reboot reconciliation (ambiguous jobs quarantined).

3. **Live Worker Registry & Snitch Observer (`scripts/live_worker_registry.py`, `scripts/snitch_observer.py`)**
   - Authoritative PID liveness verification (`os.kill(pid, 0)`).
   - Real-time detection of permission prompt blocks (`WAITING_PERMISSION`).
   - Strict distinction between `SAFE_IDLE_AFTER_FULL_DISCOVERY` and `PREMATURE_IDLE`.

4. **Continuous Safe Work Dispatcher (`scripts/continuous_safe_work_dispatcher.py`)**
   - Priority-ranked opportunity discovery across safe local tasks.
   - Deduplication protection using SHA-256 task completion fingerprints.
   - Fail-closed gates on `PAYMENT_APPROVAL_REQUIRED` and `WAITING_FOR_HUMAN`.

5. **Compound Intelligence Flywheel (`scripts/compound_intelligence_flywheel.py`)**
   - Compounding scoring weights (1x Single Task $\to$ 50x Meta-Improvement).
   - Adversarial challenge and experimental validation requiring $>5\%$ verified gain before adoption.
   - Organizational memory persistence in `events/knowledge-base/distilled_lessons.json`.

6. **Adaptive Solution Discovery (`scripts/adaptive_solution_discovery.py`)**
   - Self-tuning search cadence (1 day under high change $\to$ 7 days strategic floor under stability).
   - 7 event-wake triggers for early out-of-cycle rechecks.

---

## 🔒 Hard Safety & Operational Policies

- **Autonomous Spend Limit:** Strictly **0.00 EUR**. No paid API credits, subscriptions, or external charges without explicit human payment authorization.
- **Single Heavy Job Limit:** Exactly **1** heavy compute job at a time.
- **Fail-Closed Security:** Corrupt state files, missing PIDs, or unverified tokens fail closed immediately.
- **No Blind Replay:** Ambiguous reboot state routes to `WAITING_HUMAN`.
- **No Publication Without Authority:** Social media and creator publication remain hard-gated behind explicit Human Gates.

---

## 🚀 Key Commands

### 1. Unified Autonomous System Readiness Check (<0.05s)
```bash
python3 scripts/verify_autonomous_readiness.py
```

### 2. Live Agent HQ & Command Center Dashboard (Port 8080)
```bash
python3 dashboard/server.py
```

### 3. Run Full Modern Acceptance Regression Suite (35 suites, 184 tests)
```bash
python3 -m unittest -v \
  tests/test_verify_autonomous_readiness.py \
  tests/test_dashboard_server.py \
  tests/test_live_worker_registry.py \
  tests/test_host_survival_engine.py \
  tests/test_snitch_observer.py \
  tests/test_compound_intelligence_flywheel.py \
  tests/test_endurance_canary.py \
  tests/test_daily_ai_improvement_council.py \
  tests/test_adaptive_solution_discovery.py \
  tests/test_autonomous_production_canary.py \
  tests/test_mission_217_investigate_fix_verify_loop.py \
  tests/test_mission_216_general_autonomous_engineering.py \
  tests/test_mission_215_goal_driven_autonomous_engineering.py \
  tests/test_mission_214_anti_premature_idle_and_snitch.py \
  tests/test_mission_213_real_safe_backlog.py \
  tests/test_mission_212_productive_capacity.py \
  tests/test_mission_210_continuous_safe_work_dispatch.py \
  tests/test_mission_206_hq_operations_daemon.py \
  tests/test_mission_203_live_hq_telemetry_bridge.py \
  tests/test_live_agent_hq_mission_199.py \
  tests/test_bootstrap_replacement_host.py \
  tests/test_disaster_recovery_bundle_sync.py \
  tests/test_multi_host_failover_coordinator.py \
  reviewer_oracles/test_mission_202r_acceptance.py \
  reviewer_oracles/test_autonomy_crash_safety_oracle.py \
  tests/test_continuous_autonomous_operations.py \
  tests/test_level5_multi_host_failover.py \
  tests/test_real_failover_simulation.py \
  tests/test_external_survival_and_takeover.py \
  tests/test_host_survival_layer.py \
  tests/test_autonomy_supervisor.py \
  tests/test_autonomy_orchestrator.py \
  tests/test_google_capacity_benchmark.py \
  tests/test_canonical_authority_root_cause.py \
  tests/test_mission_211_authority_bypasses.py
```

---

## 📁 Repository Directory Structure

- `scripts/` — Subsystem engines, controllers, registries, and autonomy dispatchers.
- `tests/` — Automated unit and acceptance test suites (184 unit tests, 100% PASS).
- `reviewer_oracles/` — Acceptance oracle test harnesses (Crash Safety Oracle, M202R).
- `dashboard/` — Zero-dependency web UI and HTTP status API for Visual Agent HQ.
- `events/` — Durable runtime event directory:
  - `worker-registry/` — Active registered workers and heartbeat state.
  - `runtime-state/` — Snapshots, central motto, discovery proofs, and safe idle semantics.
  - `host-survival/` — Fencing tokens and DR manifests.
  - `opportunity-queue/` — Actionable, completed, and human-gated opportunities.
  - `knowledge-base/` — Distilled organizational lessons and compounding knowledge.
  - `runtime-alerts/` — Deduplicated Snitch anomaly alerts.
  - `worker-events/` — Compacted runtime event stream (`evt-*.json` and `archive/`).
