# A→B→C Integrationsprüfung · 23.10.2026 · Claude Opus (Integrationsarchitekt, nur lesend)

Status-Wörter: VERIFIED (selbst ausgeführt) · REPORTED (aus PR/CI) · UNKNOWN · BLOCKED. Keine Datei eines fremden Owners geändert; alle Merges nur lokal im Wegwerf-Worktree.

## 1. Geprüfte HEADs (abgerufen 23.10. ~10:40 UTC)
| PR | Branch @ Head | Basis | Owner | CI auf Head |
|---|---|---|---|---|
| — | `integration/v1` @ `d5b19f1df` | — | L1 | — |
| #826 A→B-Grundpfad | `cursor/ab-master-9ba8` @ `7686b97f6` (345 Dateien) | integration/v1 | Cursor Mac | **ROT**: pytest windows, 4 neue Fehler (3 Sammelfehler `test_muse_wall_symlink`, `test_muse_bool_target`, `test_muse_bool_metrics`; `test_ingest_docs::test_main_writes_a_local_chunk`) |
| #827 Receipt/A→B→C | `cursor/ab-receipt-verdict-f7a0` @ `4a136b88f` | **#826-Branch** (gestapelt) | Cursor Mac | nur Acceptance grün; **v1-CI (pytest/golden/windows) lief nie**, weil die Basis nicht `integration/v1` ist |
| #830 Ledger-Engine | `claude/ledger-engine-v1` @ `6cdaa170f` | integration/v1 | Claude | 7/7 grün (eigene Arbeit, keine Selbstabnahme) |
| #818 Continuity | `cursor/concurrency-unmeasured-4598` @ `642611465` | integration/v1 | Cursor | 7/7 grün |
| #829 Windows-Lease | `cursor/windows-lock-import-be3a` @ `1bcaf9299` | integration/v1 | Cursor Windows | 7/7 grün |

## 2. Abhängigkeiten, Überschneidungen, Konflikte (VERIFIED, lokaler Merge)
- #827 ⊃ #826 (gestapelt). **#827 enthält genau die Dateien, an denen #826 auf Windows scheitert** (`ingest_docs.py`, drei Muse-Tests) → #826 ist allein nicht grün; #826+#827 sind eine Einheit.
- Dateiüberschneidung #826∩#827: `artifact_receipt.py`, `courier_mailbox.py`, `ingest_docs.py`, `ledger_v1_bridge.py` (Stack, erwartbar).
- **#827 ∩ #829: `scripts/windows_worker/daemon.py`, `tests/test_windows_lock_fail_closed.py` → Merge-KONFLIKT** (2 Hunks daemon, 1 Hunk Test). Kein Duplikat: #827 verlegt das Windows-Byte-Lock hinter den PID-Eintrag; #829 macht den Daemon fail-closed (kein Default-Server, kein Lauf ohne kanonischen Lease).
- **Semantischer Konflikt (reproduziert):** Vereinigung beider Seiten → `test_windows_lock_does_not_cover_the_pid_record` (#827) **FAILED** mit `CanonicalLeaseLost`, weil der Test `get_authority_store` auf `None` setzt und #829 genau das jetzt verbietet. Einzeln sind beide grün.
- **Vorschlag (lokal geprüft):** Vereinigung + in diesem einen Test die Zeile `monkeypatch.setattr(daemon, "get_authority_store", lambda: None)` entfernen (der echte LeaseStore im Temp-Verzeichnis greift). Ergebnis: 48 passed, 1 skipped über alle Daemon-/Lock-/Lease-Tests. Patch: `INT_827_829_UNION_PROPOSAL.diff`. Entscheidung und Umsetzung: Owner #827 (Cursor Mac) + #829 (Cursor Windows), nur einer schreibt.
- #830, #818: konfliktfrei mit allem.

## 3. Kombinierter Stand (Trunk + #826 + #827 + #830 + #818 + #829-Vereinigung + Testfix), VERIFIED
`pytest -q` über 17 A→B→C-relevante Suiten (ab_e2e_gaps, ab_master_*, cross_host_abc_canary, cross_host_handoff, ledger_v1_bridge, ledger_bridge_restart_matrix, ledger_bridge_verified_inputs, ledger_chain_abcd_restart, golden_ledger_bridge_ab, golden_goal_ab_autonomous, courier_mailbox, core/test_artifact_receipt, ledger_engine, runtime_lease, windows_lock_fail_closed, tests/controller): **393 passed, 2 skipped, 2 xfailed** (die zwei bekannten Lücken-Pins aus #830).

## 4. Szenario-Matrix
| Szenario | Status | Beleg |
|---|---|---|
| A wird eindeutig angenommen | VERIFIED | `test_sender_restart_does_not_post_the_mac_mission_twice`, `test_bridge_restart_is_exactly_once`, Controller-FIFO/Claim-once |
| B erhält nur autorisierte, geprüfte Ergebnisse | VERIFIED | `test_chain_abcd_with_restart_reuses_verified_results`, `test_tampered_b_blocks_c`, Controller `_verified_input` |
| C übernimmt erst nach Verifikation | VERIFIED | `test_tampered_b_blocks_c`, `test_complete_a_finalizes_and_posts_b_in_the_same_pass` |
| Falscher Actor / Host → BLOCKED | VERIFIED | `test_wrong_actor_is_not_posted`, `test_wrong_host_is_not_posted` |
| Fehlender Blob → kein PASS | VERIFIED (nur mit #827) | Probe: Blob fehlt / Store unlesbar → `MISSING_DATA`; `test_unreadable_store_and_missing_blob_do_not_pass`. Auf Trunk weiterhin VERIFIED_MATCH (P0 vom 22.10.) |
| Hash-Mismatch → kein PASS | VERIFIED | Probe → `HASH_MISMATCH`; `test_hash_mismatch_does_not_publish_pass` |
| Fehlende Lease → BLOCKED | VERIFIED (nur mit #829) | `test_missing_lease_store_does_not_start`, `test_foreign_lease_does_not_start_the_daemon`, `test_file_lock_without_canonical_lease_exits_3` |
| **Unbekannte Kosten → BLOCKED** | **FAIL auf dem Bridge-Pfad** | siehe 5.1 |
| Absturz zwischen Ausführung und Result | VERIFIED | Controller-Restart-Grace (Abnahme-Probe `cld006`), `test_sender_dies_after_mac_accept_then_replays_without_a_second_task` |
| Replay → keine doppelte Ausführung | VERIFIED | `test_replay_writes_nothing_and_posts_nothing`, `test_restart_on_complete_task_writes_one_final_and_no_post`, Engine-Restart-Tests |
| FINAL nur mit Ergebnis- + Journal-Proof | VERIFIED | Bridge: `test_human_confirmed_effect_is_not_final`, `…without_accepted_result…`, `…non_verified_resolution…`; Engine: `REJECTED_FOREIGN_TASK`, `NOT_PROVEN` |
| Echter Provider | BLOCKED | nicht getestet, kein GO |

## 5. Reproduzierbare Fehler
1. **Bridge dispatcht ohne Kostenentscheidung** (`scripts/ledger_v1_bridge.py` `_dispatch`, #827 Head `4a136b88f`): Spec ohne `estimated_cost_eur` → gepostet; Spec mit `params.unknown_cost: true` → gepostet. Probe `test_probe_bridge_cost.py` (2 passed = Fehler bestätigt). Zusammen mit F-C1 (Controller ohne Kostensperre) erreicht unbekannte Kosten den Worker. Fix (Owner Cursor Mac): `_handoff_cost_block` für jede Spec, fehlende Kosten = UNKNOWN_COST; Testhelfer `_spec()` mit `estimated_cost_eur=0.0`.
2. **#826 allein rot auf Windows** (4 neue Fehler, s. o.). Fix steckt in #827.
3. **#827 ohne v1-CI**: Basis = #826-Branch → pytest/golden/windows nie gelaufen. Fix: #827 in #826 zusammenführen oder auf `integration/v1` umstellen, damit die volle CI auf dem kombinierten Head läuft.
4. **Semantischer Konflikt #827↔#829** (s. 2).
5. Bekannt, unverändert: F-C1 `Controller.create_task` ohne Kostensperre (L2); Host-Loop `TURN_ENDED outcome=DONE` → DONE ohne Beweis, ohne Lock (L3).

## 6. Sichere Integrationsreihenfolge (Vorschlag für L1)
1. **#818** (2 Dateien, unabhängig, grün).
2. **#830** (3 neue Dateien, unabhängig, grün) — nach unabhängiger Abnahme (nicht durch Claude).
3. **#826 + #827 als Einheit**, erst wenn auf dem kombinierten Head die volle v1-CI grün ist (Punkt 5.3) und Fehler 5.1 behoben ist.
4. **#829 zuletzt**, nach Konfliktauflösung gemäß Vorschlag in 2 (ein Writer), mit voller CI.
Begründung: unabhängige, kleine PRs zuerst senken das Risiko; der große Stack braucht seinen eigenen grünen Lauf; #829 hängt textuell und semantisch an #827.

## 7. Offene Owner-/Human-Gates
| Gate | Wer |
|---|---|
| Bridge-Kostensperre für jede Spec (5.1) | Cursor Mac (#827) |
| #827 volle CI / Stack zusammenführen (5.3) | Cursor Mac |
| Konfliktauflösung daemon.py + Testfix (5.4) | Cursor Mac + Cursor Windows (ein Writer) |
| Zentrale Kostensperre im Controller (F-C1) | L2 |
| Host-Loop über Ledger-Engine führen (F-K1/F-K2) | L3 — Owner offen |
| Unabhängige Abnahme #830 | GR57 / GR88, nicht Claude |
| owner_token-Rotation (öffentliches Repo) — P0 | Mensch (Dennis) |
| Merges | L1 nach `MERGE-GO #…` |
| Echter Provider-Lauf | eigenes GO nach allen obigen Gates |
