# O7-17 · Gesamtliste aller O7-Tests · Claude Opus (FENSTER 7)

Basis `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a`. **Gesamtlauf** aller 16 Testdateien zusammen in `tests/` der Basis: `18 passed, 26 xfailed in 3.94s`, Exit 0 (kein XPASS, kein Fehler). Kosten 0 €. Nichts committet, gepusht oder als PR geöffnet.

| ID | Block | Testdatei | sha256 Testdatei | sha256 Ergebnisdatei (Siegel) | Ergebnis auf Basis / Priorität |
|---|---|---|---|---|---|
| O7-01 | B1 | `O7-01_test_queue_feed_missing_cost.py` | `d61a8d9f4b81a5c2ffe58b2ed401577956f0e8fc0dd2a235ba411cb8c8bbe63a` | `ca363d903c735bc52b7019ee38398901fcd4f500d1e06de11671870cc04d7e7f` | 1 xfailed · Queue-Stillstand durch Spec ohne Schätzung · P2 |
| O7-02 | B1 | `O7-02_test_missing_estimate_not_zero.py` | `52596654e8daa40d52bc4e63bfe3554d3aeb42dda91f23aa89523da7845929c2` | `8366b43c679f22e6407394ee14595e17e9325776293f882cbbb78be4c094a0eb` | 2 passed, 3 xfailed · Windows-Daemon setzt None→0.0 · P1 (included_quota durch WIN-COST-1 v3 behoben; free/local Policy) |
| O7-03 | B2 | `O7-03_test_two_writers_work_queue.py` | `c6773a9f03f0f0696b4e15c57da6c0c01d28383d1c345cf3ee9ab18b871d1ff8` | `3105a67fcb80a8fcb1a505ccc30e98fa423462765939a64197fa445c81851dc2` | 1 passed, 1 xfailed · gleicher Holder auf 2 Hosts = 2 Writer · P2 |
| O7-04 | B2 | `O7-04_test_writer_lease_without_owner.py` | `fb08296f582a33c5ed2b75d01ee89d03903f5f83e9e4ccd209be328fd120918e` | `fd9f5f7b088e1275fe35beac7251c8e959e757b969f6970caf90f76d8bd276dc` | 2 passed, 5 xfailed · LeaseStore ohne Besitzer-ID · P1 |
| O7-05 | B3 | `O7-05_test_done_without_journal.py` | `ebbacd01595b5c047bf8dba0318fb64e3dea6dd16664d4190c173f4f595c2176` | `2b784bca161e53d318ecf2aba33e5463265b19bfd280992daa63e0a58f86a937` | 1 xfailed · Feed gibt DONE ohne Journal-FINAL frei · P2 |
| O7-06 | B3 | `O7-06_test_done_without_result_accepted.py` | `b48272ff7103e5cdc8b0a22bae79be8750991f435800f0bf95f51029f2f42f66` | `b93e1c47f8ddd87132660ea8fe9bb8002f97660d1bb8c10ff04d97437d134f3d` | 1 passed, 1 xfailed · pending-ID als accepted_result_id · P2 |
| O7-07 | B4 | `O7-07_test_hop_b_without_sha256.py` | `4d9ab19fb5f964cf89e3712e5a44e9add2f3f095361754380aa9465d82609a0e` | `aeacaf33031bfa52a6d33b1679daa675b16347885f881821c78c4111f7c9a403` | 3 passed, 3 xfailed · Controller nimmt Hop B ohne sha256 · P2 |
| O7-08 | B4 | `O7-08_test_bytes_changed_after_post.py` | `a138c38e80762d73b633275c4f56641b56b271ee487aa1ccfb5aed2f51e6c2a7` | `169f96bcdb2708a0a4208dffdcc2ee0690dd4330297b3562dad6d3142c432b5f` | 1 xfailed · TOCTOU: FINAL über veränderte Bytes · P2 |
| O7-09 | B5 | `O7-09_test_same_task_id_twice.py` | `80ca3ffc249e95949d40f5b42069b22c450477dfb071ac3405028946042677f4` | `f6add02e90f9c659148bd2c8ce137d9ad52214b55876cfe2465611805a219c1e` | 1 passed, 1 xfailed · Overlay öffnet erledigten Task bei Duplikat · P2 |
| O7-10 | B5 | `O7-10_test_restart_replays_done_job.py` | `6d482d93eb50c79b769c97d092aa7d6251e68ae955e2aefe035f1ef50cd938d8` | `ed643c0bd2222450fcd4b019cb77452eeeb4d9e983a31ba716e2081c2e2ec034` | 1 passed, 1 xfailed · Neustart nach Grace dispatcht erneut · P1 |
| O7-11 | B6 | `O7-11_test_wake_callback_outside_lock.py` | `9fe84df8b80ed0182749e377093d34fce529a3992a9122176d7a151fda468598` | `33306c6d436033077df59f1a41f75fef688ccaa123025c6f31f7c455e7ee9dcc` | 1 passed (kein xfail: auf Basis nicht vorhanden; rot auf #836-Head ad50f362a) · Regressionstest |
| O7-12 | B6 | `O7-12_test_finish_without_proof.py` | `c3b443ee4074f70e1322e972d2319012b5e24c124291ab37717bc1fdab6ebec8` | `d147982128de14ab21fa8ae108531466105f8a07413c5d1892dca8fba56f06ef` | 1 passed, 1 xfailed · Provider-DONE-Signal ohne Proof · P1 |
| O7-13 | G1 | `O7-13_test_feed_drops_pr_context.py` | `caac57b297bf1191a04bc5ded5ddb8487ccbc937d6ed7c06401ca1bf32a5e693` | `9254ffb96406734d96421614e8b700571c5b2ef13eed80dd648681f26851b128` | 1 passed, 2 xfailed (auch auf WQ-1b v2) · done_prs/open_pr_files fehlen · P2 |
| O7-14 | G2 | `O7-14_test_feed_renews_rejected_forever.py` | `d1d03b1c67339924e9cc74f5dacbf94e3f85ab3ec87c7b234d694893279c8290` | `a9394e3e5d93cd9f002563a844724c4e82354a5f199f120baccc3786f4c65e8d` | 1 xfailed (auch auf WQ-1b v2) · Feed erneuert abgelehnte Mission endlos · P1 (mit #846) |
| O7-15 | G2 | `O7-15_test_bridge_reposts_rejected_forever.py` | `bd631aefd48e86ccc7c8a9c390ad708a9bbfad2e951118fb0ed25a9bbf372881` | `7a0921abee8bb68e3502f469f1a0970e0385f977898edb41641fc9ae40d69686` | 1 passed, 1 xfailed (auch auf WQ-1b v2) · Bridge postet abgelehnte Mission endlos = R1 · P1 |
| O7-16 | W14 | `O7-16_test_result_without_ack_not_delivered.py` | `5c8f1e45168d983f17ebc997db76536bc22616053f1dc39943a2524631dbca47` | `d2db36953eaa6fe4edd6058f2ae91c7d058e2ebf41e9b4095e48252d0881a4c6` | 3 passed, 3 xfailed · 2xx ohne ACK = DELIVERED, Ergebnis gelöscht · P1 |

## Hinweise für FENSTER 1 (C1-17)
- Einbau: Datei nach `tests/` kopieren (Dateiname mit `-` ist bei expliziter Angabe sammelbar; für die Dauer im Repo besser `test_o7_xx_*.py` nennen).
- Alle xfail sind `strict=True, raises=AssertionError`. Ein Fix macht den Test XPASS, also rot. Dann den Marker entfernen; die Assertion bleibt als Regressionstest.
- Abhängigkeiten: O7-14 wird erst nach dem R1-Fix (O7-15) **und** dem `park` aus WQ-1b v2 grün. O7-02 `included_quota` wird mit WIN-COST-1 v3 grün; `free`/`local` brauchen eine Policy-Entscheidung. O7-11 gehört zu #836.
- Siegel: Die letzte Zeile jeder Ergebnisdatei ist `sha256` über alle Bytes davor (`head -n -1 X | sha256sum`).
sha256: 2ef699e4b7b43b44c5c50707cc268227748142f2cbeeace932649c40b7c5f4ab
