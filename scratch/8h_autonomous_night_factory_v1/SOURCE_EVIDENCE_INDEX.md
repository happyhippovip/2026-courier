# SOURCE EVIDENCE INDEX

**Mission ID**: `WINDOWS_COURIER_8H_AUTONOMOUS_NIGHT_FACTORY_V1`  
**Generated At**: `2026-09-09T23:21:46.024Z`  
**Analysis Mode**: Multi-Repository Archaeology & Differential Audit

---

## 1. Production Source Inventory & Checksums

| Area | Relative Path | Lines | Size (Bytes) | SHA-256 Checksum |
|---|---|---|---|---|
| supervisor | `supervisor/index.js` | 77 | 2692 | `2ace305a58f03695...` |
| supervisor | `supervisor/decision_engine.js` | 79 | 2578 | `ab42069fd4c5a613...` |
| supervisor | `supervisor/lease_manager.js` | 232 | 7077 | `c6bb08fe79fbdd0c...` |
| supervisor | `supervisor/no_stacking.js` | 65 | 2208 | `27bc27a3f06866a8...` |
| supervisor | `supervisor/reconciliation.js` | 153 | 5880 | `6f65fdf1958ad956...` |
| supervisor | `supervisor/task_hygiene.js` | 120 | 3711 | `2a97867b762b3499...` |
| supervisor | `supervisor/stall_policy.js` | 181 | 7222 | `70dd2334d86364a8...` |
| money_factory | `money_factory/index.js` | 87 | 2739 | `c1dffb9cf20ee8af...` |
| money_factory | `money_factory/safety_gates.js` | 159 | 5244 | `c00ed53b4f0f1fd4...` |
| money_factory | `money_factory/anti_loop_policy.js` | 204 | 6823 | `6770e9d066cb8503...` |
| money_factory | `money_factory/portfolios.js` | 157 | 5206 | `96894faf4557857e...` |
| money_factory | `money_factory/cheapest_test.js` | 85 | 3545 | `2e27dc9083e8d5e2...` |
| chief | `chief/control_plane.py` | 606 | 26009 | `1a34fe44e8d81565...` |
| chief | `chief/coordinator.py` | 257 | 10055 | `bb755d93faa564e6...` |
| chief | `chief/validator.py` | 89 | 3717 | `5528dee7820fd783...` |

---

## 2. Historical Baselines Examined (Read-Only)

1. **RC3 Baseline**: `COURIER_HANDOFF_RC3` (SHA-256: `739fe3d8...`) - Frozen release candidate.
2. **V2 Lab**: `scratch/autonomous_deep_engineering_v2` - Core dispatcher contracts.
3. **V3 Certification**: `scratch/integration_certification_factory_v3` - 498 unit & integration suites.
4. **Final 4% Intervention**: `scratch/final_4pct_adversarial_intervention_v1` - Isolation of A01, L01, G01, B01.
5. **Nightshift Factory V5**: `scratch/nightshift_adversarial_factory_v5` - 130 adversarial tests & counterexamples.
6. **Red-Team Pack V1**: `scratch/final_integration_redteam_pack_v1` - Candidate validation harness.
7. **Overnight Portfolio V1**: `scratch/autonomous_overnight_portfolio_v1` - Baseline long-run soak.
8. **Deep Build Proof Factory V2**: `scratch/autonomous_deep_build_proof_factory_v2` - 12 packages verified, 166 tests passed, 36 mutants killed.

---

## 3. Verified Production Weaknesses Identified

1. **Dispatcher Fallback Risk**: `supervisor/reconciliation.js` invokes task reroutes without verifying if the original worker is still executing.
2. **No-Stacking String Equality**: `supervisor/no_stacking.js` relies on exact string match of workspace paths. Fails on case differences and directory containment.
3. **Financial Safety Blindspot**: `money_factory/safety_gates.js` only inspects single-shot payment values; zero-cost auto-renewing subscriptions pass unchecked.
4. **PID Liveness Assumption**: `supervisor/lease_manager.js` calls `process.kill(pid, 0)` which treats recycled PIDs as valid owners.
