# Baseline vs. Patch – 29.10.2026 (nur bestehende Logs ausgewertet, kein neuer Lauf) · Stand 19:10 MEZ
Umgebung /tmp/l01: run.sh mit unshare --net, env -i, Python 3.13.5, pytest 9.1.1, `python3 -m pytest -p no:cacheprovider <args>`
Basis: integration/v1 @26ee23485952e61f6f2ad3da24176d6bbac82a63 · Patch: LUECKE_01.diff (Gate L01, Integration)

| Lauf | Commit/Tree | Exit | passed | failed | errors | Log sha256 |
|---|---|---|---|---|---|---|
| base_controller (tests/controller) | 26ee2348 | 0 | 218 (1 skip) | 0 | 0 | 34fa48ca…0c9c |
| patch_controller | 26ee2348+L01 | 0 | 231 (1 skip) | 0 | 0 | ffa27f3e…7774 |
| patch_gate_v (Gate-Tests) | 26ee2348+L01 | 0 | 13 | 0 | 0 | /tmp/l01/logs/patch_gate_v.log |
| base_full (Vollsuite) | 26ee2348 | 1 | 4017 (16 skip) | 2 | 0 | /tmp/l01/logs/base_full.log (18:46) |
| patch_full (Vollsuite) | 26ee2348+L01 | 1 | 3978 (16 skip) | 48 | 6 | 0c867349…079e |
| PYTEST_0060_a209b3fe | a209b3fe (PR 2) | 1 (Block tests/hub 15 failed/128 passed) | – | – | – | 6a7945c3…8df4 |
| PYTEST_0060_9afe8706 | 9afe8706 (PR 2+2b) | 1 (Block tests/hub 3 failed/145 passed) | – | – | – | 64478c4d…a59c |
| BASELINE_26ee2348_3tests | 26ee2348 | 1 | 2 | 1 (kolibri_view) | 0 | 13b1c967…c843 |
| INTEGRATIONSTEST (WK-INTEGRATOR-006) | 481eabda = 9afe8706+CP1–CP5 | 1 | 295 | 2 (test_hub_product) | 0 | a245d8ae…8581 |

Baseline-Fehler (beide auch im Patch): tests/hub/test_kolibri_view.py::test_github_payload_is_shown_and_a_failed_read_is_unknown · tests/test_serve.py::test_main_arg_parser_validation
NEU durch Patch L01: 52 Fehler-IDs (46 failed + 6 errors). Schwerpunkte: test_ledger_engine 22, test_continuity_demo 6 ERROR, test_mission_chip 4, test_task_dependency_input 3, test_serve +2, test_ledger_bridge_verified_inputs 3, test_ledger_chain_abcd_restart 2, test_courier_mailbox 2.
Top-Ursachen: 35× `ApiError: task has no confirmed goal contract that accepts it` (das Gate lehnt bestehende Abläufe ohne bestätigten Goal-Contract ab, Fixtures sind nicht angepasst) · 8× pytest-timeout >60 s · 4× Bridge-Subprocess Exit 2 (rejected).
0060: „3 passed, EXIT 0“ ist nur der letzte Block. Beide Gesamtläufe sind ROT (Symphony PYTEST_0060_CHECK.md bestätigt das).
URTEIL: Gate-Patch L01 und Folgepatch 009 BLOCKED/HOLD (nicht freigabereif). 0060 ROT. Kein Push, kein Merge.
