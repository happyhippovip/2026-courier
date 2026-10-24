# V7 GOAL-01…08 → fertige O7-Rot-Tests · FENSTER O · 24.10.2026

Für FENSTER 1 (Writer) und FENSTER 2 (VERIFY). Die Testnamen aus V7 sind Vorschläge („echter Name kommt in DONE.md“). Die O7-Dateien sind auf `81bbf224` geprüft und rot (strict xfail). Sie liegen in `ERGEBNISSE/` und im ZIP `FENSTER7_ERGEBNISSE.zip`.

| Goal | V7-Testname | O7-Datei = fertiger Rot-Test | wird grün, wenn | Hinweis |
|---|---|---|---|---|
| GOAL-01 B1 | `test_b1_missing_cost_blocks` | `O7-01_test_queue_feed_missing_cost.py`, `O7-02_test_missing_estimate_not_zero.py` | kein Claim/kein PowerShell-Start ohne endliche Schätzung | Bridge und Controller blocken schon (Schutztests grün). Offen: Queue (`queue_feed.py:136-142`) und Windows-Daemon (`daemon.py:359-361`) |
| GOAL-02 B2 | `test_b2_second_writer_rejected` | `O7-03_test_two_writers_work_queue.py`, `O7-04_test_writer_lease_without_owner.py` | gleicher Holder auf anderem Host abgewiesen; Lease ohne `holder_ok` abgewiesen | `work_queue.py:101-103`, `lease.py:125-170` |
| GOAL-03 B3 | `test_b3_done_requires_result_accepted` | `O7-12_test_finish_without_proof.py`, `O7-05_test_done_without_journal.py`, `O7-06_test_done_without_result_accepted.py` | kein DONE ohne `journal:<seq>:RESULT_ACCEPTED` | **Achtung:** #836 macht nur O7-12 grün (Signalpfad). Der direkte `Kirby.on_turn_end("DONE")` bleibt offen (Probe `R-154_probe_direct_on_turn_end.py`) |
| GOAL-04 B4 | `test_b4_abc_bytes_sha256_per_hop` | `O7-07_test_hop_b_without_sha256.py`, `O7-08_test_bytes_changed_after_post.py` | Controller lehnt Inputs ohne sha256 ab; vor FINAL erneuter Byte-Abgleich | O7-08 startet echten Controller + Worker (~2 s, lokal) |
| GOAL-05 B5 | `test_b5_replay_rejected` | `O7-10_test_restart_replays_done_job.py`, `O7-09_test_same_task_id_twice.py` | kein zweiter `gh workflow run` nach Grace; Overlay öffnet erledigten Task nicht neu | Vorhandener Baustein: V37 `codex/v37-task-replay-fail-closed` `a7abf74e` (4 Replay-Negativtests, nicht im Trunk, R-152) |
| GOAL-06 B6 | `test_b6_wake_outside_lock` | `O7-11_test_wake_callback_outside_lock.py` | grün auf Basis; **rot auf #836-Head** `ad50f362a` | Bedeutet: Wer #836 übernimmt, muss den Fix `REV836_wake_callback_outside_lock.diff` mitnehmen |
| GOAL-07 G1 | `test_g1_admission_passthrough` | `O7-13_test_feed_drops_pr_context.py` | Feed reicht `done_prs`/`open_pr_files` durch | Basis-Zeilen `queue_feed.py:77/137/139`; V7-Zeilen 90/179/203 gelten für WQ-1b v2 |
| GOAL-08 G2 | `test_g2_rejected_without_status_parks` | `O7-15_test_bridge_reposts_rejected_forever.py`, dann `O7-14_test_feed_renews_rejected_forever.py` | 1 POST + BLOCKED-Stempel; danach Park im Feed | Reihenfolge: Bridge zuerst |
| (W14) | – | `O7-16_test_result_without_ack_not_delivered.py` | DELIVERED nur mit ACK-Body | nicht in GOAL-01…10, P1 |

**Für GOAL-09 (LEDGER_DONE-Checkliste):** Alle Zeilen oben müssen XPASS sein, die Marker sind dann entfernt. Gesamtlauf auf Basis: `18 passed, 26 xfailed`.

**Zusatz außerhalb B1–B8 (P1-Anzeige):** `courier_hub/static/kolibri_universe.mjs:46,137-138` zeigt VERIFIED ohne Beweis. Fix `TITAN_TRUTH_FIX_V1.diff` (sha256 `d6c7bdff…`) passt noch (R-146).
sha256: c0cc0f0380210b7d3aac9874cd3b98df0c670a9f3aff9e08f5fdab0356e1a02d
