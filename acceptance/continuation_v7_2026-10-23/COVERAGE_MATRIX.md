# Abdeckung CLD-101…120 (keine Duplikate; Verweise auf vorhandene, ausgeführte Tests)
| Workkey | Status | Beleg |
|---|---|---|
| CLD-101 | PASS | #830 `8c4858692` Draft, 7/7 CI success, mergeable clean; trunk unverändert `d5b19f1` |
| CLD-102 | PASS | F-C1 v2 und WQ-1 wenden sich weiter sauber auf trunk an (`git apply --check`) |
| CLD-103 | PASS | `evidence/F-C1_red_green.log` (gegen v1: 16 failed → v2: 44 passed), `evidence/WQ-1_red_green.log` (2 failed → 3 passed) |
| CLD-104 | PASS | `test_the_shipped_adapters_declare_their_cost_class`: synthetic/local_json_delivery/spreadsheet = local, local_shell/provider_exec = metered; unknown_cost/cost_class-Varianten: `test_an_explicit_unknown_marker_is_refused_for_every_adapter` (6 Varianten × 3 Adapter) |
| CLD-105 | PASS | `test_local_shell_can_run_any_cli_so_it_needs_an_estimate` (rot gegen v1) |
| CLD-106 | siehe Subagent-Inventur (Abschnitt im Schlussbericht) | Controller-Pfad abgedeckt durch F-C1; Pfade außerhalb des Controllers: Inventur |
| CLD-107 | PASS (Analyse) | `run_antigravity_bridge.build_local_shell_task_packet` hat keinen produktiven Aufrufer, der an den Controller postet (nur 2 Tests, direkt `local_shell.run`); Skript startet keinen Provider-Prozess → heute keine Wirkung; Übergabe H6 |
| CLD-108/109 | PASS | `l2_build_2026-10-23/WQ-1_*`: zwei Homes, alter Lease, neuer Owner, Doppel-Zuweisung reproduziert; Fix verhindert Übernahme, ursprünglicher Holder setzt fort |
| CLD-110 | DESIGN | `WQ-1b_LEASE_RECOVERY_DESIGN.md`: ATTACH + Abgleich per GET + Mensch-`reclaim` mit Actor/Grund; 8 Negativtests spezifiziert |
| CLD-111 | PASS | 82 Queue/Feed/LedgerTick-Tests inkl. `test_work_queue.py` und `test_gate2_two_workkeys` grün mit WQ-1 (WorkQueue-Semantik unverändert, nur Feed-Entscheidung + additives Feld) |
| CLD-112 | PASS | Engine nutzt Controller nur lesend + `create_task`; mit F-C1: `test_direct_controller_create_task_is_cost_gated_too` (Folge-Patch H3), 47 passed |
| CLD-113 | vorhanden | `tests/test_ledger_engine.py`: `test_provider_says_done_but_nothing_is_verified_stays_claimed`, `test_human_confirmed_effect_is_not_proof`, `test_a_verified_task_of_another_workkey_cannot_finish_this_workkey`; Bridge (#827): `test_complete_without_accepted_result_is_not_final`, `test_accepted_result_with_non_verified_resolution_is_not_final` |
| CLD-114 | vorhanden | Engine: `test_a_second_finish_after_final_is_rejected_and_writes_no_second_receipt`; Bridge: `test_changed_result_does_not_write_a_second_final`, `test_restart_on_complete_task_writes_one_final_and_no_post`; Controller-Probe `cld019` |
| CLD-115 | vorhanden | Controller-Probe `cld007/cld009`; Engine `test_two_processes_never_claim_the_same_workkey`, `test_a_held_campaign_lock_makes_another_process_wait`; F-C1 `test_replay_of_an_admitted_task_is_a_duplicate_and_writes_nothing` |
| CLD-116 | vorhanden | Controller-Proben `cld018` (Restart in VERIFYING), `cld006`; Engine `test_crash_after_verifier_acceptance_completes_on_restart` |
| CLD-117 | PASS (Analyse) | ACR: vier Claim-Speicher; Vorschlag eine Wahrheit `work_queue`, Journal bleibt Ausführungswahrheit; ATTACH/RECLAIM in WQ-1b sind keine zweite Ledger-Wahrheit |
| CLD-118 | PASS | `OWNER_HANDOFFS_2026-10-23.md` (H1–H11, exakte Dateien) |
| CLD-119/120 | PASS | dieser Commit + Memory-Abschnitt 14 |
