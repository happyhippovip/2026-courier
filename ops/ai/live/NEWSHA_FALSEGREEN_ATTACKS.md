# NEW-SHA FALSE-GREEN ATTACK PREP (READ_ONLY, 2026-09-28)

PRE_FIX_ANCHOR: HEAD fix-cb1-new @ 9dba1505; defect site verifier :62-63 live (re-read).
Fix (SOLE_WINDOWS_WRITER) noch nicht gelandet. Kein Source-Edit von hier.

## A1 — Fix trifft nur den Testpfad, nicht run_loop
ATTACK=patch fixes test but not production path
HOW_FALSE_GREEN_OCCURS=Fix wird nur via Unit-Calls (verify_artifacts mit gemocktem
fetch/local_verify) oder p3_preview-Temp-Kopie bewiesen; run_loop-Produktionspfad
(:94+, echter Poll + Fetch + Verdict-POST) crasht weiter oder wird nie mit
Dict-Tasks geprueft. run_loop-Catch (:145-147) verwandelt Crash in Skip (kein FAIL).
EXACT_CHECK=(a) Neuer Test muss das ECHTE Modulfile + echten run_loop-Pfad nutzen
(kein Temp-Copy); (b) Diff-Hunks muessen im verify_artifacts-Body liegen; (c) Dict-Task
muss im Server-State RESULT_RECEIVED→FAILED_VERIFICATION erreichen (nicht klemmen).
EXPECTED_FAIL_BEFORE_FIX=TypeError :62 oder stiller Skip ohne FAIL-Verdict.
EXPECTED_PASS_AFTER_FIX=FAIL-Verdict gepostet; Task erreicht FAILED_VERIFICATION.
EVIDENCE_REQUIRED=Testfile+Zeilen; State-Transition; Verifier-Log mit FAIL (nicht "Error processing").

## A2 — Nur eine der zwei Set-Stellen gefixt (oder Catch verbreitert)
ATTACK=wrong function/path fixed
HOW_FALSE_GREEN_OCCURS=Guard landet nur an :62 (task-seitig) ODER nur :63 (result-seitig);
oder "Fix" = breiterer except (Schweigen statt FAIL); oder Fix in is_safe_artifact_name
(sieht Task-Defs nie).
EXACT_CHECK=Drei Shapes getrennt fuettern: (i) Task-Artefakt {"path": {...}},
(ii) Result-Artefakt {"path": {...}}, (iii) beides wohlgeformt. Diff-Hunks muessen :62
UND :63 abdecken (oder davor normalisieren).
EXPECTED_FAIL_BEFORE_FIX=TypeError (i)@:62, (ii)@:63.
EXPECTED_PASS_AFTER_FIX="FAIL" ohne Exception in (i)+(ii); (iii) unveraendert.
EVIDENCE_REQUIRED=Diff-Hunk-Liste; 3-Fall-Testlog.

## A3 — Erwartungs-Hash bleibt produzentenkontrolliert
ATTACK=expected hash still producer-controlled
HOW_FALSE_GREEN_OCCURS=task_expected (:78-82) stammt aus via POST /goals opak
gespeicherten Plan-Artefakten — selber Kanal wie der Claim. "Unabhaengiger Hash"
ist selbst-abgeleitet, wenn Goal-Autor == Worker.
EXACT_CHECK=EINEN expected_sha256 von Goal-Submission bis Verify tracen; jeden
Schreiber listen. PASS braucht Schreiber AUSSERHALB {Goal-Submitter, Worker}
(mit Bindungsnachweis) ODER dokumentierte Trust-Annahme (kein stilles Pass).
EXPECTED_FAIL_BEFORE_FIX=Schreiber == Claimant-Kanal, kein unabhaengiger Schreiber.
EXPECTED_PASS_AFTER_FIX=Unabhaengiger Schreiber + Bindung ODER explizite Annahme.
EVIDENCE_REQUIRED=Intake-Code-Spanne; Schreiber-Liste; Bindungs-Record oder Threat-Modell-Absatz.

## A4 — Verifier teilt Schicksal/Autoritaet mit dem Server
ATTACK=verifier still shares authority
HOW_FALSE_GREEN_OCCURS=Verifier pollt Server-State, postet an selben Server, teilt
STATE_FILE-Schicksal; Catch (:145-147) macht Crashs zu Skips. Fix in verify_artifacts
aendert nichts an: Server-down = keine Verifikation; Crash = Skip statt FAIL.
EXACT_CHECK=(a) Server-down-Verhalten muss SICHTBAR sein (Log + Marker), nicht still;
(b) injizierte Exception muss FAIL/ERROR-Verdict-Pfad nehmen, nie Skip-and-Sleep;
(c) Key-Trennung VERIFIER≠WORKER auf NEUER SHA re-pinnen.
EXPECTED_FAIL_BEFORE_FIX=Skip-and-sleep; bearer-only ohne Akteur-Identitaet.
EXPECTED_PASS_AFTER_FIX=Exception→FAIL/ERROR-Pfad definiert + getestet; Keys re-gepinnt.
EVIDENCE_REQUIRED=Server-down-Log; Crash-Injection-Test; Key-Config-Diff.

## A5 — Identitaet ohne Bindung an Ausfuehrung
ATTACK=result identity detached from execution
HOW_FALSE_GREEN_OCCURS=result_id = worker-berechneter Hash BEHAUPTETER Felder
(daemon :212-213); run_id = nackte PID (win) / random-UUID (mac :547, L26);
ACK_DUPLICATE matcht Papier, nicht Ausfuehrungen. Dedup-Fix kann gruen sein,
waehrend zwei Ausfuehrungen eine Identitaet teilen (oder umgekehrt).
EXACT_CHECK=(a) Zwei Ausfuehrungen, gleiche Payload-Bytes → result_ids: Verhalten auf
NEUER SHA aufzeichnen, nichts annehmen; (b) mac run_id an attempt/dispatch gebunden?
(c) rc==0→SUCCESS-Mapping + Missing-Artefakt→FAILED re-verifizieren.
EXPECTED_FAIL_BEFORE_FIX=UUID/PID ungebunden; ACK auf Papier.
EXPECTED_PASS_AFTER_FIX=Bindungsregel-Tabelle (Feld × bound/asserted) + pinndender Test.
EVIDENCE_REQUIRED=Bindungsregel-Tabelle; 2-Ausfuehrungs-Log.

## A6 — B startet manuell, sieht automatisch aus
ATTACK=B starts manually rather than automatically
HOW_FALSE_GREEN_OCCURS=Claim ohne Akteur-Identitaet (bearer-only), Verify-Block ohne
Timestamps (L25) → Idle-Poll-Claim ununterscheidbar von manuellem Claim.
EXACT_CHECK=B-Auto-Paket MUSS: (i) Daemon-Poll-Log mit B-Claim (prozessgebunden),
(ii) dispatched_at im Poll-Fenster nach A-Verify, (iii) kein manueller Claim im
Fenster — detektierbar nur via Akteur-Logging (fehlt → MISSING; dann Urteil
INFERRED, nie PROVEN).
EXPECTED_FAIL_BEFORE_FIX=Kein Akteur-Log, keine Timestamps → auto UNBEWEISBAR.
EXPECTED_PASS_AFTER_FIX=Paket komplett ODER explizit INFERRED (ehrlich).
EVIDENCE_REQUIRED=Daemon-Log-Auszug; dispatched_at-Werte; Akteur-Log-An/Abwesenheit.

## A7 — RUN2 konsumiert synthetischen/verunreinigten RUN1-Erfolg
ATTACK=RUN2 gate consumes synthetic RUN1 success (inkl. stale-evidence reuse)
HOW_FALSE_GREEN_OCCURS=RUN2-Checker liest "A RECONCILED?" ohne WIE. Live-State enthaelt
fremde Test-Goals ("do something"/"test-worker", eigene Probe) + alte Q10; Skripte
ignorieren --db (M7). RUN2-PASS auf geteiltem State beweist nichts ueber den Restart.
Stale-Redelivery (ACK_DUPLICATE) zaehlt als "frischer Beweis".
EXACT_CHECK=(a) RUN-eigene STATE_FILE (Env-Pin protokolliert) + Pre-RUN-Snapshot
(A-frei, Hash protokolliert); (b) A/B-Task-IDs == vorregistrierte RUN-IDs (kein Tausch);
(c) fremde Goals im RUN-State per Grep abwesend.
EXPECTED_FAIL_BEFORE_FIX=Fremde Goals im Live-State; --db-Illusion.
EXPECTED_PASS_AFTER_FIX=Dedizierte State-Datei + Pre/Post-Snapshots + ID-Gleichheit.
EVIDENCE_REQUIRED=STATE_FILE-Env-Record; Snapshot-Hashes; ID-Check; Fremd-Goals-Grep (leer).

## A8 — Alte Proofs werden auf neuer SHA wiederverwendet
ATTACK=changed SHA invalidates old proof but old proof gets reused
HOW_FALSE_GREEN_OCCURS=Neue SHA landet; alte Beweise (57/1/0, Fingerprints, ACK-Pins,
Zeilen-Refs) werden ohne Re-Execution zitiert ("GREEN carried over").
EXACT_CHECK=Konvergenz (L22): FINAL==REMOTE==LOCAL==BOUND auf NEUER SHA vierfach,
unabhaengig beobachtbar; jedes wiederverwendete Item mit PROVEN_ON_SHA; jede vom
Writer-Diff beruehrte Spanne wird RE-PROVEN, nicht zitiert.
EXPECTED_FAIL_BEFORE_FIX=Beweise auf 3c2aa516/e5751783/34b0a42 gemischt; HEAD 9dba1505
hat Zeilen-Refs invalidiert; GATE_STATE fehlt.
EXPECTED_PASS_AFTER_FIX=NEW_SHA-Dossier mit PROVEN_ON-Labels + Re-Run-Log; unberuehrte
Spannen explizit als carried mit Begruendung.
EVIDENCE_REQUIRED=4-fach-SHA-Record; Item-Labels; Writer-Diff-Spannen; Re-Run-Log.

## FINAL
TOP_FALSE_GREEN_RISKS=A8 (carried-over green, wahrscheinlichst) > A2 (Halb-Fix) >
A1 (Test-Double-Fix) > A7 (verunreinigter State) > A6 (manuelles B) > A5 > A4 > A3
REVIEWER_MUST_CHECK=Diff beruehrt :62 UND :63 (oder normalisiert davor); FAIL-Verdict
gepostet (kein Skip) bei Dict-Tasks; 4-fach-SHA neu; RUN-eigener State; Akteur-Beleg
fuer B; Bindungsregel-Tabelle; kein Proof ohne PROVEN_ON-Label
NEXT_TRIGGER=NEW_WRITER_SHA
