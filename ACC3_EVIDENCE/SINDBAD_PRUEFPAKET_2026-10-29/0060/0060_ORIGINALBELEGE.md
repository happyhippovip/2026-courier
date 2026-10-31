# 0060 – ORIGINALBELEGE · 29.10.2026 19:35 MEZ · Krieger (Acc1), nur gelesen, kein neuer Test, kein Push
Originale liegen unter /workspace/GrokBot/WORKKEYS/ERGEBNISSE/INTEGRATOR/ auf der Box von Acc1.
Wrapper: Jeder Block wird im Log mit `### HH:MM:SS [tree] <befehl>` begonnen und mit `### EXIT n HH:MM:SS` abgeschlossen. Das sind die echten pytest-Exit-Codes je Block, so wie das Wrapper-Skript sie protokolliert hat. Einen Gesamt-Exit-Code für den ganzen Prozess gibt es in keinem Log → UNKNOWN.
Befehl je Block: `python3 -m pytest -rA -p no:cacheprovider --timeout=300 <ziel>` · Python 3.13.5 · pytest 9.1.1

## LAUF A · WK-PRUEFER-012 / WK-INTEGRATOR-012 (RC-0060) · Tree a209b3fec444cc3af7d02f153c696d57991ae9d0 (26ee2348 + EC1→E0→E0b→E0-Tests→E0v2→EC1v2)
Log PYTEST_0060_a209b3fe.log · sha256 6a7945c372abd6ba0ae4d9ce38430dc8264f3991b26e3c02484f535e78478df4 · Start 18:50:32, Ende 18:52:34 MEZ
- tests/hub (Z.1150–1151): `======================= 15 failed, 128 passed in 23.15s ========================` · `### EXIT 1 18:52:14`
- tests/test_gate2_two_workkeys.py (Z.1463–1464): `============================== 3 passed in 10.82s ==============================` · `### EXIT 0 18:52:34`
- übrige Blöcke EXIT 0: ledger_v1_bridge 40, controller 220+1 skip, test_serve 24, task_dependency_input 23, mission_chip 10, local_bind_loopback 5, work_queue 21, queue_feed_pr_evidence 7, windows_local_queue 15, queue_feed_corrupt_default 2, work_queue_windows_lock 1, runtime_continuity 46 · MISSING_IN_TREE: test_p2b_journal_proof.py, controller/test_ctrl_p2b_accepted_seq.py, test_o7_04_lease_owner_required.py
- 15 FAILED (Z.1135–1149): tests/hub/test_hub_product.py::{test_blocked_effect_confirmed_through_the_hub, test_duplicate_click_is_recorded_once, test_a_stale_screen_cannot_decide_a_newer_question, test_stop_after_uncertain_effect_stays_uncertain, test_working_card_shows_observable_state_authority_and_stop, test_lost_answer_after_the_controller_recorded_is_never_reported_as_nothing_changed, test_retry_authorized_twice_gives_exactly_one_new_attempt, test_two_tabs_with_different_decisions_only_the_first_counts, test_stop_after_a_non_idempotent_action_started_never_reads_as_nothing_happened, test_stop_before_start_is_a_plain_stop, test_stop_after_completion_is_stale_not_success, test_unknown_or_malformed_task_ids_are_not_found, test_a_recorded_decision_is_never_reported_as_failed_when_the_reread_breaks, test_an_internal_error_after_relaying_never_claims_nothing_changed} + tests/hub/test_kolibri_view.py::test_github_payload_is_shown_and_a_failed_read_is_unknown

## LAUF B · gleicher Workkey · Tree 9afe8706ee94bbd554efdbff5dc4666a0bf19f64 (= A + PR-2b-Patch)
Log PYTEST_0060_9afe8706.log · sha256 64478c4d6320cebfdaa10fb78a7d9bfde044d4a93c19e52246a663c9366ee59c · Start 18:52:34, Ende 18:54:45 MEZ
- tests/hub (Z.975–976): `======================== 3 failed, 145 passed in 27.66s ========================` · `### EXIT 1 18:54:24`
- tests/test_gate2_two_workkeys.py (Z.1288–1289): `============================== 3 passed in 11.03s ==============================` · `### EXIT 0 18:54:45`
- übrige Blöcke EXIT 0, Zahlen wie in Lauf A (controller 220+1 skip)
- 3 FAILED (Z.972–974): tests/hub/test_hub_product.py::test_lost_answer_after_the_controller_recorded_is_never_reported_as_nothing_changed · tests/hub/test_hub_product.py::test_controller_not_running_means_nothing_was_sent · tests/hub/test_kolibri_view.py::test_github_payload_is_shown_and_a_failed_read_is_unknown (rot auch auf Base 26ee2348: BASELINE_26ee2348_3tests.log 13b1c967d7a6b3b3c9c4db778914a65252f886d48e64e9e0a0dfb3407d72c843)

## Weitere Belege
- PYTEST_0060.log (Integrator-Zusammenfassung) 7d626827b23221d6546a53df51d805f8aa775e76bce66cfff3663be781738581
- SHA256SUMS_012.txt (Integrator) listet beide Logs mit identischen Hashes → stimmt
- Symphony PYTEST_0060_CHECK.md: nennt 15 failed (a209b3fe) und 3 failed (9afe8706), Urteil ROT → stimmt mit den Originalen überein
- Prüfer INTEGRATOR_0060.md sha256 ecd3df47d879b5ff27169357b457d6419980f1669577602e3ed57527e3d73bba: Hashes der Logs stimmen. Achtung: Der Titel lautet „VERIFIED (3+3 passed)“, das gilt aber nur für gate2. Der Hinweis im Text nennt die roten hub-Blöcke. Als Gesamturteil ist der Titel irreführend.

## Secret-Muster
Die früheren Treffer für „sk-“ in beiden Logs sind Teilstrings von Test-Task-IDs („task-<hex>“, „task-does-…“, „task-x…“) aus pytest-Fixtures. Kategorie: TEST-FIXTURE / FALSCH-POSITIV. Weder token=, api_key= noch Bearer kommen mit Wert vor.
Bereinigung: Die Redaktionsregel (token/secret/password/api_key/authorization/bearer=Wert, ghp_, xox, AKIA) hat 0 Treffer → die bereinigten Kopien sind byte-gleich mit den Originalen. Nachscan sauber.

## Urteil
Die gemeldeten 3 und 15 failed stehen wörtlich in den Originallogs. 0060 = ROT (je ein hub-Block EXIT 1 in beiden Läufen). Gate2 allein 3 passed, EXIT 0, ist aber kein Gesamt-PASS. Gesamt-Prozess-Exit: UNKNOWN.
ZUSTELLUNG an Sindbad (Acc3): ACCESS_BLOCKED. Das Paket liegt nur lokal; Push nach happyhippovip/2026-project-memory braucht Dennis' GO (HOLD_PUSH).
