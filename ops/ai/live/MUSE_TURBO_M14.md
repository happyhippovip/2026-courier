# MUSE TURBO M14 — CROSS_RUN_CONTAMINATION (Post-Codex/RUN-Paket, Codex ausstehend)

ROLE=M14 / SHARD=M14 CROSS_RUN_CONTAMINATION
MODE=READ_ONLY_C2 / LEDGER=FROZEN / 0 Executions / 0 Source-Edits
SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf (origin/candidate-b-1, genommen, nicht revalidiert)
CODEX=ABSENT (ops/ai/live/CODEX_HIGH_RESULT_CURRENT.md fehlt) → Post-Codex/RUN-Paket, keine Aktualisierung an realer Evidence
CLAIM=/tmp/MUSE_M14.claim.json (icy-pulsar, MAC, 2026-09-28)
SOURCE_FILE=scripts/github_worker_adapter.py (alle Zeilen auf SHA)

## S1 stale-state fremder Dispatch
CLAIM=State-Datei eines alten Dispatch kontaminiert keinen neuen Dispatch desselben Task-Files.
SOURCE_TRUTH=adapter.py:32-37 (state_path = task-stem + .github-worker-state.json; write JSON sort_keys), :134-138 (prior geladen; dispatch-Mismatch → ValueError "persisted GitHub state belongs to another dispatch").
FALSE_GREEN_PATH=Alter State mit altem dispatch_id + neuer Task mit neuem dispatch_id → Re-POST alten run_id/result_id als neues Ergebnis.
INDEPENDENT_EVIDENCE=tests/test_github_worker_adapter.py:79 test_existing_waiting_dispatch_is_reconciled_not_dispatched (WAITING-State wird versöhnt, kein Redispatch); server/app.py Dup-Key mit dispatch_id (6-Feld-Key, Q027-Paket).
MINIMUM_FIX_OR_GUARD=keiner (Guard vorhanden). Falls Codex schärfer will: State-Datei pro Dispatch benennen statt pro Task-Stem (entscheidungsgated).
MINIMUM_TEST=negativ: prior dispatch-2 + Task dispatch-1 → ValueError (post-Codex, nicht jetzt).
DISPROVEN_OR_CONFIRMED=CONFIRMED (fail-closed per Code-Read).

## S2 POSTED-Replay kein Doppel-POST
CLAIM=Erneuter Adapter-Lauf nach POSTED postet nicht erneut.
SOURCE_TRUTH=adapter.py:138-139 (prior.status == POSTED → return 0 vor find_run/dispatch/download).
FALSE_GREEN_PATH=Crash nach POST, vor State-Write → Re-POST → Doppel-Execution am Server.
INDEPENDENT_EVIDENCE=tests/:63 test_verified_completed_result_posts_and_records_run_attempt (POSTED-State schreibt run_id/run_attempt/result_id); Server-Dedup ACK_DUPLICATE/409 (app.py task_result).
MINIMUM_FIX_OR_GUARD=keiner. Restlücke (Crash zwischen post_result und write_state) fängt Server-Dedup.
MINIMUM_TEST=POSTED-State → run() == 0 ohne post_result-Aufruf (post-Codex).
DISPROVEN_OR_CONFIRMED=CONFIRMED.

## S3 Download-Verzeichnis + Dateinamen pro Dispatch gebunden
CLAIM=Ergebnisse eines fremden Dispatch landen nicht im Verzeichnis/laufen nicht unter fremdem Namen ein.
SOURCE_TRUTH=adapter.py:158 (directory = .courier-result-{dispatch_id}), :62-68 (download via gh run download courier-result-{dispatch_id}; glob result_{dispatch_id}.json + courier_output_{dispatch_id}.json), :166 (finally: rmtree ignore_errors).
FALSE_GREEN_PATH=Zwei Dispatches teilen sich ein Verzeichnis → result_dispatch-2.json wird als dispatch-1-Ergebnis verifiziert/gepostet.
INDEPENDENT_EVIDENCE=tests/:89 test_dispatch_preserves_taskpacket_as_raw_json (Dispatch-Payload exakt, --raw-field); :82 S1-Bindung result-{dispatch_id} im Test-Paket.
MINIMUM_FIX_OR_GUARD=keiner. Hinweis: rmtree im finally löscht auch bei Verify-Fail (kein Forensik-Verlust am Server, nur lokal).
MINIMUM_TEST=zwei Dispatch-IDs → zwei getrennte Verzeichnisse/Globs (post-Codex).
DISPROVEN_OR_CONFIRMED=CONFIRMED.

## S4 Ergebnis-an-Run-Bindung (falscher Run abgewiesen)
CLAIM=Ergebnis eines fremden GitHub-Runs wird nicht für diesen Dispatch akzeptiert.
SOURCE_TRUTH=adapter.py:80-84 (IDENTITY_FIELDS-Abgleich task vs result; run_id- und result_id-Bindung result-{dispatch_id}; run_attempt digit-pflichtig).
FALSE_GREEN_PATH=Angreifer/alter Run liefert result-dispatch-2 für dispatch-1 → Bindung an falsche Ausführung.
INDEPENDENT_EVIDENCE=tests/:27,:33 (nondict result/evidence rejected); :103 test_durable_result_preserves_github_run_attempt; contract validate_durable_result (server/app.py:376).
MINIMUM_FIX_OR_GUARD=keiner.
MINIMUM_TEST=run_id-Mismatch + result_id-Mismatch → ValueError (post-Codex).
DISPROVEN_OR_CONFIRMED=CONFIRMED.

## S5 Run-Lookup exakter Titel, Mehrfach-Match fail-closed
CLAIM=Präfix-Dispatch (dispatch-1 vs dispatch-10) kollidiert nicht; zwei Runs gleicher Dispatch-ID dispatchen nicht doppelt.
SOURCE_TRUTH=adapter.py:50-59 (Liste --limit 100; exakter displayTitle == "Courier dispatch {id}"; >1 Match → RuntimeError).
FALSE_GREEN_PATH=Substring-Match dispatch-1 trifft dispatch-10 → falscher run_id; Re-Dispatch bei zwei Runs.
INDEPENDENT_EVIDENCE=tests/:55 test_find_run_uses_exact_dispatch_title (dispatch-1 vs dispatch-10 nebeneinander, erwartet ("4","queued")) — deckt exakt diesen Falsifier ab.
MINIMUM_FIX_OR_GUARD=keiner. Residual (nur Notiz, kein Fix): --limit 100 bei >100 Runs könnte den eigenen Run verpassen → WAITING-Schleife, kein False-SUCCESS.
MINIMUM_TEST=bereits als Test vorhanden (:55); Re-Run post-Codex genügt.
DISPROVEN_OR_CONFIRMED=CONFIRMED.

---

CONFIRMED=S1,S2,S3,S4,S5 (alle 5 per Code-Read auf SHA; kein False-SUCCESS-Pfad gefunden)
DISPROVEN=keine (kein Contamination-Defect auf dieser Linie)
MISSING_EVIDENCE=physischer 2-Run-Nachweis (RUN_1/RUN_2) + Codex-Review; Test-Re-Run auf SHA (alles LIGHT-/Load-gated, bewusst 0 Executions)
OWNER_PACKET=icy-pulsar / MAC / 2026-09-28
BEFORE_RUN1=YES (Paket ist RUN-vorbereitend: S1-S5 nennen je MINIMUM_TEST für RUN-Nachweis)
BEFORE_RUN2=YES (S2-Replay + S3-Verzeichnisbindung sind RUN_2-Replay-Gates)
BEFORE_FREEZE=YES (kein Freeze-Blocker gefunden; --limit-100-Residual als Notiz)
DEFER=MINIMUM_TEST-Re-Runs + physischer 2-Dispatch-Nachweis → post-Codex / RUN-Owner
DO_NOT_REPEAT=Gate-Revalidierung, Cascade A/B/C, 65-96, Ledger, Canary, Full Suite, M06-TIMEOUT-Paket (/tmp/MUSE_TURBO_SHARD_06.packet.md), TURBO 01/03/06/09/11/12, Altfunde neu erzählen

## TURBO-B-Falsifikation (MUSE-elm-aquarius, Selbstangriff)
Geprüft: scripts/run1_physical/verify_proof_contracts.py:28-200 +
RUN1_EXPECTED_HASH_CHAIN.md.
- S1 ÜBERLEBT abgeschwächt: persisted/no_replay/global_counts existieren als
  Zähler-Vergleiche selbstberichteter Snapshots; Krypto-Bindung Run1→Run2 fehlt
  weiter (Residual: Hash-Chain-Extension).
- S2-RUN1 WIDERLEGT: compute_run1_chain (:47-61) mischt final_sha +
  Artifact-Bytes — SHA-Dir-Hash für RUN_1 existiert. S2 überlebt nur verengt
  fürs RUN_2-Restart-Dir.
- S3/S4 ÜBERLEBEN (Guard / Doc-Defect fremder Owner).
- S5 ÜBERLEBT, VERSTÄRKT: not_synthetic prüft nur Selbst-Flag; server_bytes
  liest expected-Hash aus demselben Snapshot (Selbstbezeugung, C1-Klasse).
FAMILY_COMPLETE=NO. NEXT_OWNER=RUN_2-Harness (Krypto-Link+Authority) + GOOGLE_CLI (G195).
