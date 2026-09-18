# Courier Symphony Muse — Chat-Übergabe und Wiederanlauf

Erstellt: 18.09.2026. Geprüfter Repository-Snapshot: `56fa90573dc2ad7a45ac407025ec1113a139b88b` auf `release-candidate-integration`.
Repository: `happyhippovip/2026-courier`.

**Engineering-Übergabe, keine Produktionsfreigabe, kein neuer Scheduler und kein Nachweis erfolgreicher physischer Abnahme.** Diese Datei ist eine historische Übergabe innerhalb des bestehenden `ops/ai`-Gedächtnisses. Sie ersetzt weder Ownership noch kanonische Laufzeitdaten.

## 1. Nutzerziel und Auftragsgrenze

Der Nutzer möchte Courier fertigstellen, ohne ständig neue weiter/proceed-Prompts schicken zu müssen. Codex auf dem MacBook soll sich auf Ledger/Guard und unmittelbar notwendige Motor-, Persistenz- und Review-Arbeit konzentrieren. Gewünscht sind nachvollziehbarer Fortschritt, sparsamer Kontingenteinsatz, geringe Rechnerbelastung und ein gespeicherter Stand für Wiederaufnahme nach Chatverlust, Prozessende oder Rechnerneustart.

Das Ziel ist nicht dauerhaftes Tokenverbrauchen oder grüne Statusfelder. Sichere vorbereitete Arbeit soll selbstständig abgearbeitet werden; Ergebnisse sollen dauerhaft festgehalten werden; echte Abhängigkeiten sollen zu kontrolliertem Warten statt wiederholten unveränderten Scans führen.

Der letzte ausdrückliche stop-Befehl wurde bestätigt. Dieser neue Auftrag erlaubt Übergabe und Dokumentationssicherung. Er startet keine Produktionsdienste, Deployments, Merges, Zahlungen oder Publikationen. Ein späterer Arbeitsauftrag muss die vorhandenen Rollen und Berechtigungen beachten.

## 2. Belegklassen und Wissensgrenzen

Teile des älteren Chatverlaufs sind in der Sicherungssitzung nicht lesbar. Sie lassen sich nicht zuverlässig rekonstruieren. Vorhandene Originalanhänge wurden separat privat archiviert; auch sie können bereits gekürzte Terminalausgaben enthalten. Kein vollständiger Chat-Export und keine Garantie, jedes jemals besprochene Detail erhalten zu haben.

- Repository-beobachtet: Inhalt wurde am oben genannten vollständigen SHA gelesen. Beweist committed Inhalt, nicht laufende Prozesse.
- Agentenbericht: Log/Paket/Checkpoint behauptet Ausführung oder Test. Rohbeleg und Zielbindung bleiben zu prüfen.
- Spezifikation: gewünschtes Verhalten oder Prüfanordnung, keine fertige Implementierung.
- Arbeitskopie/Draft: lokale Änderungen ohne Nachweis, dass sie im Remote-Snapshot gesichert sind.
- Offen: nicht gelesen, ausgeführt, erreichbar oder widerspruchsfrei. Keine plausiblen Ersatzannahmen.

In dieser Sicherungsrunde wurden keine Courier-Tests und keine Mac-/Windows-Laufzeitaktionen ausgeführt. Die Containerumgebung ist nicht der Nutzer-Mac. Direkter Container-Download von GitHub scheiterte an DNS; die GitHub-Verbindung lieferte die verwendeten Repository-Inhalte. Der Ledger-JSON-Abruf lieferte Metadaten, aber leeren Inhalt: weder Ledger leer noch ein aktueller Ledger-Zustand darf daraus abgeleitet werden. [R01–R12]

## 3. Beobachteter Snapshot

| Gegenstand | Beobachtung | Grenze |
|---|---|---|
| Remote-Integration | `56fa90573dc2ad7a45ac407025ec1113a139b88b`; Commit `docs(continuous): record iter7 YAML-break lesson`, 10:15:25 UTC | Kein Beweis für lokalen HEAD oder Dienste |
| START_HERE | `ops/ai/` als gemeinsames Gedächtnis; weiterhin `CODE_BASE_HEAD=0c8d1edd…` | Nicht automatisch aktuelle Bindung aller späteren Laufzeitänderungen |
| Muse-Checkpoint | iteration 7; darin zuletzt verifizierter HEAD `871c81d3…`; nächste Aktion `RECOMPUTE_FRONTIER_NEXT_TURN` | Keine aktuelle Prozessbeobachtung |
| Codex-Review-Checkpoint | Committed YAML weiterhin iteration 0; Review-Snapshot `9837e5ae…` | Nicht Beweis fehlender Arbeit; Ergebnisse können anderswo liegen |
| Google-Implementierungs-Checkpoint | Gelesener Kopfbereich iteration 0 und alter Snapshot | Keine aktuelle Fortschrittsmessung |
| NEXT_WORK | Frühere Zustände wie `WAITING_FOR_COMPLETE_PACKET` und `OWNERSHIP_COORDINATION_REQUIRED` | Nicht als frischer Gesamtstatus verwenden |
| Mac-/Windows-Prozesse, Deploy-SHA, aktuelle Abnahme | In dieser Runde nicht beobachtet | Kein YES/COMPLETE/CANONICAL_ACCEPTED |

Quellen: [R01–R07, R16].

## 4. Gemeinsames Gedächtnis

Bestehendes gemeinsames Gedächtnis: `ops/ai/`. Erweitern, keine konkurrierende Wahrheit aufbauen. Historische `.agents/knowledge/*` und Root-Backlog nicht als neue kanonische Queue verwenden. [R02]

```text
ops/ai/START_HERE.md
ops/ai/MASTER_OPERATING_SYSTEM.md
ops/ai/CLOUD_ALIGNMENT_2026-09-18.md
ops/ai/OWNERSHIP_MAP.yaml
ops/ai/NEXT_WORK.yaml
ops/ai/DEFERRED_LEDGER_QUEUE.yaml
ops/ai/TEST_MAP.yaml
ops/ai/FAILURE_SIGNATURES.yaml
ops/ai/ATTACK_LOG.md
ops/ai/ARCHITECTURE_BASELINE.md
ops/ai/CODEX_BUDGET.md
ops/ai/MORNING_REVIEW.md
ops/ai/DAILY_REMINDER.md
ops/ai/WINDOWS_RUNTIME_MAP.md
ops/ai/PHYSICAL_ACCEPTANCE_PLAN.md
ops/ai/CUSTOMER_GATES.md
ops/ai/MUSE_CONTINUOUS_WORK.yaml
ops/ai/GOOGLE_CONTINUOUS_WORK.yaml
ops/ai/CODEX_CONTINUOUS_REVIEW.yaml
ops/ai/WINDOWS_CONTINUOUS_WORK.yaml
ops/ai/packets/
KNOWN_GOOD_CHECKPOINT.md
```

Nicht alle Dateien wurden in dieser Runde vollständig neu gelesen. Gelesen wurden START_HERE, Ownership, NEXT_WORK, Queue, TEST_MAP, ATTACK_LOG, Muse-/Codex-Loop und KNOWN_GOOD; vom Google-Loop der relevante Kopfbereich. Weitere Pfade stammen aus vorhandenen Verweisen und früheren Übergaben.

## 5. Rollen und Eigentum

Die gelesene OWNERSHIP_MAP weist GOOGLE den sensiblen Produktionsscope `ledger_guard_motor` bis zum ausdrücklichen Handoff und kanonische Integration/Windows-Laufzeit zu. MUSE besitzt Cockpit/Studio und Invarianten-/Paketprüfung. NEWSY ist read-only Scout. CODEX ist unabhängiger Reviewer mit vollständigen Paketen. CHATGPT ist Supervisor, nicht Runtime-Autorität. Physische persistente Laufzeitaktionen brauchen konkrete Maschinenberechtigung und Belege. [R04]

Eine YAML-Zeile `owner: GOOGLE` ist Zuständigkeitsdokumentation, keine technische Sperre oder Authentifizierung. Aktiven Besitzer vor Änderungen klären. Verschiedene Modellnamen, Worker-Namen oder API-Schlüssel beweisen nicht automatisch unabhängige Akteure.

Der jüngste Wunsch nach einer Zentrale in Codex steht neben der bestehenden read-only Codex-Rolle. Nicht stillschweigend auflösen. Codex kann zunächst begrenzte Ledger-Entscheidungs-/Review-Arbeit übernehmen. Produktionsschreibrechte brauchen expliziten aktuellen Scope-Handoff; sonst kollidiert Codex mit Google und entwertet die unabhängige Prüfung.

Architektur: ein Motor als Scheduler/Claim-Autorität; kanonischer Serverzustand als Laufzeitdatenquelle; Guard vor Ledger; Ledger als Aufzeichnung; Cockpit als Beobachter. Engineering-Arbeitslisten dürfen kein zweiter Produktionsscheduler werden.

## 6. Offene und widersprüchliche Arbeitsbereiche

### DLQ-01 — Selbstbestätigung über Revisionen

Historischer Angriff: selbst erzeugtes MACHINE_ARTIFACT in Update 1 ablegen und in Update 2 als bereits vorhandene Evidenz für CANONICAL_ACCEPTED verwenden. Ein Same-update-Verbot schließt das nicht. Die Queue bindet die letzte Reproduktion an `50810001`, nicht an diesen Snapshot. [R03]

Im gelesenen committed Code bildet update() prior_evidence aus alter/neuer Evidenz. has_physical_proof prüft Typ, SHA, Runtime-String und VALID. Zusätzliche Identitätsprüfungen gelten für neu hinzugefügte Evidenz und vergleichen Strings. Im gelesenen Abschnitt basiert das Prädikat nicht auf authentifizierter Attester-Autorität. Codebefund, keine in dieser Runde erneut ausgeführte Reproduktion. [R09]

Muse meldet dagegen einen lokalen Draft mit introducer_map/Writer-History-Check und Tests; übrige Draft-Dateien seien uncommitted und fremd bearbeitet. Nicht als integriert/gesichert ausgeben. [R06, R08]

Paket: `ops/ai/packets/DLQ-01_review_packet.md`. Forge-Anhang unterscheidet History-Check (b) und noch zu entscheidende authentifizierte Attester-Autorität (c). History-Check allein ist keine vollständige Vertrauenswurzel. Die separat hochgeladene strengere Spezifikation verlangt serverseitig authentifizierte Principals, unveränderliche Event-/Digest-/Subject-Bindung und unabhängige Verifikation. [R11, U01–U02]

### DLQ-02 — Frische, Uhr, Binding-Epoch

Historisch wurden 2020-datierte und zukünftige Evidenzen trotz VALID akzeptiert. Forge schlägt Zeitfenster/Monotonie vor. Muse berichtet später einen lokalen 48-Stunden-Draft, nicht eine vollständig implementierte Epoch-/Attestierungsarchitektur. Der gelesene committed has_physical_proof-Abschnitt prüft keinen Zeitwert. [R08–R09, R12]

Die spätere Upload-Spezifikation ist strenger: Producer-Zeit advisory; serverseitige Empfangs-/Verifikationszeit; kanonische Binding-Epoch; Frische je Evidenzklasse; kein universelles TTL. Teilweise widersprüchliche Dokumente als ausstehende Spezifikationsentscheidung erhalten; nicht 48 Stunden heimlich zum endgültigen Vertrag erklären. [U01–U02]

Prüffragen: Monoton neuerer Zeitstempel verhindert keine künstliche Verjüngung. utc_now() im lokalen Ledger-Writer wird nicht allein dadurch zur unabhängigen Serveruhr. Gleicher SHA bestätigt keinen gleichen Prozess nach Neustart.

### DLQ-03 — Duplicate/ACK/Revision

Queue und ATTACK_LOG melden früheren raise-at-storage-Vertrag als implementiert und geprüft: keine sinnlose zweite Änderung, veraltete Revision kollidiert, autoritativer Wert bleibt. Historischer Contract-Test-Commit `20ca0601`. [R03, R08]

Spätere Spezifikation verlangt typisierte Outcomes NO_MEANINGFUL_CHANGE, REVISION_CONFLICT, RESULT_CONFLICT statt String-Teiltreffern. Im gelesenen Motor stehen noch `"meaningful change" in str(e)` und `"revision conflict" in str(e)`. Größere Forderung nicht als erfüllt belegt. [R10, U02]

ACK-Verlust differenzieren: Wiederholung mit ursprünglicher nun alter Revision kann zuerst Revisionskonflikt ergeben. Nach Reload prüfen, ob Resultat bereits existiert. Nicht jede identische Zustellung ist unmittelbar derselbe Storage-No-op. Widersprüchliche Duplikate nicht blind rebasing/retrying überschreiben.

### DLQ-04 / DLQ-08 — Frontier, Double-submission, Hang, Drain

Frühere Änderungen ergänzten done_edges und später continue für Frontier-Neuberechnung. Historische Referenzen `17b39cbc`, `ceba1fe0`, später `bbc86b56` nicht als denselben Fix behandeln. [R03, R08, U03]

Im gelesenen Motor erfolgt future.result() erst unter future.done(). Die frühere Begründung nacktes future.result() beweist den Hang ist unzureichend. Daneben existiert Acht-Sekunden-Abandon: Eintrag aus running_tasks entfernen und Blocker-Schreibversuch. Im gezeigten Pfad keine Beendigung des laufenden Threads sichtbar. --once-Ausgang verwendet os._exit(0). [R10]

Nächste Prüfung, noch kein Ergebnis: echter Motor mit kontrolliert hängender Arbeit; gesunder unabhängiger Task läuft weiter; persistierter Timeout/Fehler; keine verlorene Fertigstellung, doppelte Ausführung oder Ressourcenlecks; korrekter Exitcode. Ein grüner Einzeltest/Future-Verweisentfernung beweist das nicht. Harter Exit ist kein Beleg geordneter Persistenz/Cleanup.

### DLQ-05 — Provider-/Quota-Isolation

Historische Implementierung `0c8d1edd`: Schlüssel aus Quota-Pool und worker-gemeldetem Provider. Queue meldet IMPLEMENTED_AND_VERIFIED und enthält zugleich PENDING IDENTITY REVIEW. Muse berichtet unbefüllte worker_quota_pools in Produktionscode, effektiver Schlüssel worker_id:provider. [R03, R08]

Neu: Muse beschreibt Gate-Entfernung im Owner-Commit `29191a53` ausdrücklich als beabsichtigten WAITING_PROVIDER-Deadlock-Fix; WATCH aufgelöst. Nicht blind altes Gate wiederherstellen. Ebenso wenig vollständige clusterweite Quota-Isolation daraus ableiten. Aktuellen Vertrag/Task-Betroffenheit gegen neuen Code prüfen. [R06, R08]

Paket: `ops/ai/packets/CODEX_DLQ05-provider-lock.md`. Engste vertrauenswürdig abgeleitete Quota-Ressource: gleiche ausgeschöpfte Quota wartet, unabhängiger Account/Pool/Provider und lokale READY-Arbeit laufen weiter. Provider-/Capability-Strings sind kein authentifizierter Quota-Vertrag.

### DLQ-06 — Windows-Dateifreigabekonflikte

Erste Tests prüften nur fehlende Retry-Schleife; zeitweise pass/assert True. Kein Verhaltensnachweis eines Windows-Rennens. Später Fault-Injection-Tests und Retry-Fix `3039126e`. Hochgeladene Folgesitzung mockte validate_bundle und entfernte Testdatei lokal. Muse hält Wiederherstellung/saubere Anpassung als Owner-Punkt fest. [U03–U04, R08]

Fault Injection belegt behandelte Fehlerklasse; echte Windows-Handles/Sharing-Modi brauchen Windows-Beleg. Reader-Retry allein repariert keinen Writer-Fehler an os.replace. Persistente Zugriffsfehler/korruptes JSON dürfen nicht endlos als transient gelten.

Pakete: `WINDOWS_DLQ06-race-prep.md`, `WINDOWS_DLQ06-worker-commands.md` unter ops/ai/packets/.

### DLQ-07 — INIT-Selbstakzeptanz und Überblockierung

Historisch konnte initialize() direkt akzeptierten Zustand erzeugen. Muse meldet INIT-Gate-Fix `8918bc8f` als geprüft, aber Überblockierung: Demotion auf INVALID außerhalb des verwendeten Schemas, sechs rote Tests. Folgepaket `DLQ-07-FOLLOWUP-overblock.md`. [R08]

Muse meldet Demotion-Schleife im lokalen Draft entfernt und Tests grün. Draft-Bericht, keine gesicherte Integration. Queue enthält weiterhin alte Angriffe. INIT-PROVISIONAL ist Strukturregel; spätere Updates brauchen unabhängige Attestierung.

### G5 / W04–W06 — Ausnahme, Retry-Ende, Blocker-Erhalt

Reports nennen geschluckte Future-Ausnahme, Reset von Retry-Zählern nach Limit und Erfolg von B überschreibt A-Blocker. Erste Reproducer waren AST-Suchen, kein automatisch laufzeitbewiesener endloser Hang. Späterer Report nennt Reparaturen in `bbc86b56`. [U03–U04]

Aktueller Motor versucht Exceptions/Timeouts im Ledger zu erfassen; Fehler dieses Updates werden nur ausgegeben. Dauerhafte Behandlung fehlgeschlagener Blocker-Persistenz prüfen. Blocker von A erhalten darf nicht B dauerhaft stoppen bedeuten. Task-lokale Fehler und globale Ausführbarkeit trennen. [R10]

## 7. Strengere Attestierungs-Spezifikation nicht verlieren

Uploads `markdown(20260918-074842).md eingefügt` und `markdown (2)(20260918-075003).md eingefügt` plus identische spätere Kopien enthalten eine Spezifikation an `d00a00a8…`. Sie sagen ausdrücklich keine Produktionsimplementierung, kein Commit, kein Push. [U01–U02]

Erforderliche Themen:

1. Authentifizierte serverseitige Principals statt Producer/Verifier/Writer-Strings. Credentials desselben Actors nicht automatisch unabhängig.
2. Canonical Attestation Registry innerhalb bestehender Serverautorität, unveränderliche attestation_id/Event-ID/Subject/Digest/SHA/Runtime/Machine/Boot/Process-Bindung, keine zweite Wahrheit.
3. Producer-Zeit advisory; Server erzeugt server_received_at, verification_time, binding_epoch_id. Skew 299/300 Sekunden als Input-Sanity zulässig, 301 unzulässig; kein TTL.
4. Epoch-Wechsel bei relevanter Runtime/Artifact/Prozess/Boot/Deployment/Trust/Guard-Semantik-Änderung. Nur Dokumentation bei identischem aktivem Artefakt erzeugt keinen automatischen Runtime-Epoch-Wechsel.
5. RUNTIME_LIVE_STATE, IMMUTABLE_EXTERNAL_EVENT, MUTABLE_EXTERNAL_STATE, DEPLOYMENT_EVENT, ONE_TIME_ACCEPTANCE_RUN unterschiedlich behandeln.
6. Alte unstrukturierte Evidenz sichtbar, aber nicht neue aktuelle Attestierung; keine erfundenen Principal/Epoch/Zeitfelder bei Migration.
7. Identisches Replay idempotent; Widerspruch expliziter Konflikt; keine neue Wirkung nur wegen ACK-Verlust.
8. Crash-Matrix zwischen Artefakt, Registry, Verifikation, Receipt, Ledger, ACK, Epoch-Rotation; keine blinde Wiederholung möglicher externer Effekte.
9. Inputlimits, JSON-Ambiguität, URL-/Pfadmissbrauch, Revocation/Supersession und Signaturbindung.

Offene Designabstimmung: Forge fordert schwächere History-/Zeitfenster-Maßnahmen, Uploads Registry/Epoch/signierte Receipts. Versionierten maßgeblichen Vertrag mit Owner festlegen. Blueprint ready ist keine Abnahme.

Soll-T3: test_ledger_attestation_trust_root.py, test_ledger_freshness_binding_epoch.py, test_ledger_duplicate_semantics_contract.py, test_attestation_cross_defect_crash.py, bestehende False-Green-/Edge-Conservation-Tests und test_execution_truth.mjs. Spezifikation beweist weder Vorhandensein neuer Dateien noch ausgeführte Ergebnisse.

## 8. Besonders gefährliche falsche Abschlussannahmen

- IMPLEMENTED_AND_VERIFIED, SAFE_WORK_REMAINING=0, LANES_EXHAUSTED und Testanzahlen sind keine selbsterklärenden Beweise.
- T2/T3: PASS, /tmp-Verweise und QUESTIONS_TO_ANSWER: None im W01–W07-Paket erfüllen keinen vollständigen Review-Auftrag. [U04]
- Früheres NEXT_WORK-Update iterierte lanes statt tatsächlicher tasks. Report behauptete Änderungen, später gelesene Datei zeigte sie nicht. Read-back/Schema-Prüfung nötig. [U03, R05]
- YAML-Arbeitsplan ist keine installierte Hintergrundausführung. Checkpoint nur im Modellgedächtnis ist keine belastbare Wiederanlaufsicherung.
- KNOWN_GOOD sagt SAFE AFTER RESTART: YES, bindet sich aber an `2ee8d905…` plus lokale Fixes und beschreibt Windows-Service/Task/Detached-Loop alternativ statt eindeutig beobachteter Installation. Runbook-Behauptung, keine hier bestätigte Neustartfreigabe. [R07]
- Runbook-Eintrag BypassSandbox: true ist keine durch diese Übergabe erteilte Freigabe/Voraussetzung. Sicherheitsgrenzen nicht umgehen.
- Zwei reale Worker/zehn Tasks, Mock-Zyklen und 310 Testfälle sind verschiedene Belegarten. Alte physische Abnahme nicht auf geänderte Prädikate übertragen.
- DUPLICATE_EXTERNAL_EFFECTS=0 braucht Instrumentierung. Historischer Report fand keine Counter-Writer; Initialwert Null ist keine gemessene Exactly-once-Garantie. [U05]
- Secrets und private Rohlogs nicht veröffentlichen. Entfernen aus aktuellem Code macht alte Exposition nicht rückwirkend geheim; Rotation nur autorisiert.

## 9. Teststrategie und Rechnerbelastung

T0 Syntax/Import/Schema/Isolation; T1 exakte Regression; T2 betroffene Komponenten; T3 kleine adversarielle Truth-Suite; T4 nur Integrationsgrenze. Shared-State/Physical seriell; keine parallelen schweren Gesamtsuiten auf dem Mac. TEST_MAP enthält Platzhalter `import ast,...`/`test_<area>`: keine direkt lauffähigen Befehle. [R13, U06]

Bekannte Zustandsdatei, isolierte Ressourcen, konkrete Befehle/Exitcodes, Laufzeitgrenzen, Cleanup eigener Prozesse. Timeout ersetzt keine Ressourcenverwaltung. Kein killall, fremde Locks löschen oder Prüfungen abschalten für grüne Anzeige.

Historische Muse-Thermalanalyse meldete hohen Swap-/Speicherdruck, aber gesperrtes ps/top; kein einzelner Schuldiger bewiesen. Aktuellen Zustand nicht extrapolieren. [U05]

Dokumentierte Fallen: Auth-Header-Platzhalter/Bracket-Fehler erzeugten 401; Importzeit-Konfiguration; Standalone-Pass nicht automatisch Batch-Pass; reset_state und Testlocks; fehlende State-Isolation kann echte Daten beschädigen. Queue lässt konkreten COURIER_STATE_DIR/COURIER_STATE_FILE-Kandidaten mangels aktueller Evidenz aus; nicht als sicheren offenen Fehler erfinden. [R03, R08]

## 10. Sparsamer Codex-Dauerbetrieb und Persistenz

Codex-YAML ist ausdrücklich read-only: keine Produktionsedits/Commits/Pushes; acht Lanes und RECORD_VERDICT_IN_CHECKPOINT_MEMORY; committed Checkpoint Null. Aktiver Codex-Bot und rebootfester Reviewer sind dadurch nicht nachgewiesen. [R06]

Vor neuer Dauerausführung vorhandenen Runner lokal identifizieren: Prozess, Arbeitsverzeichnis, Session-ID, Konfiguration, State-/Output-Pfad, letzte echte Aktion, Wiederanlaufweg, Besitzer. Keine neue Schleife erfinden, bevor vorhandene verstanden ist.

Vorschlag für nächste autorisierte Runde: ein Reviewer; unveränderliche Review-Revision pro Einheit; nur neue vollständige Ledger-Pakete; unveränderte erledigte Pakete nicht erneut prüfen; nach Ergebnis nächste sichere Arbeit; bei reinen Abhängigkeiten ohne LLM-Dauerpolling yielden; begrenzte Retries; Stop/Resume; haltbarer Resultat-Export durch erlaubten Recorder. Datei allein erfüllt das nicht.

Read-only und Checkpoint ins Repo schreiben widersprechen sich. Entweder Codex liefert Ergebnisse und autorisierter Recorder speichert, oder expliziter enger Schreibscope nur für Review-Artefakte. Codex-Verbote nicht unbemerkt abschalten.

Offizielle OpenAI-Dokumentation beschreibt codex exec für nichtinteraktive Arbeit und resume für Sitzungswiederaufnahme. Das bestätigt keine Installation auf diesem Mac. Installierte Version/--help vor Befehlen prüfen. [W01–W02]

## 11. Modell/Budget — letzte offene Diskussion

Nutzer fragte nach GPT-6 Astra + Mittel als Standard, Hoch gezielt, sehr hoch nicht dauerhaft. Abschließende Entscheidung oder tatsächlich geänderte Konfiguration hier nicht belegt.

Arbeitsprinzip: angemessener Aufwand für Routine; höhere Denktiefe für konkrete schwierige Trust-/Concurrency-/Crash-Frage; tatsächlichen Verbrauch messen. Langsames Bearbeiten/Tagesprompt nicht automatisch billig. OpenAI beschreibt Abhängigkeit von Modell, Aufgabe, Kontext, Reasoning und Ausführungsweise; /status/Usage-Dashboard prüfen. [W03]

Frühere Prozentstände historisch/nutzerberichtet. Tatsächlicher Rest, Reset, Zusatzcredits/Auto-Recharge unbekannt. Kein Creditkauf, keine kostenpflichtige API-Umschaltung oder Budgeterweiterung durch diesen Auftrag.

Alte Budgetformeln sind Vorschläge, keine Providerregeln. Routingfrage erhalten: negatives Gewicht für Paketvorbereitung kann gut vorbereitete schwierige Reviews aussortieren; künstliches Verbrauchsminimum bringt keinen Nutzen. Nicht ungefragt gesamtes Routing neu entwerfen. [U06]

## 12. Historischer Kontext

17.09.: Windows Central wurde als hinter Integration/vor PR41 beschrieben. Späterer Report meldete Deployment `355c98670b3ae469e502c52d2c5f3e39c2b042bb` und Zehn-Task-/Zwei-Worker-Lauf. Historische Behauptung für diesen Stand, keine aktuelle Abnahme. [U07]

Danach fix_final_ledger*.py-Schritte mit gewünschten Endzuständen und als MACHINE_ARTIFACT bezeichneten Commit-URLs. Diese Selbstbestätigung wurde später angegriffen. Commit-URL belegt Commit, nicht physische Ausführung. [U08]

Weitere Runden trennten Code-Pass, Arbeitskopie-Pass, Ledger-Behauptung, Prozessbindung und externe Wirkung. Gleichzeitig parallele Writer, Shared-State-Tests, temporäre Reproducer, wiederholte Prompts. ops/ai und Agenten-Loops sollten Wiederholung reduzieren, sind aber keine automatisch bewiesene Ausführungsinfrastruktur.

PR41 Motor-Eligibility; PR42/PR43 spätere Proof-/Ledger-Arbeit: heutiger Status in dieser Runde nicht abgefragt. PR44 aktuell geschlossen, nicht gemergt wegen parallel anders gelandetem Ops-System. PR45 aktuell offen/Draft/nicht gemergt; auf Duplikate prüfen. [R14–R15]

Visuelle Konzepte: Vier-Agenten-/3D-Wasserfall-Storyboard und Courier-Cockpit. Design-/Demo-Artefakte, keine Laufzeitbelege. Private Bilder nicht mitgepusht. Ledger-Abschluss hat im jüngsten Nutzerwunsch Vorrang vor UI/Marketing.

## 13. Nächste Schritte

1. **Lokalen Stand sichern:** Owner sichert uncommittete Ledger/Motor/Guard/Test-Änderungen und notwendige untracked Dateien, ohne fremde Arbeit zu verwerfen. Remote/lokal/staged/unstaged/untracked und Besitzer erfassen. Wegen expliziter Draft-Meldungen wichtigste fehlende Sicherung.
2. **Codex eng zuschneiden:** unbegründete Ledger-Akzeptanz verhindern; aktueller committed Stand gegen DLQ01/02 und Owner-Drafts; konkrete Trust-/Freshness-Entscheidung oder vollständiges Implementierungsreview, kein breiter Audit. W01–W07 nur für ihren SHA, neue Deltas explizit. Unvollständige Pakete zurück an Muse/Google; anderes vollständiges Ledger-Paket nutzen; keine künstliche Arbeit.
3. **Google integriert:** kohärenter Implementierungsstand, echte T1/T2/T3-Belege, vollständiges Review-Paket. Muse stabilisiert Reproducer und dokumentiert widersprüchliche Checkpoints. Windows-Physical ist konkrete autorisierte Maschinenarbeit; andere Maschine allein beweist kein fehlendes Recht.

Diese Reihenfolge ist Übergabeempfehlung, kein gestarteter Auftrag und keine Ownership-Änderung.

## 14. Wiederanlauf nach Chat-/Rechnerverlust

Vor geplantem Neustart: tatsächlicher Owner sichert lokale getrackte/untracked Arbeit außerhalb flüchtiger Verzeichnisse; genaue Startpfade/Versionen/sichere Config-Referenzen/Checkpoints/Outbox/eigene Prozesszuordnung. Runtime-State nur konsistent über Anwendungssicherung oder koordinierten Stillstand kopieren. Secrets nur privat, Repo nur redigierte Referenzen. Prüfsummen und Wiederherstellung prüfen. Kein pauschales stash -u/reset --hard/Blind-Cleanup über alle Writer.

Nach Neustart: Übergabe/Checkpoint/Stopstatus lesen; lokale/Remote-Revision, Dateien, Dienste, Listener, Logfortschritt und Besitzer neu feststellen; autogestartete Instanzen nicht duplizieren. Vorhandenen dokumentierten zulässigen Startweg verwenden. Aus dieser Übergabe nicht wahllos neue Server/Verifier starten.

Mögliche Arbeit mit verlorenem ACK zuerst kanonisch abgleichen; kein blindes Effect-Replay. Prozess-/Boot-/Epoch-Vertrag beachten. Desktop wieder da ist keine Motor-Abnahme.

Diese Sicherung enthält keinen Zugriff auf Nutzer-Mac/Windows-State, keine Credential-Sicherung, keinen Beleg aktiven Autostarts und keine Garantie über fremde uncommittete Arbeitskopien. Separater privater ZIP enthält 76 hier gemountete Anhänge/visuelle Anlagen, nicht gesamtes Dateisystem oder verborgene Chatnachrichten.

## 15. Vollständigkeitscheck

- Aktive Sessions/Besitzer/Stopstatus und lokal uncommittete Drafts gesichert?
- Tatsächlicher Runner oder nur YAML; wo dauerhafte Review-Ergebnisse; Reboot-/Sessionverlust getestet?
- DLQ01-Attester-Autorität und DLQ02-Clock/Epoch-Vertrag entschieden/implementiert?
- Typisierte Duplicate-Fehler oder nur alter String-Vertrag?
- Abandon/harter Exit/Blocker-Persistenz/gesunde Siblings verhaltensgeprüft?
- DLQ05 nach absichtlicher Gate-Entfernung konsistent; Quota-Zuordnung tatsächlich befüllt?
- DLQ06-Tests vorhanden/isoliert; Mocks nicht als Gesamtbeweis?
- INIT-Schutz ohne Überblockierung; alte Evidenz nicht zu neuer Trust-Architektur umetikettiert?
- Windows-Prozesskette und Deploy/Test-SHA; alte Abnahmen nicht übernommen?
- T3-Dateien/Exitcodes/Rohlogs/Cleanup wirklich vorhanden?
- Queue/NEXT_WORK/Checkpoint-Schema konsistent; YES-with-owner-Strings nicht als boolesches Ready behandeln?
- Alte Secret-Exposition und ggf. autorisierte Rotation separat?
- Budget/Reset aktuell, kein erfundener Rest oder Zusatzkauf?

## 16. Quellen

Fester Snapshot-Permalink-Präfix:
https://github.com/happyhippovip/2026-courier/blob/56fa90573dc2ad7a45ac407025ec1113a139b88b/

R01 Branch-API release-candidate-integration, HEAD/Commitzeit.
R02 ops/ai/START_HERE.md.
R03 ops/ai/DEFERRED_LEDGER_QUEUE.yaml.
R04 ops/ai/OWNERSHIP_MAP.yaml.
R05 ops/ai/NEXT_WORK.yaml.
R06 ops/ai/MUSE_CONTINUOUS_WORK.yaml und ops/ai/CODEX_CONTINUOUS_REVIEW.yaml.
R07 KNOWN_GOOD_CHECKPOINT.md.
R08 ops/ai/ATTACK_LOG.md.
R09 scripts/agent_handoff_ledger.py, gelesene Zeilen 650–840.
R10 scripts/courier_continue.py, gelesene Zeilen 510–650.
R11 ops/ai/packets/DLQ-01_review_packet.md, Forge ab Zeile 75.
R12 ops/ai/packets/DLQ-02_review_packet.md, Forge ab Zeile 75.
R13 ops/ai/TEST_MAP.yaml.
R14 https://github.com/happyhippovip/2026-courier/pull/44.
R15 https://github.com/happyhippovip/2026-courier/pull/45.
R16 ops/ai/GOOGLE_CONTINUOUS_WORK.yaml, Zeilen 1–160.
R17 ops/ai/packets/ Verzeichnis, Pfade nicht gleich Paketvollständigkeit.

Private Uploadquellen, nicht öffentlich mitgepusht:
U01 markdown(20260918-074842).md eingefügt: Clock/Epoch/Freshness, 210 Zeilen.
U02 markdown (2)(20260918-075003).md eingefügt: Angriffsmatrix/Definition of Done, 295 Zeilen; spätere identische Kopien nicht mehrfach als unabhängige Evidenz zählen.
U03 Eingefügter Text(20260918-073629).txt: DLQ04/DLQ06/NEXT_WORK, 555 Zeilen.
U04 Eingefügter Text (2)(20260918-084227).txt: W01–W07, lokale Löschungen, Abschlussbehauptung, 498 Zeilen.
U05 Eingefügter Text.txt: historische Counter-/Thermalanalyse.
U06 markdown(20260918-062529).md eingefügt und markdown(20260918-063139).md eingefügt: Rollen/Budget/Test-Lane-Vorschläge.
U07 markdown(20260917-144412).md eingefügt: historischer Deploymentreport.
U08 Eingefügter Text(20260917-150144).txt: fix_final_ledger-Abläufe.

Externe offizielle OpenAI-Dokumentation, am 18.09.2026 gelesen, keine Repositorybelege:
W01 https://developers.openai.com/de-DE/docs/non-interactive-mode
W02 https://developers.openai.com/codex/cli/reference
W03 https://help.openai.com/de-de/articles/11369540-codex-mit-ihrem-chatgpt-tarif-nutzen

**Status:** Dokumentationssicherung. Produktionsabschluss, aktueller Laufzeitstatus, physische Abnahme und lokale Reboot-Sicherheit bleiben getrennte, hier nicht erfüllte Nachweise.
