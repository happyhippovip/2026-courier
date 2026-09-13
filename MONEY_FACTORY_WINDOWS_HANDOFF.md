# MONEY FACTORY WINDOWS HANDOFF

## 1. Environment & Workspace Metadata
- **WORKSPACE**: `C:\Users\lol\2026-workspace\courier`
- **BRANCH**: `windows/money-factory-p0`
- **CURRENT_HEAD**: `aa5c01d21c7e055c7e3b5117ded5eddc6793dde4` (`docs: add Money Factory P0 architecture and integration blueprint`)
- **PREVIOUS_COMMIT**: `c9053cf5dd43fa9f73aca2760fe8fd18c2f20068` (`feat(money_factory): implement P0 durable autonomous foundation and deterministic test suite`)
- **GIT_STATUS**: Working tree clean prior to handoff creation (`MONEY_FACTORY_WINDOWS_HANDOFF.md` remains untracked as instructed)

---

## 2. Files Created in P0 Build
- `opportunity_warehouse/opportunities.yaml` (durable YAML schema with explicit UNKNOWN values)
- `opportunity_warehouse/opportunities.json` (machine-readable store)
- `opportunity_warehouse/LEADERBOARD.md` (radar across NOW, 30D, 365D, ASYMMETRIC)
- `opportunity_warehouse/MONEY_FACTORY_POLICY.md` (hard safety invariants & anti-loop rules)
- `opportunity_warehouse/history_ledger.json` (append-only audit history)
- `money_factory/warehouse.js` (lifecycle state machine & zero-dependency YAML serialization)
- `money_factory/scoring.js` (deterministic multi-factor economic scoring)
- `money_factory/portfolios.js` (portfolio horizon weights: 50% CASH_NOW, 35% GROWTH, 15% MOONSHOTS)
- `money_factory/seed_classes.js` (7 strategic seed categories initialized with explicit UNVERIFIED/UNKNOWN evidence)
- `money_factory/cycle_ledger.js` (durable cycle identity MONEY-YYYY-MM-DD, SHA-256 fingerprint, missed-cycle catch-up)
- `money_factory/prediction_calibration.js` (immutable prediction history & actuals reconciliation)
- `money_factory/safety_gates.js` (zero-spend guardrail, 14 human gates, structured SPEND_REQUEST)
- `money_factory/anti_loop_policy.js` (post-freeze Courier infrastructure lock & Money Truth Firewall)
- `money_factory/leaderboard_generator.js` (markdown leaderboard exporter)
- `money_factory/index.js` (unified library entry point)
- `tests/test_money_factory_p0.js` (18 deterministic invariant tests)
- `MONEY_FACTORY_ARCHITECTURE.md` (architecture & post-freeze integration guide)

---

## 3. Test Verification & Commands
- **TEST_COMMANDS**:
  ```powershell
  $env:PATH = "C:\Users\lol\AppData\Local\OpenAI\Codex\runtimes\cua_node\b474a88d5d105afa\bin;" + $env:PATH
  node tests/test_money_factory_p0.js
  node tests/test_cross_device_intake.js
  ```
- **TEST_TOTAL**: 26 (18 Money Factory P0 + 8 Cross-Device Intake)
- **TEST_PASS**: 26
- **TEST_FAIL**: 0
- **TEST_ERROR**: 0

---

## 4. Safety Invariants Hard-Coded
- `AUTONOMOUS_SPEND_LIMIT_EUR = 0`
- `REAL_TRADES = 0`
- `REAL_FUNDS_TOUCHED = NO`
- `REAL_POSITIONS_CHANGED = 0`
- `REAL_WALLETS_CONNECTED = NO`
- `WALLET_SIGNING = NO`
- Mandatory `HUMAN_GATE` for all 14 critical operations (payment, subscription, purchase, upgrade, overage, publication, production deployment, customer outreach, external message, real trade, wallet signing, account creation, login/2FA/KYC, real spend).

---

## 5. Codex Review Verdict
- **CODEX_REVIEW_VERDICT**: `READY_FOR_POST_FREEZE_INTEGRATION_WITH_STRICT_FIREWALL`

---

## 6. Architectural Invariant
- Money Factory is a **deterministic domain library/state warehouse**.
- Courier remains the **ONLY canonical execution/orchestration engine**.
- Money Factory must **never become a second scheduler/orchestrator**.

---

## 7. Post-Freeze Next Action
- Review Windows commits/diff against Codex findings, then integrate the minimum Money Factory API into the proven Courier baseline.

---

## 8. DO NOT REPEAT
- Do not rebuild Money Factory P0.
- Do not rerun architecture discovery.
- Do not recreate Opportunity Warehouse.
- Do not redo the existing 26-test P0 proof unless integration changes relevant code.
