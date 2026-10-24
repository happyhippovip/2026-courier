# O7 → LF Querverweis · FENSTER O (Claude Opus) · 24.10.2026

Hilfsdatei für die LF-Besitzer und für FENSTER 1. **Keine** LF-Datei übernommen: Die Besitzer bleiben wie in V4. Jede Zeile nennt einen fertigen, auf `81bbf224` geprüften strict-xfail-Test aus `ERGEBNISSE/`. Er kann als ROT-Test direkt dienen: auf der Basis rot (xfailed), nach dem Fix XPASS, dann Marker entfernen.

| LF | Block | Besitzer (V4) | fertiger Rot-Test (ERGEBNISSE) | Rot-Kriterium auf 81bbf224 | Anmerkung |
|---|---|---|---|---|---|
| LF-01/02 | B7/G1 | G1 / G2 | `O7-13_test_feed_drops_pr_context.py` | Feed claimt WK1 trotz offener PR; PR-abhängiges WK2 wird nie gefüttert | Basis-Zeilen `queue_feed.py:77/137/139`; Katalog-Zeilen 90/179/203 gelten für WQ-1b v2 `a2a6dfabd`. Der Test nimmt Config-Felder `done_prs`/`open_pr_files` an |
| LF-03/04 | B8/G2 | G3 / GA | `O7-14_test_feed_renews_rejected_forever.py` + `O7-15_test_bridge_reposts_rejected_forever.py` | 3 Durchläufe ergeben 3 POSTs; WK1 bleibt CLAIMED | Reihenfolge: zuerst der Bridge-BLOCKED-Stempel (O7-15), dann `park` (WQ-1b v2) |
| LF-05/06 | B1 | G4 / G5 | `O7-01_test_queue_feed_missing_cost.py`, `O7-02_test_missing_estimate_not_zero.py` | Spec ohne Schätzung blockiert die Queue; Windows-Daemon setzt None → 0.0 | Schutz: Die Bridge postet nichts ohne Schätzung (passed). O7-02 `included_quota` wird durch WIN-COST-1 v3 grün |
| LF-07/08 | B2 | G6 / G7 | `O7-03_test_two_writers_work_queue.py`, `O7-04_test_writer_lease_without_owner.py` | gleicher Holder auf 2 Hosts = 2 Writer; Lease für Holder `""`/`None`/`True`/`0` | `holder_ok` existiert (`lease.py:73-75`), wird aber in `acquire` nicht aufgerufen |
| LF-09/10 | B3 | G8 / G9 | `O7-05_test_done_without_journal.py`, `O7-06_test_done_without_result_accepted.py`, `O7-12_test_finish_without_proof.py` | Freigabe ohne Journal-FINAL; pending-ID als accepted; Provider-DONE ohne Proof | O7-12 ist P1: `continuity.py:225-230` |
| LF-11/12 | B4 | G10 / W1 | `O7-07_test_hop_b_without_sha256.py`, `O7-08_test_bytes_changed_after_post.py` | Controller nimmt Hop B ohne sha256 (201); FINAL über veränderte Bytes | O7-08 braucht echten Controller + Worker (ein lokaler Heavy-Job, ~2 s) |
| LF-13/14 | B5 | W2 / W3 | `O7-09_test_same_task_id_twice.py`, `O7-10_test_restart_replays_done_job.py` | Overlay öffnet erledigten Task wieder; Neustart nach 300 s dispatcht erneut | O7-10 ist P1 (`intake_dispatcher.py:269-283`) |
| LF-15/16 | B6 | G1 / G2 | `O7-11_test_wake_callback_outside_lock.py` (kein xfail), `O7-12_test_finish_without_proof.py` | O7-11: auf Basis grün, auf #836-Head `ad50f362a` rot | Wake-im-Lock gibt es **nur** in PR #836; Fix-Diff `REV836_wake_callback_outside_lock.diff` (sha256 `2807873e…`) |
| (W14) | – | – | `O7-16_test_result_without_ack_not_delivered.py` | 2xx ohne ACK-Body = DELIVERED | P1; W14-Patch nicht angewendet |

Gesamtlauf aller O7-Tests auf der Basis: `18 passed, 26 xfailed`, Exit 0 (siehe `O7-17_ERGEBNIS.md`).

## Für FENSTER 1 (B1→B6)
Pro Block die Testdatei als `tests/test_o7_xx_<name>.py` übernehmen und rot bestätigen, dann den Fix. Grün bedeutet XPASS, dann den Marker entfernen und den Test als Regressionstest behalten. Kein Test braucht Netz oder einen Provider.
sha256: 72ada19bfbd0ed26879b50cf0279188e6d8f961e42389367a9dc4f84b8dae8df
